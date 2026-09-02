#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review-prefilter.py — Review 预过滤：差异统计 + 静态检查 → 精简关注包 (v1.0, 2026-08-22)

Purpose: instead of the Review agent swallowing a whole large diff (blowing up
context injection), run deterministic pre-filtering FIRST: git diff stats
(which files / how much changed) + optional lint/typecheck/test steps. Emit a
COMPACT "focus packet" (top-N changed files + bounded check results) — the LLM
only reads the packet, cutting Review-mode context injection 50-80% on big PRs.

Design rules (SDK §3/G-gates, §6 Review, ref-19 §2.2):
  * Python 3.9+ stdlib only. JSON out. Read-only (never modifies anything).
  * Bounded output: top-N files (--top 15), bounded check tails (--tail 8).
  * Exit: 0 = all checks pass / 2 = at least one check failed (blocker).

Usage:
  python review-prefilter.py --base main --json
  python review-prefilter.py --base main --checks "pytest -q" "python -m py_compile x.py" --top 10
  python review-prefilter.py --base HEAD~1 --config review.json --json
Exit codes: 0 = checks pass / 2 = a check failed (blocker for review).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run(cmd: list[str], timeout: int = 120, cwd: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "command not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def git_diff_stats(base: str, cwd: str) -> dict:
    """Parse `git diff --numstat base` into per-file +/- counts. Bounded to top-N later."""
    res = run(["git", "-C", cwd, "diff", "--numstat", base], timeout=30)
    files, total_add, total_del = [], 0, 0
    if res.returncode != 0:
        return {"error": res.stderr.strip() or "git diff failed", "files": [], "total_added": 0, "total_deleted": 0}
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add, dele, path = parts
        if add == "-" or dele == "-":  # binary
            continue
        a, d = int(add), int(dele)
        total_add += a
        total_del += d
        files.append({"path": path, "added": a, "deleted": d})
    files.sort(key=lambda f: -(f["added"] + f["deleted"]))
    return {"files": files, "total_files": len(files), "total_added": total_add, "total_deleted": total_del}


def main() -> int:
    ap = argparse.ArgumentParser(description="Review pre-filter: diff stats + static checks → focus packet")
    ap.add_argument("--base", default="HEAD", help="git base ref for diff (default HEAD = uncommitted)")
    ap.add_argument("--top", type=int, default=15, help="max changed files in focus packet")
    ap.add_argument("--checks", nargs="+", default=None, help="check commands: --checks 'pytest -q' 'ruff check .'")
    ap.add_argument("--config", default=None, help="JSON config {checks:[{cmd:[...],timeout}]}")
    ap.add_argument("--tail", type=int, default=8, help="bounded tail lines per check (G1)")
    ap.add_argument("--cwd", default=None, help="working dir (default: cwd)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cwd = args.cwd or str(Path.cwd())

    diff = git_diff_stats(args.base, cwd)

    checks = []
    if args.config:
        cfg_path = Path(args.config)
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            checks = [{"name": c.get("name", " ".join(c["cmd"])), "cmd": c["cmd"],
                       "timeout": int(c.get("timeout", 120))} for c in cfg.get("checks", [])]
    if args.checks:
        checks = [{"name": c, "cmd": c.split(), "timeout": 120} for c in args.checks]

    check_rows = []
    for ch in checks:
        res = run(ch["cmd"], timeout=ch["timeout"], cwd=cwd)
        out = (res.stdout or "").strip().splitlines()
        err = (res.stderr or "").strip().splitlines()
        combined = out + (["[stderr]"] + err if err else [])
        check_rows.append({"name": ch["name"], "ok": res.returncode == 0,
                           "exit_code": res.returncode, "tail": combined[-args.tail:]})
    any_fail = any(not r["ok"] for r in check_rows)

    focus = diff.get("files", [])[: args.top]
    packet = {
        "time": now_iso(),
        "base": args.base,
        "diff": diff,
        "focus_files": focus,
        "checks": check_rows,
        "blockers": any_fail,
    }

    if args.json:
        print(json.dumps(packet, ensure_ascii=False, indent=2))
    else:
        d = diff
        print(f"== Review prefilter (base: {args.base}) ==")
        if d.get("error"):
            print(f"  !! {d['error']}")
        else:
            print(f"  diff: {d['total_files']} files, +{d['total_added']}/-{d['total_deleted']}")
            for f in focus:
                print(f"  {f['added']:>4} +{f['deleted']:>4} -  {f['path']}")
        for r in check_rows:
            print(f"  {'OK ' if r['ok'] else '!! '} check: {r['name']} (exit {r['exit_code']})")
            for ln in r["tail"]:
                print(f"        | {ln[:110]}")
    return 2 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
