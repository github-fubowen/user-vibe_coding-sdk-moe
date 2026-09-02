#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe-tools.py — 会话级工具探测单次调用化 (v1.0, 2026-08-22)

Purpose: replace per-session 6+ individual `--version` probe tool-calls with ONE
deterministic call. Agent runs `python scripts/probe-tools.py --json` once per
session; output feeds §6 static tool routing (G3) — probe once, degrade silently.

Design rules (SDK §3/G1-G3, §6):
  * Single source of truth: toolstack.json local_tools manifest (same dir).
  * Python 3.9+ stdlib only. JSON out via --json. Exit 0 always (probe is never fatal).
  * Windows npm shim fallback (.cmd/.exe) — mirrors toolstack-pipeline.py.

Usage:
  python probe-tools.py                # human-readable probe table
  python probe-tools.py --json         # machine-readable JSON (for agent routing)
  python probe-tools.py --group llm    # filter by manifest group (optional)
Exit codes: 0 = done (probe results are informational; missing tools are not fatal).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST = SCRIPT_DIR / "toolstack.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "command not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def probe_one(name: str, cfg: dict) -> dict:
    cmd = list(cfg["cmd"])
    # Windows: npm shims are extensionless (`ocr`) — CreateProcess needs *.cmd/*.exe.
    candidates = [cmd]
    if os.name == "nt" and "." not in os.path.basename(cmd[0]):
        candidates.append([cmd[0] + ".cmd", *cmd[1:]])
        candidates.append([cmd[0] + ".exe", *cmd[1:]])
    res = None
    for cand in candidates:
        res = run(cand, timeout=int(cfg.get("timeout", 30)))
        if res.returncode != 127:
            break
    ok = res is not None and res.returncode == 0
    ver = None
    if ok and res.stdout.strip():
        if cfg.get("grep"):
            ver = next((ln.strip() for ln in res.stdout.splitlines() if cfg["grep"] in ln), None)
        if ver is None:
            ver = res.stdout.strip().splitlines()[0]
    return {
        "tool": name,
        "group": cfg.get("group", "misc"),
        "ok": ok,
        "version": ver,
        "exit_code": res.returncode if res else None,
        "note": cfg.get("note", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK session tool probe (one call, all tools)")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    ap.add_argument("--group", default=None, help="filter by manifest group (e.g. review/debug/llm)")
    args = ap.parse_args()

    if not MANIFEST.exists():
        log(json.dumps({"error": f"manifest not found: {MANIFEST}"}))
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    local_tools: dict = manifest.get("local_tools", {})
    rows = [probe_one(n, c) for n, c in local_tools.items()
            if not args.group or c.get("group") == args.group]

    if args.json:
        print(json.dumps({"time": now_iso(), "tools": rows}, ensure_ascii=False, indent=2))
    else:
        log("== Local tool probes ==")
        for r in rows:
            v = r["version"] or ("—" if r["ok"] else "MISSING")
            log(f"  {'OK ' if r['ok'] else '!! '} {r['tool']:<28} [{r['group']:<8}] {v}")
        missing = [r["tool"] for r in rows if not r["ok"]]
        if missing:
            log(f"  -> missing (expected or degraded): {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
