#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flaky-check.py — flaky 测试判别器（T-20 / F-31，v2.9.0）

Why: verification-kernel §B.10 —— **单次失败绝不足以修改应用代码**。此前 SDK 对
间歇性失败零判别（全库 grep flaky = 0）：一次失败即触发修复环 → 白耗修复预算
（max_repair_attempts=3 会被无效消耗）且可能引入错误改动。agentic-cicd §8.4 给出
确定性判别规则，本脚本是它的最小 stdlib 实现。

Classification (deterministic, fail-closed):
  REAL              所有 N 次运行全部失败 —— 可稳定复现，进修复环（ref-18）
  FLAKY             通过/失败混合 且 N >= 5（agentic-cicd §8.4 隔离门槛：
                    >=5 次运行且变率 >=20%）→ 建议 quarantine（**永不删除**）
  INFRA             混合结果中失败运行全部带基础设施指纹（超时/网络/exit 124）
                    → RETRY（配 ref-22 重试预算）
  NOT_REPRODUCIBLE  所有 N 次全部通过 —— 复现失败，疑似环境差异或已自愈；
                    fail-closed：按 UNKNOWN 处置，**不得据此跳过验证**
  UNKNOWN           混合但 N < 5（样本不足）→ **fail-closed 视同 REAL**，
                    建议加大 --runs 复跑

Design rules:
  * stdlib only · 零 LLM · 判定只是事实分类，进修复/quarantine 的决策留 agent。
  * flaky_probability = 2*min(fail_rate, 1-fail_rate)（混合时 0.5/0.5 → 1.0，
    单边趋满 → 0；确定性代理指标，非二项检验——见 ENGINEERING 契约注）。
  * Exit 0 = 分类完成（含 REAL）；Exit 2 = 用法错误（runs<2 / 无命令 / cwd 不存在）。

Usage:
  python flaky-check.py --runs 5 --cwd . --cmd pytest -q tests/test_x.py
  python flaky-check.py --runs 5 --cmd python tests/test_x.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "flaky-check.v1"

FLAKY_MIN_RUNS = 5          # agentic-cicd §8.4：FLAKY 判定门槛（隔离需 >=5 次 & >=20% 变率）
INFRA_FINGERPRINT = re.compile(
    r"timed out|timeout|TimeoutExpired|connection (reset|refused|error)|getaddrinfo"
    r"|ECONNRESET|ETIMEDOUT|HTTP 5\d\d|exit code (124|137)|killed", re.I)
CAUSE_SIGNALS = [
    ("network_timing", re.compile(r"connection|network|getaddrinfo|ECONN|ETIMEDOUT", re.I)),
    ("timeout_sensitive", re.compile(r"timed out|timeout|deadline", re.I)),
    ("shared_state", re.compile(r"already exists|in use|locked|address already", re.I)),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run_once(cmd: list, cwd: str | None, timeout: int, tail_lines: int) -> dict:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
        out = (r.stdout or "") + (r.stderr or "")
        return {"exit_code": r.returncode, "ok": r.returncode == 0,
                "timed_out": False, "tail": [ln for ln in out.splitlines() if ln.strip()][-tail_lines:]}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "ok": False, "timed_out": True, "tail": ["[timeout] exceeded --timeout"]}
    except FileNotFoundError as e:
        return {"exit_code": 127, "ok": False, "timed_out": False,
                "tail": [f"[fatal] command not found: {e}"]}


def classify(results: list[dict], runs: int) -> dict:
    fails = [r for r in results if not r["ok"]]
    passes = runs - len(fails)
    fail_rate = len(fails) / runs if runs else 0.0

    def causes() -> list[str]:
        blob = "\n".join("\n".join(r["tail"]) for r in fails)
        found = [name for name, pat in CAUSE_SIGNALS if pat.search(blob)]
        return found or ["unknown"]

    if not fails:
        return {"verdict": "NOT_REPRODUCIBLE", "flaky_probability": 0.0,
                "recommended_action": "TREAT_AS_UNKNOWN",
                "note": (f"failed originally but passed {runs}/{runs} now — fail-closed: "
                         "do NOT skip verification; rerun with more runs or diff the environment")}
    if not passes:
        return {"verdict": "REAL", "flaky_probability": 0.0,
                "recommended_action": "REPAIR",
                "note": f"deterministic reproduction ({runs}/{runs} failed)"}
    # 混合结果
    all_infra = all(r["timed_out"] or INFRA_FINGERPRINT.search("\n".join(r["tail"]))
                    for r in fails)
    if all_infra:
        return {"verdict": "INFRA", "flaky_probability": round(2 * min(fail_rate, 1 - fail_rate), 2),
                "recommended_action": "RETRY",
                "note": "every failing run carries an infra fingerprint (timeout/network) — retry within ref-22 budget"}
    if runs >= FLAKY_MIN_RUNS:
        return {"verdict": "FLAKY", "flaky_probability": round(2 * min(fail_rate, 1 - fail_rate), 2),
                "suspected_causes": causes(), "recommended_action": "QUARANTINE",
                "note": (f"variance across {runs} identical runs — quarantine (never delete, "
                         "never silently skip); file a tracking item")}
    return {"verdict": "UNKNOWN", "flaky_probability": None,
            "suspected_causes": causes(), "recommended_action": "TREAT_AS_REAL",
            "note": (f"mixed outcome but runs={runs} < {FLAKY_MIN_RUNS} — insufficient evidence, "
                     "fail-closed: treat as REAL and rerun with more runs")}


def main() -> int:
    ap = argparse.ArgumentParser(description="Flaky test discriminator (T-20, F-31)")
    ap.add_argument("--cmd", nargs=argparse.REMAINDER, default=None,
                    help="command to rerun (put it LAST, e.g. --cmd pytest -q tests/test_x.py)")
    ap.add_argument("--runs", type=int, default=3, help="rerun count (FLAKY verdict needs >=5)")
    ap.add_argument("--timeout", type=int, default=300, help="per-run timeout seconds")
    ap.add_argument("--cwd", default=None, help="working dir for the command")
    ap.add_argument("--tail", type=int, default=6, help="bounded tail lines kept per run")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    args = ap.parse_args()

    if not args.cmd:
        print("[fatal] --cmd required (put the command last)", file=sys.stderr)
        return 2
    if args.runs < 2:
        print(f"[fatal] --runs must be >= 2 (got {args.runs}) — a single rerun proves nothing", file=sys.stderr)
        return 2
    if args.cwd and not Path(args.cwd).is_dir():
        print(f"[fatal] --cwd not a directory: {args.cwd}", file=sys.stderr)
        return 2

    results = [run_once(args.cmd, args.cwd, args.timeout, args.tail) for _ in range(args.runs)]
    verdict = classify(results, args.runs)

    report = {
        "schema": SCHEMA,
        "time": now_iso(),
        "cmd": args.cmd,
        "runs": args.runs,
        "pass_count": sum(1 for r in results if r["ok"]),
        "fail_count": sum(1 for r in results if not r["ok"]),
        "flaky_min_runs": FLAKY_MIN_RUNS,
        **verdict,
        "runs_detail": results,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"== flaky-check: {report['verdict']} "
              f"({report['pass_count']}/{args.runs} passed, p={report['flaky_probability']}) ==")
        print(f"  action: {report['recommended_action']}")
        print(f"  note:   {report['note']}")
        if report.get("suspected_causes"):
            print(f"  causes: {', '.join(report['suspected_causes'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
