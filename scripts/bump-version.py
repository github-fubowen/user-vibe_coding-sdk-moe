#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bump-version.py — 技能版本 bump 单命令化 (v1.0, 2026-08-22)

Purpose: replace the ~6-10 manual edits+commit of every version bump (§10.8
self-versioning) with ONE deterministic command. Updates version strings in
SKILL.md (frontmatter + title) and README, prepends a dated CHANGELOG header,
optionally commits locally. Never pushes (tier-4 gate, §10.9).

Design rules (SDK §10, §3/G-gates):
  * Only replaces exact version tokens `vX.Y.Z` matching the old version — no regex sweep.
  * Python 3.9+ stdlib only. JSON out via --json. Local commit default behavior.
  * Changelog body is left to the agent (narrative judgment is NOT scripted);
    script only inserts the `## vX.Y.Z（date）` header line.

Usage:
  python bump-version.py v1.11.0                  # dry-run: show what would change
  python bump-version.py v1.11.0 --apply          # actually apply
  python bump-version.py v1.11.0 --apply --commit # apply + local commit
  python bump-version.py v1.11.0 --json           # machine-readable dry-run
Exit codes: 0 = ok / 1 = old version not found or not applicable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SDK_ROOT = SCRIPT_DIR.parent
TARGETS = [  # (path, pattern kind)
    (SDK_ROOT / "SKILL.md", "frontmatter"),
    (SDK_ROOT / "SKILL.md", "title"),
    (SDK_ROOT / "README.md", "blurb"),
    (SDK_ROOT / "README.md", "version-line"),
    # T-511（F-60）：version-check 从 5 点扩到 7 点，bump 必须同步这两枚戳，
    # 否则下一次 bump 会立刻把新闸打红（闸门与发布工具必须成对改）。
    # 戳缺失时下面两个 kind 的 subn 计数为 0，plan 里不出现，不阻塞。
    (SDK_ROOT / "ENGINEERING.md", "engineering-head"),
    (SDK_ROOT / "ALIGNMENT.md", "alignment-head"),
]
CHANGELOG = SDK_ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r"v\d+\.\d+\.\d+")

# Set in main() once --json is parsed; read by log() to keep stdout pure JSON.
JSON_MODE = False


def log(msg: str) -> None:
    # v2.10.1: --json promises parseable JSON on stdout, so progress must go to
    # stderr in that mode (same contract as ci-smoke.py, F-45).
    print(msg, file=sys.stderr if JSON_MODE else sys.stdout, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_cn() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    kw = {"cwd": str(cwd)} if cwd else {}
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=60, **kw)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git"], 127, "", "git not found")


def git_root() -> Path:
    res = git("-C", str(SCRIPT_DIR), "rev-parse", "--show-toplevel")
    if res.returncode == 0 and res.stdout.strip():
        return Path(res.stdout.strip())
    return SDK_ROOT


def plan_edits(old: str, new: str) -> list[dict]:
    """Compute all line-level edits (no writes). Returns list of {file, old_line, new_line}."""
    edits: list[dict] = []
    for path, kind in TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if kind == "frontmatter":
            # line inside description: "MoE-optimized coding skill SDK (vX.Y.Z). USE ..."
            pat = re.compile(r"(MoE-optimized coding skill SDK \()" + re.escape(old) + r"(\))")
        elif kind == "title":
            pat = re.compile(r"(# user-vibe_coding-sdk-moe )" + re.escape(old) + r"( —)")
        elif kind == "blurb":
            # README first line: "> MoE 特化编程技能 SDK（vX.Y.Z）——..."
            pat = re.compile(r"(MoE 特化编程技能 SDK（)" + re.escape(old) + r"(）——)")
        elif kind == "engineering-head":
            # ENGINEERING.md 第 3 行：`> vX.Y.Z · YYYY-MM-DD · …`
            pat = re.compile(r"(^> )" + re.escape(old) + r"( ·)", re.M)
        elif kind == "alignment-head":
            # ALIGNMENT.md 头部：`> 吸收对象本体：`user-vibe_coding-sdk-moe`（vX.Y.Z）`
            pat = re.compile(r"(吸收对象本体：`user-vibe_coding-sdk-moe`（)"
                             + re.escape(old) + r"(）)")
        else:  # version-line: ">- 版本：**vX.Y.Z**（..."
            pat = re.compile(r"(\*\*)" + re.escape(old) + r"(\*\*)")
        new_text, n = pat.subn(r"\g<1>" + new + r"\g<2>", text)
        if n:
            edits.append({"file": str(path), "kind": kind, "count": n})
    return edits


def apply_edits(edits: list[dict], old: str, new: str) -> None:
    for e in edits:
        path = Path(e["file"])
        text = path.read_text(encoding="utf-8")
        pats = {
            "frontmatter": re.compile(r"(MoE-optimized coding skill SDK \()" + re.escape(old) + r"(\))"),
            "title": re.compile(r"(# user-vibe_coding-sdk-moe )" + re.escape(old) + r"( —)"),
            "blurb": re.compile(r"(MoE 特化编程技能 SDK（)" + re.escape(old) + r"(）——)"),
            "version-line": re.compile(r"(\*\*)" + re.escape(old) + r"(\*\*)"),
            "engineering-head": re.compile(r"(^> )" + re.escape(old) + r"( ·)", re.M),
            "alignment-head": re.compile(
                r"(吸收对象本体：`user-vibe_coding-sdk-moe`（)" + re.escape(old) + r"(）)"),
        }
        text, n = pats[e["kind"]].subn(r"\g<1>" + new + r"\g<2>", text)
        path.write_text(text, encoding="utf-8")
        log(f"  [edit] {e['kind']:<12} {e['file']}  ({n}× {old} -> {new})")


def plan_size_sync() -> list[dict]:
    """T-15：算出声明体积与实测的差值（F-13 漂移类）。

    v2.6.1 的声明停在 30,253B，实测已 31,659B —— 声明一旦失真，G2「主文件多大」
    这个 token 预算依据就跟着失真。体积声明必须由脚本回写，不能靠人记。
    """
    out: list[dict] = []
    skill = SDK_ROOT / "SKILL.md"
    if not skill.exists():
        return out
    actual = skill.stat().st_size
    for path, pats in (
        (skill, [r"实测 \d{4}-\d{2}-\d{2} ?= ?[\d,]+B"]),
        (SDK_ROOT / "README.md", [r"实测 [\d,]+B \d{4}-\d{2}-\d{2}", r"~(\d+)KB"]),
    ):
        if not path.exists():
            continue
        for ln_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "主文件" not in line and "SKILL.md" not in line:
                continue
            for pat in pats:
                m = re.search(pat, line)
                if m:
                    out.append({"file": str(path), "line": ln_no, "pattern": pat,
                                "old": m.group(0), "actual_bytes": actual})
    return out


def apply_size_sync() -> int:
    """Rewrite size declarations with measured values. Returns number of edits."""
    skill = SDK_ROOT / "SKILL.md"
    actual = skill.stat().st_size
    kb = max(1, round(actual / 1024))
    today = today_cn()
    subs = [
        (re.compile(r"实测 \d{4}-\d{2}-\d{2} ?= ?[\d,]+B"), f"实测 {today} = {actual:,}B"),
        (re.compile(r"实测 [\d,]+B \d{4}-\d{2}-\d{2}"), f"实测 {actual:,}B {today}"),
        (re.compile(r"~(\d+)KB"), f"~{kb}KB"),
    ]
    n = 0
    for path in (skill, SDK_ROOT / "README.md"):
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        for i, line in enumerate(lines):
            if "主文件" not in line and "SKILL.md" not in line:
                continue
            new_line = line
            for pat, rep in subs:
                new_line = pat.sub(rep, new_line)
            if new_line != line:
                lines[i] = new_line
                n += 1
                changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            log(f"  [edit] size-sync {path} -> {actual:,}B (~{kb}KB)")
    return n


def prepend_changelog(new: str) -> None:
    if not CHANGELOG.exists():
        log("  [warn] CHANGELOG.md not found — skipped")
        return
    text = CHANGELOG.read_text(encoding="utf-8")
    header = f"## {new}（{today_cn()}）"
    if header in text:
        log("  [skip] changelog header already present")
        return
    lines = text.splitlines()
    # Layout-robust insert: place the header right BEFORE the first existing
    # version entry (`## vX.Y.Z`), no matter where the `# CHANGELOG` title sits.
    # (Canonical layout = title/intro first, newest entry at top; this insert
    # repairs both layouts instead of assuming one.)
    insert_at = None
    for i, ln in enumerate(lines):
        if ln.startswith("## v") and re.match(r"^## v\d+\.\d+\.\d+", ln):
            insert_at = i
            break
    if insert_at is None:
        # no entries yet — append at end (or after title if present)
        insert_at = len(lines)
    lines.insert(insert_at, "")
    lines.insert(insert_at, header)
    CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"  [edit] changelog header {header} inserted (before line {insert_at + 1})")


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK version bump (self-versioning, §10.8)")
    ap.add_argument("new_version", nargs="?", default=None,
                    help="new version, e.g. v1.11.0 (omit when using --sync-size standalone)")
    ap.add_argument("--old", default=None, help="old version (default: detect from SKILL.md)")
    ap.add_argument("--apply", action="store_true", help="apply edits (default: dry-run)")
    ap.add_argument("--commit", action="store_true", help="git add + commit (local only, after --apply)")
    ap.add_argument("--commit-msg", default=None, help="override conventional commit message")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--sync-size", action="store_true",
                    help="回写 SKILL/README 的体积声明为实测值（T-15，防 F-13 类漂移）")
    args = ap.parse_args()
    global JSON_MODE
    JSON_MODE = args.json

    # --sync-size 可独立于版本 bump 使用（体积漂移不必等发版才修）
    if args.new_version is None:
        if not args.sync_size:
            log("[fatal] new_version required (or use --sync-size standalone)")
            return 1
        if args.json:
            print(json.dumps({"size_sync": plan_size_sync()}, ensure_ascii=False, indent=2))
            return 0
        log("== size sync (standalone) ==")
        found = plan_size_sync()
        if not found:
            log("  [warn] no size declarations found to sync")
            return 0
        for s in found:
            log(f"  [plan] {s['file']}:{s['line']}  {s['old']} -> 实测 {s['actual_bytes']:,}B")
        if args.apply:
            apply_size_sync()
        else:
            log("  (dry-run — re-run with --apply to write)")
        return 0

    new = args.new_version if args.new_version.startswith("v") else "v" + args.new_version
    if not VERSION_RE.fullmatch(new):
        log(f"[fatal] invalid version: {new} (expect vX.Y.Z)")
        return 1

    old = args.old
    if old is None:
        m = VERSION_RE.search((SDK_ROOT / "SKILL.md").read_text(encoding="utf-8"))
        old = m.group(0) if m else None
    if not old:
        log("[fatal] cannot detect old version (use --old)")
        return 1

    edits = plan_edits(old, new)
    if not edits:
        log(f"[fatal] no version tokens {old} found in targets — abort (nothing to bump)")
        return 1
    if old == new:
        log(f"[fatal] old == new ({old}) — nothing to bump")
        return 1

    size_plan = plan_size_sync() if args.sync_size else []

    log(f"== Version bump: {old} -> {new} (dry-run)" if not args.apply else f"== Version bump: {old} -> {new}")
    for e in edits:
        log(f"  [plan] {e['kind']:<12} {e['file']}  ({e['count']}×)")
    for s in size_plan:
        log(f"  [plan] size-sync   {s['file']}:{s['line']}  {s['old']} -> 实测 {s['actual_bytes']:,}B")

    # v2.10.1 (F-47): --json used to `return 0` here, so `--apply --json` printed
    # a plan and wrote NOTHING — a silent no-op that only the version-check gate
    # caught. Apply first, then emit JSON with an explicit `applied` verdict.
    applied = False
    if args.apply:
        apply_edits(edits, old, new)
        prepend_changelog(new)
        if args.sync_size:
            apply_size_sync()
        applied = True
    else:
        log("  (dry-run — re-run with --apply to write)")

    if args.json:
        print(json.dumps({
            "old": old, "new": new,
            "applied": applied, "dry_run": not args.apply,
            "edits": edits,
            "size_sync": size_plan,
            "changelog_header": f"## {new}（{today_cn()}）",
        }, ensure_ascii=False, indent=2))

    if not args.apply and not args.commit:
        return 0
    # --commit without --apply: commit the pending working-tree changes only.

    if args.commit:
        root = git_root()
        for rel in ("SKILL.md", "README.md", "CHANGELOG.md"):
            res = git("add", "--", os.path.relpath(SDK_ROOT / rel, root), cwd=root)
            if res.returncode != 0:
                log(f"  [warn] add failed for {rel}: {res.stderr.strip()}")
                return 1
        if args.commit_msg:
            msg = args.commit_msg
        elif old != new:
            msg = f"chore(skill-moe): bump v{old[1:]} -> v{new[1:]}"
        else:
            msg = "chore(skill-moe): version bump 收尾（changelog 正文）"
        res = git("commit", "-m", msg, cwd=root)
        log(res.stdout.strip() or res.stderr.strip())
        log(f"  [commit] ok -> {git('log', '-1', '--format=%h', cwd=root).stdout.strip()}")
        log("  [note] push requires explicit user confirmation (§10) — not performed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
