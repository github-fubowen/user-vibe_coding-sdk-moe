#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
toolstack-pipeline.py — user-vibe_coding-sdk-moe 工具栈维护流水线 (v1.0, 2026-08-18)

Stages: probe(local) -> diff(upstream) -> data(sha256) -> sdk_tools(diff)
        -> report -> [--update] -> [--commit] -> [--push]
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
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SDK_ROOT = SCRIPT_DIR.parent
MANIFEST = SCRIPT_DIR / "toolstack.json"

# Windows-only fallback for gh; PATH is tried first. Override via GH_CLI_PATH
# (machine-specific install dirs are NOT hardcoded — privacy-safe for public repos).
GH_FALLBACKS = ([os.environ["GH_CLI_PATH"]] if os.environ.get("GH_CLI_PATH")
                else [r"C:\Program Files\GitHub CLI\gh.exe", "gh.exe"])

# v2.7.1: bound the network phase. Per-call timeout + total budget so a stalled
# gh api call can never starve CI (robustness case budget = 60s per case).
GH_CALL_TIMEOUT = 15
UPSTREAM_BUDGET_S = 30


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
    except subprocess.TimeoutExpired:
        # v2.7.1: degrade gracefully (rc=124) instead of crashing the whole run —
        # callers treat non-zero as "no data" and keep going.
        if check:
            raise
        return subprocess.CompletedProcess(cmd, 124, "", f"timeout after {timeout}s")


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
    res = run([gh, "api", *args], timeout=GH_CALL_TIMEOUT)
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
    deadline = time.monotonic() + UPSTREAM_BUDGET_S
    for rid, cfg in refs.items():
        repo, branch = cfg["repo"], cfg.get("branch", "main")
        rec = cfg.get("recorded", {})
        row = {"ref": rid, "repo": repo, "drift": False, "fields": {}}

        if gh is None:
            row["note"] = "gh missing — upstream check skipped"
            rows.append(row)
            continue

        if time.monotonic() > deadline:
            row["note"] = "upstream time budget exceeded — check skipped"
            rows.append(row)
            continue

        def gh_b(args: list[str]) -> dict | None:
            """gh_json with per-call budget enforcement (bounds worst case)."""
            if time.monotonic() > deadline:
                return None
            return gh_json(gh, args)

        repo_meta = gh_b([f"repos/{repo}"])
        head = gh_b([f"repos/{repo}/commits/{branch}"])
        rel = gh_b([f"repos/{repo}/releases/latest"]) if cfg.get("check") in ("release", "both") else None

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
    # v2.7.1: SDK_NONINTERACTIVE escape hatch — on some hosts (ConPTY/sandbox
    # shims) isatty() lies even for NUL stdin, which would block in input()
    # forever. The env var is the deterministic refusal path.
    if os.environ.get("SDK_NONINTERACTIVE") or not sys.stdin.isatty():
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
# --------------------------------------------------------------------------
# Stage 3b: sdk_tools diff (v2.10.2, F-43 治本)
# --------------------------------------------------------------------------
# `sdk_tools` was the only toolstack group with NO automation until v2.10.2:
# refs got upstream checks, local_tools got probe-tools, and sdk_tools got
# nothing — so 5 scripts added between v2.8.2 and v2.10.0 silently went
# unregistered and action-gate denied all of them (F-42).

DEFAULT_SDK_TOOL = {
    "category": "EXECUTE",
    "risk_tier": 2,          # conservative: controlled-modification tier
    "timeout_ms": 120000,
    "idempotent": False,     # conservative: forces an idempotency key on retry
    "cost_estimate": "none",
    "schema": "sdk-tool.v1",
    "runtime": "python-stdlib",
    "note": "auto-registered by toolstack-pipeline — review category/risk_tier",
}


# --- R-9: 重复登记检测（ResourceOS §21.1）-------------------------------------
# Stage 3b 此前"仅增不删、无查重"：同名能力的脚本换个文件名就会被再登记一次，
# 于是同一个能力在表里出现两份，路由与 health 都被稀释。
# §21.1 的原则是**标记进评审队列而非自动合并** —— 所以只 warn + 拒绝自动登记，
# 合并与否留给人工（capability 等价性不是 token 重叠能判定的）。
DUP_THRESHOLD = 0.7
_CJK = r"\u4e00-\u9fff"
_WORD_SPLIT_RE = re.compile(r"[^0-9a-zA-Z]+")
_CJK_RUN_RE = re.compile(f"[{_CJK}]+")
# 文件名里的噪声词：`x.py` 与 `x-alt.py` 的 "py" 不该贡献相似度
_STOP_TOKENS = {"py"}


def tokenize(text: str, drop_stop: bool = False) -> set[str]:
    """stdlib 分词：ASCII 按非字母数字切分，CJK 按字 bigram（中文无空格）。"""
    text = (text or "").lower()
    toks: set[str] = set()
    for run in _WORD_SPLIT_RE.split(text):
        if run:
            toks.add(run)
    for m in _CJK_RUN_RE.finditer(text):
        s = m.group(0)
        if len(s) == 1:
            toks.add(s)
        for i in range(len(s) - 1):
            toks.add(s[i:i + 2])
    return toks - _STOP_TOKENS if drop_stop else toks


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap_coefficient(a: set[str], b: set[str]) -> float:
    """|A∩B| / min(|A|,|B|) —— 判定"名字是已有名字的超集"（x-alt ⊃ x）。

    Jaccard 会惩罚额外 token（`verify-runner-alt` vs `verify-runner` 只有 0.5），
    而重复登记的形态恰恰是"同一个能力 + 后缀"，用重叠系数才抓得住。
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def name_tokens(key: str) -> set[str]:
    """条目键名的词袋（`verify-runner.py` → {verify, runner}）。"""
    stem = key[:-3] if key.endswith(".py") else key
    return tokenize(stem.replace("-", " ").replace("_", " "), drop_stop=True)


def desc_tokens(meta: dict) -> set[str]:
    """描述面的词袋：note + group + category + capabilities。"""
    parts = [meta.get("note", ""), meta.get("group", ""), meta.get("category", "")]
    parts.append(" ".join(meta.get("capabilities") or []))
    return tokenize(" ".join(str(p) for p in parts), drop_stop=True)


def find_duplicates(manifest: dict, candidates: list[str],
                    threshold: float = DUP_THRESHOLD) -> list[dict]:
    """待登记条目 vs 现存条目的重复检测（§21.1：只标记，不自动合并）。

    两个通道，任一超阈值即标记：
      * **name**（主通道）：待登记条目此时只有文件名，用重叠系数判定
        "名字是已有名字的超集"（`x-alt` ⊃ `x`）—— Jaccard 会被后缀稀释。
      * **desc**：note + group + category + capabilities 的 Jaccard（§21.1 原始口径）；
        自动登记条目尚无 note，此通道通常为 0，但对**手工填写过 note** 的
        重复条目有效。

    通用默认 note（"auto-registered by…"）**不计入**候选侧 —— 它对所有自动登记
    条目都一样，计入会把任意两个自动登记条目判成重复。
    """
    sdk_tools: dict = manifest.get("sdk_tools", {})
    out: list[dict] = []
    for name in candidates:
        cand_name = name_tokens(name)
        cand_desc: set[str] = set()  # 待登记条目无 note/group/capabilities
        best_n, best_d, best_k = 0.0, 0.0, None
        for k, meta in sdk_tools.items():
            if k == name:
                continue
            n_sim = overlap_coefficient(cand_name, name_tokens(k))
            d_sim = jaccard(cand_desc, desc_tokens(meta)) if cand_desc else 0.0
            score = max(n_sim, d_sim)
            if score > max(best_n, best_d):
                best_n, best_d, best_k = n_sim, d_sim, k
        if best_k is not None and max(best_n, best_d) >= threshold:
            out.append({"script": name, "duplicate_of": best_k,
                        "name_overlap": round(best_n, 3),
                        "desc_jaccard": round(best_d, 3),
                        "score": round(max(best_n, best_d), 3),
                        "threshold": threshold,
                        "action": "manual confirm — 不自动登记、不自动合并（§21.1）"})
    return out


def check_sdk_tools(manifest: dict, threshold: float = DUP_THRESHOLD,
                    scripts_dir: Path | None = None) -> tuple[list[dict], bool]:
    """Diff scripts/*.py against manifest `sdk_tools`. Returns (rows, drift)."""
    sdk_tools: dict = manifest.get("sdk_tools", {})
    exempt = set(manifest.get("sdk_tools_exempt", []))
    on_disk = {p.name for p in (scripts_dir or SCRIPT_DIR).glob("*.py")}
    unregistered = sorted(on_disk - set(sdk_tools) - exempt)
    missing = sorted(k for k in sdk_tools if k not in on_disk)
    rows = ([{"script": n, "status": "unregistered",
              "action": "auto-registered on --update"}
             for n in unregistered]
            + [{"script": n, "status": "missing",
                "action": "manual removal (never auto-deleted)"}
               for n in missing])
    # R-9：重复登记预警并入同一张表（状态独立，不改变 drift 语义 ——
    # 未登记才是 drift，疑似重复只是人工确认项）
    rows += [dict(r, status="suspect-duplicate") for r in
             find_duplicates(manifest, unregistered, threshold=threshold)]
    return rows, bool(unregistered or missing)


def update_sdk_tools(manifest: dict, allow_duplicate: bool = False,
                     threshold: float = DUP_THRESHOLD,
                     scripts_dir: Path | None = None) -> tuple[list[str], list[str]]:
    """Register unregistered scripts with conservative defaults.

    Additive only: registering a script is safe (it makes the script gateable).
    Removing a stale entry is destructive, so `missing` entries are reported but
    never auto-deleted (§10.9 risk tier 3 → human decision).

    R-9: scripts flagged as suspect-duplicate are **held back** — §21.1 says mark
    for review, never auto-merge, so the gate refuses to register them unless
    `--allow-duplicate` is passed.
    """
    sdk_tools: dict = manifest.setdefault("sdk_tools", {})
    exempt = set(manifest.get("sdk_tools_exempt", []))
    on_disk = {p.name for p in (scripts_dir or SCRIPT_DIR).glob("*.py")}
    pending = sorted(on_disk - set(sdk_tools) - exempt)
    dupes = find_duplicates(manifest, pending, threshold=threshold)
    held: set[str] = set() if allow_duplicate else {d["script"] for d in dupes}
    added = []
    for name in pending:
        if name in held:
            continue
        entry = dict(DEFAULT_SDK_TOOL)
        sdk_tools[name] = entry
        added.append(name)
    manifest["sdk_tools"] = dict(sorted(sdk_tools.items()))
    return added, sorted(held)


def print_report(probe_rows: list[dict], up_rows: list[dict], data_rows: list[dict],
                 sdk_rows: list[dict], drift: bool) -> None:
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
    log("== SDK tools (scripts/ vs sdk_tools) ==")
    if not sdk_rows:
        log(f"  OK  all scripts registered")
    for r in sdk_rows:
        log(f"  !!  {r['script']:<28} {r['status']} — {r['action']}")
    log("")
    log(f"Verdict: {'DRIFT DETECTED (run with --update)' if drift else 'CLEAN'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK tool-stack maintenance pipeline")
    ap.add_argument("--json", action="store_true", help="machine-readable report to stdout")
    ap.add_argument("--update", action="store_true", help="refresh drifted data + recorded pins")
    ap.add_argument("--commit", action="store_true", help="git add + commit changed files (local only)")
    ap.add_argument("--commit-msg", default=None, help="override conventional commit message")
    ap.add_argument("--push", action="store_true", help="push to origin after interactive y/N gate")
    ap.add_argument("--manifest", default=None,
                    help="use a different manifest (fixtures/tests; lets the drift "
                         "path be asserted offline instead of depending on live upstream)")
    ap.add_argument("--dup-threshold", type=float, default=DUP_THRESHOLD,
                    help=f"重复登记 Jaccard 阈值（默认 {DUP_THRESHOLD}；§21.1 只标记不合并）")
    ap.add_argument("--scripts-dir", default=None,
                    help="扫描哪个 scripts/ 目录（夹具；默认脚本自身所在目录）")
    ap.add_argument("--allow-duplicate", action="store_true",
                    help="放行疑似重复条目的自动登记（人工确认后使用）")
    args = ap.parse_args()

    manifest_path = Path(args.manifest).resolve() if args.manifest else MANIFEST
    if not manifest_path.exists():
        log(f"[fatal] manifest not found: {manifest_path}")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    refs: dict = manifest.get("refs", {})
    local_tools: dict = manifest.get("local_tools", {})

    gh = find_gh()
    if gh is None:
        log("[warn] gh CLI not found — upstream checks skipped (local probes only)")

    probe_rows = probe_local(local_tools)
    up_rows, drift = check_upstream(gh, refs)
    data_rows, data_bad = check_data(refs)
    sdir = Path(args.scripts_dir).resolve() if args.scripts_dir else None
    sdk_rows, sdk_drift = check_sdk_tools(manifest, threshold=args.dup_threshold,
                                          scripts_dir=sdir)
    drift = drift or data_bad or sdk_drift

    if args.json:
        report = {
            "time": now_iso(),
            "gh": bool(gh),
            "drift": drift,
            "local": probe_rows,
            "upstream": up_rows,
            "data": data_rows,
            "sdk_tools": sdk_rows,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(probe_rows, up_rows, data_rows, sdk_rows, drift)

    changed: list[str] = []
    if args.update:
        log("== Update ==")
        manifest["last_check"] = now_iso()
        changed = update_refs(gh, refs)
        added, held = update_sdk_tools(manifest, allow_duplicate=args.allow_duplicate,
                                       threshold=args.dup_threshold, scripts_dir=sdir)
        for name in added:
            log(f"  [update] sdk_tools += {name} (tier "
                f"{DEFAULT_SDK_TOOL['risk_tier']}, review category/risk_tier)")
        for name in held:
            log(f"  [held]   sdk_tools !{name} — 疑似重复登记，未自动登记"
                f"（人工确认后加 --allow-duplicate；§21.1 不自动合并）")
        changed += [f"sdk_tools+{n}" for n in added] + [f"sdk_tools!{n}" for n in held]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        log(f"  [update] manifest saved (last_check={manifest['last_check']}): {manifest_path}")

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
