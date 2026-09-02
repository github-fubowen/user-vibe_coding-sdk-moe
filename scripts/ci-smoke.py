#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ci-smoke.py — 定时冒烟（评估报告 P2-1，ref-23）

One command that runs the FULL deterministic regression stack for the SDK and
writes a dated summary. Intended to run on a schedule (weekly automation) and
before/after any release. Zero-LLM, offline.

Steps (cheapest-first — verification-kernel §B.3 ordering):
  0. version-check (T-16)             — version strings + CHANGELOG order (F-26 gate)
  1. robustness-suite (full, 51+ cases)
  2. golden-run --validate-set (v2, v3)   — accept-rule pre-check (zero LLM)
  3. golden-run --offline v3              — 32/32 structural judging (zero LLM)
  4. privacy-scan SDK dir                 — leak gate for new content
Exit: 0 = all green / 2 = any failure. Summary JSON via --json or --report <path>.

Usage:
  python ci-smoke.py
  python ci-smoke.py --json
  python ci-smoke.py --report <REPORT_PATH>/smoke-2026-08-26.json
  python ci-smoke.py --skip-privacy       # slow environments
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
SDK_DIR = SCRIPT_DIR.parent


def sanitize_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # sandbox shim (E1)
    return env


def run(cmd: list, timeout: int = 600) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=sanitize_env(), stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 127, f"{type(e).__name__}: {e}"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK scheduled smoke test (robustness+golden+privacy)")
    ap.add_argument("--json", action="store_true", help="summary JSON to stdout")
    ap.add_argument("--report", default=None, help="write summary JSON to a dated file")
    ap.add_argument("--skip-privacy", action="store_true", help="skip privacy-scan step")
    args = ap.parse_args()

    def echo(msg: str) -> None:
        """Progress line: stderr when --json (stdout stays pure JSON), else stdout."""
        print(msg, file=sys.stderr if args.json else sys.stdout, flush=True)

    steps = [
        # T-16（F-26）：最便宜的闸先跑 —— 版本串失配 / CHANGELOG 顺序倒置秒级检出，
        # 避免后面的 4 分钟全量套件跑完才发现红灯（verification-kernel cheapest-first）。
        ("version-check", [sys.executable, str(SCRIPT_DIR / "version-check.py"), "--json"], 60),
        # v2.10.1 (F-43 治本): sdk_tools 在 toolstack.json 里无自动化维护
        # （toolstack-pipeline 只管 refs/provider_health），6 个脚本曾静默漏登记。
        # 静态自检秒级检出：frontmatter / refs / 脚本存在性 / toolstack 完整性。
        ("selfcheck-static", [sys.executable, str(SCRIPT_DIR / "selfcheck-static.py"), "--quiet"], 60),
        ("robustness-suite", [sys.executable, str(SCRIPT_DIR / "robustness-suite.py"), "--json"], 600),
        ("golden v2 validate", [sys.executable, str(SCRIPT_DIR / "golden-run.py"),
                                "--set", str(SCRIPT_DIR / "data" / "golden-set-v2.json"), "--validate-set", "--json"], 120),
        ("golden v3 validate", [sys.executable, str(SCRIPT_DIR / "golden-run.py"),
                                "--set", str(SCRIPT_DIR / "data" / "golden-set-v3.json"), "--validate-set", "--json"], 120),
        ("golden v3 offline", [sys.executable, str(SCRIPT_DIR / "golden-run.py"),
                               "--offline", "--set", str(SCRIPT_DIR / "data" / "golden-set-v3.json"), "--json"], 120),
    ]
    if not args.skip_privacy:
        steps.append(("privacy-scan", [sys.executable, str(SCRIPT_DIR / "privacy-scan.py"),
                                       str(SDK_DIR), "--json"], 180))

    results = []
    for name, cmd, timeout in steps:
        code, out = run(cmd, timeout=timeout)
        ok = code == 0
        # extract a compact verdict line from JSON payloads
        detail = ""
        try:
            data = json.loads(out[out.index("{"):])
            if "pass_rate" in data:
                detail = f"pass_rate={data['pass_rate']}"
                if not ok:  # F-55：失败时必须点名失败用例，否则红灯不可归因（v2.10.5 第 6 轮自检实录）
                    bad = [c.get("name", "?") for c in (data.get("results") or [])
                           if not c.get("ok", True)][:5]
                    if bad:
                        detail += " failed=" + "; ".join(bad)[:160]
            elif "valid" in data:
                detail = f"valid={data['valid']}"
            elif "changelog_top" in data:
                detail = (f"consistent={data.get('ok')} top={data.get('changelog_top')}"
                          + (f" problems={len(data['problems'])}" if data.get("problems") else ""))
            elif "clean" in data:
                detail = f"clean={data['clean']} findings={data.get('total')}"
        except (ValueError, IndexError, json.JSONDecodeError):
            detail = out.strip().splitlines()[-1][:80] if out.strip() else "no output"
        results.append({"step": name, "ok": ok, "exit": code, "detail": detail})
        # v2.10.1 (F-45): --json must emit parseable JSON on stdout only —
        # progress lines go to stderr, otherwise `ci-smoke --json | jq` breaks.
        echo(f"  [{'OK ' if ok else '!! '}] {name:<22} exit={code} {detail}")

    all_ok = all(r["ok"] for r in results)
    summary = {"schema": "ci-smoke.v1", "time": now_iso(), "all_ok": all_ok, "steps": results}

    if args.report:
        p = Path(args.report)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.json:
            print(f"  [report] {p}", file=sys.stderr, flush=True)
        else:
            print(f"  [report] {p}", flush=True)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    echo(f"ci-smoke: {'ALL GREEN' if all_ok else 'FAILURES — see steps above'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
