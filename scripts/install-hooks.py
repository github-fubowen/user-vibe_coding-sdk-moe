#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install-hooks.py — 安装/卸载 SDK pre-commit 钩子（ref-23，评估报告 P0-1）

Installs `.git/hooks/pre-commit` in the skills repo that execs
`user-vibe_coding-sdk-moe/scripts/git-pre-commit.py`. Idempotent; refuses to
overwrite a foreign hook unless --force. The hook file itself is NOT
version-controlled (git convention) — this installer is the reproducible path.

Design rules (SDK §10, ref-23):
  * Python 3.9+ stdlib only. Never pushes. Never touches anything but the hook.
  * --repo overrides repo root (testing); default: git rev-parse from scripts dir.
  * SDK_RELPATH is derived at install time from this file's own location (F2,
    C0-2): renaming the SDK directory re-derives the path, so the gate stays
    attached (hook body never hardcodes the old name).
  * Hook body resolves python via the current interpreter's absolute path
    (machine-local hook file, never committed — safe); hook runs with cwd =
    repo top (git contract).

Usage:
  python install-hooks.py                  # install (idempotent)
  python install-hooks.py --remove         # uninstall
  python install-hooks.py --repo /tmp/x    # install into a specific repo (testing)
Exit codes: 0 = ok / 1 = foreign hook present without --force / 2 = error.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SDK_DIR = SCRIPT_DIR.parent


def resolve_sdk_relpath(root: Path) -> str:
    """F2: repo-relative path of the SDK dir, derived at install time.

    Prefers the true relative path inside `root`; falls back to the directory
    basename when the SDK lives outside `root` (e.g. --repo testing with a
    throwaway repo, or a renamed directory copy).
    """
    try:
        return str(SDK_DIR.resolve().relative_to(root.resolve()))
    except ValueError:
        return SDK_DIR.name


def sanitize_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              timeout=30, cwd=str(cwd) if cwd else None,
                              env=sanitize_env())
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git"], 127, "", "git not found")


def main() -> int:
    ap = argparse.ArgumentParser(description="Install/remove SDK pre-commit hook")
    ap.add_argument("--repo", default=None, help="repo root (default: git rev-parse from this dir)")
    ap.add_argument("--remove", action="store_true", help="uninstall the hook")
    ap.add_argument("--force", action="store_true", help="overwrite a foreign hook")
    ap.add_argument("--dry-run", action="store_true", help="print plan only")
    args = ap.parse_args()

    if args.repo:
        root = Path(args.repo)
    else:
        res = git("-C", str(SCRIPT_DIR.parent), "rev-parse", "--show-toplevel")
        if res.returncode != 0:
            print(f"[fatal] not in a git repo: {res.stderr.strip() or 'git error'}", file=sys.stderr)
            return 2
        root = Path(res.stdout.strip())

    # F2: SDK relpath derived at install time (renamed-dir safe)
    rel = resolve_sdk_relpath(root)
    # Hook body embeds the CURRENT interpreter's absolute path (machine-local hook
    # file, never committed — safe) so git runs the gate even when `python` is not
    # on PATH.
    # F-56 (v2.10.5): hook exec path must be ABSOLUTE, not repo-relative; a relative
    # path breaks in any linked worktree (worktree root != repo root): the gate fails
    # closed with "No such file or directory" and blocks every commit there.
    sdk_gate = (SDK_DIR / "scripts" / "git-pre-commit.py").resolve()
    hook_body = f"""#!/bin/sh
# SDK pre-commit gate (installed by user-vibe-coding-sdk-moe/scripts/install-hooks.py, ref-23)
# Gates: changed SDK scripts -> robustness subset; data files -> JSON/golden; new SDK files -> privacy-scan.
exec "{sys.executable}" "{sdk_gate.as_posix()}" "$@"
"""

    hook = root / ".git" / "hooks" / "pre-commit"
    if args.remove:
        if hook.exists():
            if args.dry_run:
                print(f"[plan] remove {hook}")
                return 0
            hook.unlink()
            print(f"[ok] removed {hook}")
        else:
            print("[ok] no hook to remove")
        return 0

    if hook.exists():
        existing = hook.read_text(encoding="utf-8", errors="replace")
        if existing == hook_body:
            print("[ok] already installed (idempotent) — nothing to do")
            return 0
        if "git-pre-commit.py" in existing:
            # our own hook but outdated (e.g. interpreter path / SDK relpath changed)
            # — upgrade silently
            if args.dry_run:
                print(f"[plan] upgrade hook at {hook}")
                return 0
            hook.write_text(hook_body, encoding="utf-8")
            print(f"[ok] upgraded hook at {hook} (SDK exec: {rel}/scripts/git-pre-commit.py)")
            return 0
        if not args.force:
            print("[fatal] foreign hook present — re-run with --force to overwrite", file=sys.stderr)
            return 1

    if args.dry_run:
        print(f"[plan] install hook at {hook} (SDK relpath: {rel})")
        return 0

    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(hook_body, encoding="utf-8")
    print(f"[ok] installed {hook} (SDK exec: {rel}/scripts/git-pre-commit.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
