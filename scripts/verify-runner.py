#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-runner.py — 修复/变更后的确定性验证闸 (v1.0, 2026-08-22)

Purpose: replace the LLM-narrated verify loop (§5.6 / ref-18 §4) with ONE
deterministic call that runs test/lint/build steps and reports pass/fail JSON.
Code execution is the ground truth; the agent only reads the verdict + bounded
diagnostic tails instead of narrating "now running tests... now checking...".

Design rules (SDK §3/G-gates, §5.6 verification five-state):
  * Config: verify.json in --config (default: ./verify.json) — {steps:[{name,cmd,timeout}]}
  * Python 3.9+ stdlib only. JSON out. Exit: 0 = all pass / 2 = any fail.
  * Output tails are BOUNDED (--tail 12 lines/step) — never dump full logs (G1).
  * Verification states are NOT judged here: script reports pass/fail facts;
    the five-state judgment (REGRESSION/UNKNOWN etc.) stays with the agent (ref-18).

Usage:
  python verify-runner.py --config verify.json            # human table
  python verify-runner.py --config verify.json --json     # machine-readable
  python verify-runner.py --config verify.json --tail 8   # bounded tails
  python verify-runner.py --config verify.json --cmd "pytest -q"  # single ad-hoc step
Exit codes: 0 = all steps passed / 2 = at least one step failed (or config missing).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run_step(name: str, cmd: list[str], timeout: int, tail: int, cwd: str | None) -> dict:
    t0 = datetime.now()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        res = subprocess.CompletedProcess(cmd, 127, "", "command not found")
    except subprocess.TimeoutExpired:
        res = subprocess.CompletedProcess(cmd, 124, "", "timeout")
    dur_ms = int((datetime.now() - t0).total_seconds() * 1000)
    out = (res.stdout or "").strip().splitlines()
    err = (res.stderr or "").strip().splitlines()
    combined = out + (["[stderr]"] + err if err else [])
    return {
        "name": name,
        "cmd": cmd,
        "ok": res.returncode == 0,
        "exit_code": res.returncode,
        "duration_ms": dur_ms,
        "tail": combined[-tail:],
    }


def load_config(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log(f"[fatal] invalid JSON in {path}")
        sys.exit(2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic verify gate (test/lint/build)")
    ap.add_argument("--config", default="verify.json", help="JSON config with steps")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    ap.add_argument("--tail", type=int, default=12, help="bounded tail lines per step")
    ap.add_argument("--cmd", nargs=argparse.REMAINDER, default=None, help="ad-hoc single step: --cmd pytest -q")
    ap.add_argument("--cwd", default=None, help="working dir for steps (default: config dir)")
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    cfg = load_config(cfg_path)
    steps = (cfg or {}).get("steps", [])
    if args.cmd:
        steps = [{"name": "adhoc", "cmd": args.cmd}]

    if not steps:
        reason = "config not found" if cfg is None else "no steps in config"
        log(f"[fatal] {reason}: {cfg_path} (use --cmd or add steps to config)")
        return 2

    cwd = args.cwd or (str(cfg_path.parent) if cfg_path.exists() else None)
    rows = [run_step(s.get("name", "step"), list(s["cmd"]), int(s.get("timeout", 120)), args.tail, cwd)
            for s in steps]
    all_ok = all(r["ok"] for r in rows)

    if args.json:
        report = {"time": now_iso(), "config": str(cfg_path), "all_ok": all_ok, "steps": rows}
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            mark = "OK " if r["ok"] else f"!! {r['exit_code']}"
            log(f"  {mark}  {r['name']:<24} {r['duration_ms']:>7}ms  {(' '.join(r['cmd']))[:60]}")
            for ln in r["tail"]:
                log(f"        | {ln[:120]}")
        log(f"Verdict: {'ALL PASS' if all_ok else 'FAILED — see exit codes above'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
