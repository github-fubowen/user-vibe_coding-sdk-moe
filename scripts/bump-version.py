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
]
CHANGELOG = SDK_ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r"v\d+\.\d+\.\d+")


def log(msg: str) -> None:
    print(msg, flush=True)


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
        }
        text, n = pats[e["kind"]].subn(r"\g<1>" + new + r"\g<2>", text)
        path.write_text(text, encoding="utf-8")
        log(f"  [edit] {e['kind']:<12} {e['file']}  ({n}× {old} -> {new})")


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
    ap.add_argument("new_version", help="new version, e.g. v1.11.0")
    ap.add_argument("--old", default=None, help="old version (default: detect from SKILL.md)")
    ap.add_argument("--apply", action="store_true", help="apply edits (default: dry-run)")
    ap.add_argument("--commit", action="store_true", help="git add + commit (local only, after --apply)")
    ap.add_argument("--commit-msg", default=None, help="override conventional commit message")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

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

    if args.json:
        print(json.dumps({
            "old": old, "new": new, "edits": edits,
            "changelog_header": f"## {new}（{today_cn()}）",
        }, ensure_ascii=False, indent=2))
        return 0

    log(f"== Version bump: {old} -> {new} (dry-run)" if not args.apply else f"== Version bump: {old} -> {new}")
    for e in edits:
        log(f"  [plan] {e['kind']:<12} {e['file']}  ({e['count']}×)")
    if not args.apply:
        log("  (dry-run — re-run with --apply to write)")
        if not args.commit:
            return 0
        # --commit without --apply: commit the pending working-tree changes only.

    if args.apply:
        apply_edits(edits, old, new)
        prepend_changelog(new)

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
