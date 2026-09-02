#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spec-tasks-import.py — spec-kit tasks.md → task-state.v1 映射 (v1.0, 2026-08-28, C2-4)

Purpose: bridge GitHub spec-kit output into the SDK task state machine. Parses
a spec-kit tasks.md (checkbox list) into one task-state.v1 JSON per task in the
target --tasks-dir, aligned with the C1-2 production fields (priority /
acceptance_criteria / branch / workspace / runs).

Parsing contract (deterministic, stdlib, zero-LLM):
  * Lines matching `- [ ] **T-xxx** title...` → task id = T-xxx (fallback
    auto-increment T-001..); title = rest of the line after the id.
  * Optional `[P0|P1|P2|P3]` tag inside the line → priority.
  * Optional acceptance block: following lines (until next task / blank EOF)
    that start with `  - ` are joined into acceptance_criteria.
  * Unmatched `- [ ]` lines get auto ids and P2 priority.
  * `--dry-run` lists what would be written; never overwrites existing task ids
    unless --force.

Design rules (SDK §3/G-gates): never touches anything outside --tasks-dir;
writes are tier-2 (git-tracked JSON, reversible). Exit 0 = ok / 2 = error.

Usage:
  python spec-tasks-import.py --tasks tasks.md --tasks-dir .workbuddy/tasks
  python spec-tasks-import.py --tasks tasks.md --tasks-dir .workbuddy/tasks --dry-run --json
Exit codes: 0 = ok / 2 = error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "task-state.v1"
TASK_RE = re.compile(r"^\s*- \[ \]\s+\*\*(T-[\w.-]+)\*\*\s+(.*)$")
PRIORITY_RE = re.compile(r"\[(P[0-3])\]")
ACCEPT_RE = re.compile(r"^\s{2,}-\s+(.+)$")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_tasks(text: str) -> list[dict]:
    tasks: list[dict] = []
    auto = 0
    i = 0
    lines = text.splitlines()
    while i < len(lines):
        line = lines[i]
        m = TASK_RE.match(line)
        if m:
            tid, title = m.group(1), m.group(2)
            auto = 0
        elif re.match(r"^\s*- \[ \]", line):
            auto += 1
            tid, title = f"T-{auto:03d}", re.sub(r"^\s*- \[ \]\s*", "", line).strip()
        else:
            i += 1
            continue
        pm = PRIORITY_RE.search(title)
        priority = pm.group(1) if pm else "P2"
        title = PRIORITY_RE.sub("", title).strip()
        # acceptance block: following indented "- " lines
        accept = []
        j = i + 1
        while j < len(lines):
            am = ACCEPT_RE.match(lines[j])
            if am:
                accept.append(am.group(1).strip())
                j += 1
            elif lines[j].strip() == "":
                j += 1  # blank lines inside a block are tolerated
            else:
                break
        tasks.append({"task_id": tid, "title": title, "priority": priority,
                      "acceptance": " ".join(accept)})
        i = j
    return tasks


def build_task(parsed: dict) -> dict:
    ts = now_iso()
    return {
        "schema": SCHEMA, "task_id": parsed["task_id"], "title": parsed["title"],
        "mode": "SDD", "state": "INIT", "verdict": None,
        "priority": parsed["priority"], "acceptance_criteria": parsed["acceptance"],
        "branch": None, "workspace": None, "runs": [],
        "created_at": ts, "updated_at": ts,
        "history": [{"ts": ts, "from": None, "to": "INIT", "verdict": None,
                     "note": "imported from spec-kit tasks.md"}],
        "blackboard": {"recent_actions": [], "known_failures": [],
                       "residuals": [], "facts": {"source": "spec-kit/tasks.md"}},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Import spec-kit tasks.md into task-state.v1 (C2-4)")
    ap.add_argument("--tasks", required=True, help="tasks.md path")
    ap.add_argument("--tasks-dir", default=".workbuddy/tasks", help="target task store dir")
    ap.add_argument("--dry-run", action="store_true", help="list only, write nothing")
    ap.add_argument("--force", action="store_true", help="overwrite existing task ids")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tasks_path = Path(args.tasks)
    if not tasks_path.exists():
        print(f"[fatal] tasks.md not found: {tasks_path}", file=sys.stderr)
        return 2
    text = tasks_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_tasks(text)
    if not parsed:
        print(f"[fatal] no '- [ ]' tasks found in {tasks_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.tasks_dir)
    written, skipped, errors = [], [], []
    for p in parsed:
        target = out_dir / f"{p['task_id']}.json"
        if target.exists() and not args.force:
            skipped.append(p["task_id"])
            continue
        if args.dry_run:
            written.append(p["task_id"])
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(build_task(p), ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
            written.append(p["task_id"])
        except Exception as e:
            errors.append(f"{p['task_id']}: {type(e).__name__}: {e}")

    result = {"schema": "spec-tasks-import.v1", "parsed": len(parsed),
              "written": written, "skipped": skipped, "errors": errors,
              "dry_run": args.dry_run, "tasks_dir": str(out_dir)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        mode = "would write" if args.dry_run else "wrote"
        print(f"== spec-tasks-import: {len(parsed)} task(s) parsed, "
              f"{mode} {len(written)}, skipped {len(skipped)} ==")
        for tid in written:
            print(f"  {tid}")
        for tid in skipped:
            print(f"  {tid} (skipped: exists)")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
