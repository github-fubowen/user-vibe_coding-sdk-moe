#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
env-snapshot.py — Debug 环境快照一次成型 (v1.0, 2026-08-22)

Purpose: replace the LLM "let me check the environment" multi-turn chain (ref-18
deterministic-first, step "差分/环境对比") with ONE deterministic snapshot:
tool versions, git state, selected env vars, recent log tail, config file digest.
The snapshot is a bounded JSON the agent consumes in one read.

Design rules (SDK §3/G-gates, ref-18 §2):
  * Python 3.9+ stdlib only. JSON out. Read-only (never modifies anything).
  * Bounded output: log tail default 20 lines; env vars whitelist-filtered.
  * The 127 exit-code convention is NOT used here — snapshot is informational (0).

Usage:
  python env-snapshot.py                        # human-readable
  python env-snapshot.py --json                 # machine-readable
  python env-snapshot.py --log app.log --tail 30
  python env-snapshot.py --env PATH,PYTHONPATH,UV_CACHE_DIR --cwd /path
Exit codes: 0 always (informational).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SAFE_ENV = ["PATH", "PYTHONPATH", "UV_CACHE_DIR", "UV_TOOL_DIR", "HERMES_HOME",
            "OLLAMA_HOST", "NODE_PATH", "PNPM_HOME", "HOME", "USERPROFILE"]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run(cmd: list[str], timeout: int = 15) -> str:
    # Windows: npm shim is extensionless — CreateProcess needs .cmd/.exe.
    candidates = [cmd]
    if os.name == "nt" and "." not in os.path.basename(cmd[0]):
        candidates += [[cmd[0] + ".cmd", *cmd[1:]], [cmd[0] + ".exe", *cmd[1:]]]
    for cand in candidates:
        try:
            res = subprocess.run(cand, capture_output=True, text=True, timeout=timeout)
        except Exception:
            continue
        if res.returncode == 0 and (res.stdout or res.stderr):
            return (res.stdout or res.stderr).strip().splitlines()[0]
    return ""


def file_digest(path: Path, n: int = 64) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()[:n]
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic environment snapshot for Debug")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--cwd", default=".", help="base dir for git state / config files")
    ap.add_argument("--log", default=None, help="log file to tail (--tail lines)")
    ap.add_argument("--tail", type=int, default=20, help="log tail lines (bounded, G1)")
    ap.add_argument("--env", default=None, help="comma-separated env vars (default: SAFE_ENV whitelist)")
    ap.add_argument("--path-limit", type=int, default=10, help="cap PATH entries in snapshot (G1 bounded output)")
    ap.add_argument("--configs", default="", help="comma-separated config paths to digest (relative to --cwd)")
    args = ap.parse_args()

    cwd = Path(args.cwd).resolve()
    env_names = [e.strip() for e in (args.env or ",".join(SAFE_ENV)).split(",") if e.strip()]

    env_out = {}
    for k in env_names:
        v = os.environ.get(k)
        if not v:
            continue
        if k == "PATH":
            entries = [e for e in v.split(os.pathsep) if e]
            truncated = entries[: args.path_limit]
            env_out[k] = {"total": len(entries), "entries": truncated,
                          "truncated": len(entries) > args.path_limit}
        else:
            env_out[k] = v

    snap = {
        "time": now_iso(),
        "host": {"platform": platform.platform(), "python": sys.version.split()[0],
                 "python_exe": sys.executable},
        "tools": {
            "git": run(["git", "--version"]),
            "node": run(["node", "--version"]),
            "npm": run(["npm", "--version"]),
            "uv": run(["uv", "--version"]),
            "gh": run(["gh", "--version"]),
        },
        "env": env_out,
        "cwd": str(cwd),
        "git": {
            "root": run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"]),
            "branch": run(["git", "-C", str(cwd), "branch", "--show-current"]),
            "head": run(["git", "-C", str(cwd), "rev-parse", "--short", "HEAD"]),
            "status_short": run(["git", "-C", str(cwd), "status", "--short"]),
        },
    }

    if args.log:
        log_path = Path(args.log)
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            snap["log"] = {"path": str(log_path), "tail": lines[-args.tail:]}
        else:
            snap["log"] = {"path": str(log_path), "tail": [], "note": "not found"}

    if args.configs:
        snap["configs"] = {}
        for rel in [c.strip() for c in args.configs.split(",") if c.strip()]:
            p = cwd / rel
            snap["configs"][rel] = {"exists": p.exists(),
                                    "sha256_64": file_digest(p) if p.exists() else None}

    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
    else:
        print(f"== env-snapshot @ {snap['time']} (cwd: {cwd}) ==")
        print(f"  host: {snap['host']['platform']} | python {snap['host']['python']}")
        print(f"  git: {snap['git']['branch'] or '?'} @ {snap['git']['head'] or '?'} root={snap['git']['root'] or '?'}")
        print(f"  tools: node={snap['tools']['node'] or 'MISSING'} npm={snap['tools']['npm'] or 'MISSING'} "
              f"uv={snap['tools']['uv'] or 'MISSING'} gh={snap['tools']['gh'] or 'MISSING'}")
        if snap.get("log"):
            print(f"  log tail ({len(snap['log'].get('tail', []))} lines): {snap['log'].get('path')}")
        if snap.get("configs"):
            for rel, c in snap["configs"].items():
                print(f"  cfg {rel}: {'sha256=' + c['sha256_64'] if c['exists'] else 'MISSING'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
