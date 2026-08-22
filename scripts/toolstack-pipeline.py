#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
toolstack-pipeline.py — user-vibe_coding-sdk-moe 工具栈维护流水线 (v1.0, 2026-08-18)

Stages: probe(local) -> diff(upstream) -> report -> [--update] -> [--commit] -> [--push]
Design rules (SDK §10):
  * Local commit = default; push NEVER without explicit interactive confirmation.
  * Single source of truth: toolstack.json next to this script (same dir).
  * gh CLI for upstream checks; degrade gracefully when gh is missing.
  * Python 3.9+ stdlib only. No network except via gh/curl subprocesses.

Usage:
  python toolstack-pipeline.py                 # probe + diff + report (read-only)
  python toolstack-pipeline.py --json          # same, machine-readable report to stdout
  python toolstack-pipeline.py --update        # refresh drifted data + manifest pins
  python toolstack-pipeline.py --commit        # git add + commit changed files (local)
  python toolstack-pipeline.py --update --commit
  python toolstack-pipeline.py --push          # interactive y/N gate, then git push
Exit codes: 0 = clean / 2 = drift detected (report-only mode).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SDK_ROOT = SCRIPT_DIR.parent
MANIFEST = SCRIPT_DIR / "toolstack.json"

# Windows-only fallback for gh; PATH is tried first. Override via GH_CLI_PATH
# (machine-specific install dirs are NOT hardcoded — privacy-safe for public repos).
GH_FALLBACKS = ([os.environ["GH_CLI_PATH"]] if os.environ.get("GH_CLI_PATH")
                else [r"C:\Program Files\GitHub CLI\gh.exe", "gh.exe"])


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], timeout: int = 60, check: bool = False, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess; list-args only (no shell). Returns CompletedProcess."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        if check:
            raise
        return subprocess.CompletedProcess(cmd, 127, "", "command not found")


def find_gh() -> str | None:
    """Locate the gh CLI binary."""
    found = run(["gh", "--version"], timeout=10)
    if found.returncode == 0:
        return "gh"
    for cand in GH_FALLBACKS:
        if Path(cand).exists():
            return cand
    return None


def gh_json(gh: str, args: list[str]) -> dict | None:
    """gh api call returning parsed JSON (or None on failure)."""
    res = run([gh, "api", *args], timeout=60)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def sha256_of(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Stage 0/1: local tool probes
# --------------------------------------------------------------------------
def probe_local(local_tools: dict) -> list[dict]:
    rows = []
    for name, cfg in local_tools.items():
        cmd = list(cfg["cmd"])
        res = None
        # Windows: npm shims are extensionless (`ocr`) — CreateProcess needs *.cmd/*.exe.
        candidates = [cmd]
        if os.name == "nt" and "." not in os.path.basename(cmd[0]):
            candidates.append([cmd[0] + ".cmd", *cmd[1:]])
            candidates.append([cmd[0] + ".exe", *cmd[1:]])
        for cand in candidates:
            res = run(cand, timeout=30)
            if res.returncode != 127:
                break
        ok = res is not None and res.returncode == 0
        ver = None
        if ok and res.stdout.strip():
            if cfg.get("grep"):
                ver = next((ln.strip() for ln in res.stdout.splitlines() if cfg["grep"] in ln), None)
            if ver is None:
                ver = res.stdout.strip().splitlines()[0]
        rows.append({"tool": name, "ok": ok, "version": ver, "note": cfg.get("note", "")})
    return rows


# --------------------------------------------------------------------------
# Stage 2: upstream diff
# --------------------------------------------------------------------------
def check_upstream(gh: str | None, refs: dict) -> tuple[list[dict], bool]:
    """Compare recorded pins vs upstream. Returns (rows, drift_flag)."""
    rows, drift = [], False
    for rid, cfg in refs.items():
        repo, branch = cfg["repo"], cfg.get("branch", "main")
        rec = cfg.get("recorded", {})
        row = {"ref": rid, "repo": repo, "drift": False, "fields": {}}

        if gh is None:
            row["note"] = "gh missing — upstream check skipped"
            rows.append(row)
            continue

        repo_meta = gh_json(gh, [f"repos/{repo}"])
        head = gh_json(gh, [f"repos/{repo}/commits/{branch}"])
        rel = gh_json(gh, [f"repos/{repo}/releases/latest"]) if cfg.get("check") in ("release", "both") else None

        cur = {
            "head": (head or {}).get("sha"),
            "head_date": ((head or {}).get("commit", {}) or {}).get("author", {}).get("date"),
            "release": (rel or {}).get("tag_name"),
            "stars": (repo_meta or {}).get("stargazers_count"),
            "pushed_at": (repo_meta or {}).get("pushed_at"),
        }

        for key, cur_val in cur.items():
            if cur_val is None or key not in rec:
                continue
            # stars are informational only (move every check); drift = head/release/pushed_at
            if key == "stars":
                row.setdefault("info", {})[key] = {"recorded": rec[key], "current": cur_val}
                continue
            if str(rec[key]) != str(cur_val):
                row["fields"][key] = {"recorded": rec[key], "current": cur_val}
                row["drift"] = True
        drift = drift or row["drift"]
        rows.append(row)
    return rows, drift


# --------------------------------------------------------------------------
# Stage 3: data integrity (vendored files)
# --------------------------------------------------------------------------
def check_data(refs: dict) -> tuple[list[dict], bool]:
    rows, bad = [], False
    for rid, cfg in refs.items():
        data = cfg.get("data")
        if not data:
            continue
        p = Path(data["path"]).expanduser()
        cur = sha256_of(p)
        row = {"ref": rid, "file": str(p), "ok": cur == data["sha256"], "current_sha": cur, "recorded_sha": data["sha256"]}
        rows.append(row)
        bad = bad or not row["ok"]
    return rows, bad


# --------------------------------------------------------------------------
# Stage 4: --update
# --------------------------------------------------------------------------
def update_refs(gh: str | None, refs: dict) -> list[str]:
    """Apply update strategies per ref; returns list of changed ref ids."""
    changed = []
    for rid, cfg in refs.items():
        # 1) update recorded pins for any ref with upstream data
        if gh is not None:
            repo, branch = cfg["repo"], cfg.get("branch", "main")
            repo_meta = gh_json(gh, [f"repos/{repo}"])
            head = gh_json(gh, [f"repos/{repo}/commits/{branch}"])
            rel = gh_json(gh, [f"repos/{repo}/releases/latest"]) if cfg.get("check") in ("release", "both") else None
            rec = cfg.setdefault("recorded", {})
            new_vals = {}
            if head:
                new_vals["head"] = head["sha"]
                new_vals["head_date"] = head["commit"]["author"]["date"]
            if rel:
                new_vals["release"] = rel["tag_name"]
            if repo_meta:
                new_vals["stars"] = repo_meta["stargazers_count"]
                new_vals["pushed_at"] = repo_meta["pushed_at"]
            if any(rec.get(k) != v for k, v in new_vals.items()):
                rec.update(new_vals)
                changed.append(rid)
                log(f"  [update] {rid}: recorded pins synced -> {json.dumps(new_vals, ensure_ascii=False)}")

        # 2) vendored data re-fetch (only public-apis style: raw url + PROVENANCE template)
        data = cfg.get("data")
        if data and gh is not None:
            p = Path(data["path"]).expanduser()
            head = (cfg.get("recorded") or {}).get("head")
            if head and data.get("raw_url_template"):
                url = data["raw_url_template"].format(head=head)
                res = run(["curl", "-sL", url, "-o", str(p)], timeout=180)
                if res.returncode == 0:
                    new_sha = sha256_of(p)
                    if new_sha and new_sha != data["sha256"]:
                        data["sha256"] = new_sha
                        log(f"  [update] {rid}: data refreshed @ {head[:12]} sha256={new_sha[:16]}…")
                        refresh_provenance(Path(data["provenance"]).expanduser(), cfg, new_sha)
                        changed.append(rid)
                else:
                    log(f"  [warn] {rid}: data download failed ({res.returncode})")

    return changed


def refresh_provenance(prov: Path, cfg: dict, new_sha: str) -> None:
    """Update the PROVENANCE.md table (public-apis style) in place."""
    if not prov.exists():
        log(f"  [warn] PROVENANCE not found: {prov}")
        return
    rec = cfg.get("recorded") or {}
    repl = [
        (r"- \*\*stars\*\*: [0-9,]+.*", f"- **stars**: {rec.get('stars', '?')}（{now_iso()[:10]} 更新）"),
        (r"\| 上游 commit SHA \| `[0-9a-f]+` \|", f"| 上游 commit SHA | `{rec.get('head', '?')}` |"),
        (r"\| 上游提交时间 \| [^|]+ \|", f"| 上游提交时间 | {rec.get('head_date', '?')} |"),
        (r"\| 本地拉取时间 \| [^|]+ \|", f"| 本地拉取时间 | {now_iso()} |"),
        (r"\| data/README.md SHA256 \| `[0-9a-f]+` \|", f"| data/README.md SHA256 | `{new_sha}` |"),
    ]
    text = prov.read_text(encoding="utf-8")
    for pat, rep in repl:
        text = re.sub(pat, rep, text)
    prov.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# Stage 5/6: git commit + push gate
# --------------------------------------------------------------------------
def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    kw = {"cwd": str(cwd)} if cwd else {}
    return run(["git", *args], timeout=60, **kw)


def git_root() -> Path:
    """Repo root containing the SDK (cwd-neutral; works via symlink too)."""
    res = git("-C", str(SCRIPT_DIR), "rev-parse", "--show-toplevel")
    if res.returncode == 0 and res.stdout.strip():
        return Path(res.stdout.strip())
    return SCRIPT_DIR


def do_commit(message: str, paths: list[str]) -> None:
    root = git_root()
    for p in paths:
        rel = os.path.relpath(p, root)  # relative to root: avoids symlink "outside repo" rejections
        res = git("add", "--", rel, cwd=root)
        if res.returncode != 0:
            log(f"  [warn] add failed for {p}: {res.stderr.strip()}")
            return
    res = git("commit", "-m", message, cwd=root)
    log(res.stdout.strip() or res.stderr.strip())
    if res.returncode != 0:
        log("  [warn] commit failed or nothing to commit")
    else:
        log(f"  [commit] ok -> {git('log', '-1', '--format=%h', cwd=root).stdout.strip()}")


def do_push() -> None:
    """Interactive y/N gate; refuses in non-TTY (sandbox) with instructions."""
    if not sys.stdin.isatty():
        log("  [skip] push requires an interactive terminal (SDK §10: explicit confirmation).")
        log("  Run this yourself:  git push")
        return
    try:
        ans = input("  Push to origin? (y/N) ").strip().lower()
    except EOFError:
        ans = ""
    if ans not in ("y", "yes"):
        log("  [skip] push declined.")
        return
    res = git("push", cwd=git_root())
    log(res.stdout.strip() or res.stderr.strip())


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def print_report(probe_rows: list[dict], up_rows: list[dict], data_rows: list[dict], drift: bool) -> None:
    log("== Local tool probes ==")
    for r in probe_rows:
        v = r["version"] or ("—" if r["ok"] else "MISSING")
        log(f"  {'OK ' if r['ok'] else '!! '} {r['tool']:<28} {v}")
    log("== Upstream pins ==")
    for r in up_rows:
        if r.get("note"):
            log(f"  --  {r['ref']:<18} {r['note']}")
            continue
        fields = r.get("fields", {})
        if fields:
            for k, v in fields.items():
                log(f"  !!  {r['ref']:<18} {k}: {v['recorded']} -> {v['current']}")
        else:
            info = r.get("info", {}).get("stars")
            star_note = f"  (stars {info['recorded']} -> {info['current']})" if info else ""
            log(f"  OK  {r['ref']:<18} up-to-date{star_note}")
    log("== Data integrity ==")
    if not data_rows:
        log("  (no vendored data entries)")
    for r in data_rows:
        log(f"  {'OK ' if r['ok'] else '!! '} {r['ref']:<18} sha256={'match' if r['ok'] else 'MISMATCH'}")
    log("")
    log(f"Verdict: {'DRIFT DETECTED (run with --update)' if drift else 'CLEAN'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK tool-stack maintenance pipeline")
    ap.add_argument("--json", action="store_true", help="machine-readable report to stdout")
    ap.add_argument("--update", action="store_true", help="refresh drifted data + recorded pins")
    ap.add_argument("--commit", action="store_true", help="git add + commit changed files (local only)")
    ap.add_argument("--commit-msg", default=None, help="override conventional commit message")
    ap.add_argument("--push", action="store_true", help="push to origin after interactive y/N gate")
    args = ap.parse_args()

    if not MANIFEST.exists():
        log(f"[fatal] manifest not found: {MANIFEST}")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    refs: dict = manifest.get("refs", {})
    local_tools: dict = manifest.get("local_tools", {})

    gh = find_gh()
    if gh is None:
        log("[warn] gh CLI not found — upstream checks skipped (local probes only)")

    probe_rows = probe_local(local_tools)
    up_rows, drift = check_upstream(gh, refs)
    data_rows, data_bad = check_data(refs)
    drift = drift or data_bad

    if args.json:
        report = {
            "time": now_iso(),
            "gh": bool(gh),
            "drift": drift,
            "local": probe_rows,
            "upstream": up_rows,
            "data": data_rows,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(probe_rows, up_rows, data_rows, drift)

    changed: list[str] = []
    if args.update:
        log("== Update ==")
        manifest["last_check"] = now_iso()
        changed = update_refs(gh, refs)
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log(f"  [update] manifest saved (last_check={manifest['last_check']}): {MANIFEST}")

    if args.commit:
        msg = args.commit_msg or f"chore(skill-moe): toolstack update ({', '.join(changed) or 'no drift'})"
        log("== Commit ==")
        do_commit(msg, [str(MANIFEST), str(SCRIPT_DIR)])

    if args.push:
        log("== Push (explicit-confirmation gate) ==")
        do_push()

    return 2 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
