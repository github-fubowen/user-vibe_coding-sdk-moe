#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
task-workspace.py — per-task 独立工作区 (v1.0, 2026-08-28, C1-1)

Purpose: implement 软件工厂 §3 Execution Plane (coding-agent-os 吸收, v2.5.0) —
each task gets an isolated directory tree with logs/ artifacts/ test-results/
agent-state.json; optionally a dedicated git worktree on a feature branch so
parallel tasks never collide on the same checkout.

Design rules (SDK §3/G-gates, §10.9 risk tiers):
  * Python 3.9+ stdlib only. JSON out. Exit: 0 = ok / 2 = error.
  * create = tier-2 controlled modification (new dirs, reversible by cleanup);
  * cleanup = tier-3: fail-closed unless the target dir contains the marker
    file agent-state.json AND its task_id matches (never rm a foreign dir);
  * git worktree ops are delegated to `git worktree add/remove` (branch created
    per task when --branch omitted); worktree never pushed.
  * Never touches anything outside --dir.

Usage:
  python task-workspace.py --dir <root> create --task t-001
  python task-workspace.py --dir <root> create --task t-001 --worktree <repo> --branch feat/x
  python task-workspace.py --dir <root> status --task t-001 --json
  python task-workspace.py --dir <root> verify --task t-001 [--worktree-repo <repo>]
  python task-workspace.py --dir <root> cleanup --task t-001
Exit codes: 0 = ok / 2 = error (incl. safety refusal).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "task-workspace.v1"
SUBDIRS = ("logs", "artifacts", "test-results")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def task_dir(root: Path, task_id: str) -> Path:
    return root / task_id


def state_file(root: Path, task_id: str) -> Path:
    return task_dir(root, task_id) / "agent-state.json"


def run_git(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True,
                           timeout=60, cwd=str(cwd) if cwd else None)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, "git not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def cmd_create(root: Path, task_id: str, worktree_repo: str | None,
               branch: str | None, force: bool) -> int:
    td = task_dir(root, task_id)
    if td.exists() and not force:
        print(f"[fatal] task workspace already exists: {td}", file=sys.stderr)
        return 2
    td.mkdir(parents=True, exist_ok=True)
    for sub in SUBDIRS:
        (td / sub).mkdir(exist_ok=True)
    state = {"schema": SCHEMA, "task_id": task_id, "status": "created",
             "created_at": now_iso(), "worktree": None, "branch": None,
             "worktree_repo": None}
    if worktree_repo:
        repo = Path(worktree_repo).resolve()
        br = branch or f"task/{task_id}"
        wt_path = td / "worktree"
        code, out = run_git(["-C", str(repo), "worktree", "add", str(wt_path), "-b", br])
        if code != 0:
            print(f"[fatal] worktree add failed: {out.strip()[:300]}", file=sys.stderr)
            return 2
        state.update({"status": "created", "worktree": str(wt_path),
                      "branch": br, "worktree_repo": str(repo)})
    (td / "agent-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"created": task_id, "dir": str(td), "worktree": state["worktree"],
                      "branch": state["branch"]}, ensure_ascii=False, indent=2))
    return 0


def load_state(root: Path, task_id: str) -> dict | None:
    sf = state_file(root, task_id)
    if not sf.exists():
        return None
    try:
        return json.loads(sf.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[fatal] invalid agent-state.json: {sf}", file=sys.stderr)
        return None


def cmd_status(root: Path, task_id: str, as_json: bool) -> int:
    st = load_state(root, task_id)
    if st is None:
        print(f"[fatal] task workspace not found: {task_id}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
    else:
        print(f"== task workspace {task_id} (status={st['status']}) ==")
        print(f"  dir:      {task_dir(root, task_id)}")
        print(f"  worktree: {st.get('worktree') or '-'}  branch: {st.get('branch') or '-'}")
    return 0


def cmd_verify(root: Path, task_id: str, worktree_repo: str | None) -> int:
    st = load_state(root, task_id)
    if st is None:
        print(f"[fatal] task workspace not found: {task_id}", file=sys.stderr)
        return 2
    td = task_dir(root, task_id)
    problems = []
    for sub in SUBDIRS:
        if not (td / sub).is_dir():
            problems.append(f"missing subdir: {sub}")
    if st.get("worktree"):
        wt = Path(st["worktree"])
        if not wt.is_dir():
            problems.append("worktree dir missing")
        elif worktree_repo:
            code, out = run_git(["-C", worktree_repo, "worktree", "list"])
            registered = {Path(ln.split()[0]).resolve()
                          for ln in out.splitlines() if ln.strip()}
            if code != 0 or wt.resolve() not in registered:
                problems.append("worktree not registered in repo")
    ok = not problems
    print(json.dumps({"task": task_id, "valid": ok, "problems": problems,
                      "status": st.get("status")}, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def cmd_cleanup(root: Path, task_id: str, keep_worktree: bool) -> int:
    td = task_dir(root, task_id)
    st = load_state(root, task_id)
    # fail-closed (tier-3): only remove a dir that carries OUR marker + matching id
    if st is None:
        print(f"[fatal] refuse: no agent-state.json marker for {task_id}", file=sys.stderr)
        return 2
    if st.get("task_id") != task_id:
        print(f"[fatal] refuse: marker task_id mismatch ({st.get('task_id')})", file=sys.stderr)
        return 2
    if st.get("worktree") and not keep_worktree:
        wt = Path(st["worktree"])
        repo = st.get("worktree_repo")
        if repo and wt.exists():
            code, out = run_git(["-C", repo, "worktree", "remove", str(wt), "--force"])
            if code != 0:
                print(f"[fatal] worktree remove failed: {out.strip()[:300]}", file=sys.stderr)
                return 2
    shutil.rmtree(td, ignore_errors=True)
    print(json.dumps({"removed": task_id, "dir": str(td),
                      "worktree_removed": bool(st.get("worktree")) and not keep_worktree},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-task isolated workspace (ref-20/C1-1)")
    ap.add_argument("--dir", required=True, help="workspace root (tasks live in <root>/<task_id>/)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="create task workspace (+ optional git worktree)")
    c.add_argument("--task", required=True)
    c.add_argument("--worktree", default=None, help="repo path for a dedicated git worktree")
    c.add_argument("--branch", default=None, help="worktree branch (default: task/<task_id>)")
    c.add_argument("--force", action="store_true", help="recreate existing workspace")

    s = sub.add_parser("status", help="show workspace state")
    s.add_argument("--task", required=True)
    s.add_argument("--json", action="store_true")

    v = sub.add_parser("verify", help="isolation + worktree verification")
    v.add_argument("--task", required=True)
    v.add_argument("--worktree-repo", default=None, help="repo to cross-check worktree registration")

    cl = sub.add_parser("cleanup", help="remove task workspace (fail-closed safety)")
    cl.add_argument("--task", required=True)
    cl.add_argument("--keep-worktree", action="store_true", help="leave the git worktree in place")

    args = ap.parse_args()
    root = Path(args.dir)

    if args.cmd == "create":
        return cmd_create(root, args.task, args.worktree, args.branch, args.force)
    if args.cmd == "status":
        return cmd_status(root, args.task, args.json)
    if args.cmd == "verify":
        return cmd_verify(root, args.task, args.worktree_repo)
    if args.cmd == "cleanup":
        return cmd_cleanup(root, args.task, args.keep_worktree)
    return 1


if __name__ == "__main__":
    sys.exit(main())
