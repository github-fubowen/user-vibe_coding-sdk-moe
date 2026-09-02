#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ci-fail-analyze.py — CI 失败分析器 (v1.0, 2026-08-28, C1-4)

Purpose: implement GH 方案 §11 Failure Analyzer as a deterministic zero-LLM
script: parse a GitHub Actions failure log + optional git diff to emit a
diagnostic.v1 record that feeds the ref-18 hypothesis loop (Debug mode) and
the ref-22 repair escalation ladder. The agent consumes the diagnostic; this
script only classifies FACTS.

Failure-type taxonomy (deterministic regex, first match wins):
  permission     — permission denied / EACCES / EPERM / 403（v2.8.0 T-09，AgentOS #8）
  dependency     — "Could not find a version" / ERESOLVE / peer dep（v2.8.0 T-09）
  unit_failure   — pytest/unittest FAILED / AssertionError / "1 failed"
  timeout        — "timed out" / "Timeout" / "The operation was canceled"
  assertion      — jest/vitest 风格 expect(received) / Expected:...Received: / ✕
                   （v2.8.0 T-09；置于 unit_failure 之后 —— pytest 的 AssertionError
                   仍归 unit_failure，此处只接非 pytest 断言上下文）
  command_missing— "command not found" / "No such file or directory" / "not found:"
  install_error  — pip/npm/apt install failure ("error: " ... "install")
  generic        — fallback (log present but unclassified)

Ordering rationale (v2.6.1 教训：顺序敏感防吞并):
  permission 最先（权限错误常混在 install/step 输出里，应按根因归类）；
  dependency 先于 command_missing（"Could not find a version" 不含 "not found:"
  但语义是依赖解析，不是命令缺失）；assertion 在 unit_failure 之后防吞并。

Design rules (SDK §3/G-gates, §10.9):
  * Python 3.9+ stdlib only. JSON out. Exit 0 = ok / 2 = error (missing log).
  * Zero LLM — classification is regex over the log; confidence is a fixed
    heuristic per class, never fabricated from content.
  * --git-dir optional: affected_files from `git diff --name-only` (uncommitted
    changes in the runner workspace at failure time).
  * Output schema: diagnostic.v1 (aligns verify-runner --json).

Usage:
  python ci-fail-analyze.py --log actions-failure.log
  python ci-fail-analyze.py --log actions-failure.log --git-dir . --json
  python ci-fail-analyze.py --log f.log --results-json results.json --json  # vk B.6 per-test
  python ci-fail-analyze.py --log missing.log      # exit 2: not found
Exit codes: 0 = diagnostic emitted / 2 = error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "diagnostic.v1"

# T-19（v2.9.0, F-30）：origin class —— verification-kernel §H：**由 origin 而非
# leaf 决定下一步动作**。"一切皆代码缺陷" 是 agentic-cicd §1 明列要避免的十大
# 错误之一：Dependency Failure + Infra Bug（registry 抖动）应 RETRY，却被当
# Code Bug 送进修复环 = 白耗修复预算 + 可能引入错误改动。
#   origin ∈ code | test | dependency | infra | environment | flaky | unknown
# flaky 不由本脚本产生（单条日志无法判定，归 T-20 flaky-check.py 的重跑统计）。
ORIGIN_BY_TYPE = {
    "syntax_error": "code",
    "unit_failure": "code",
    "assertion": "code",
    "dependency": "dependency",
    "install_error": "dependency",
    "timeout": "infra",
    "permission": "environment",
    "command_missing": "environment",
    "generic": "unknown",
}

# 日志级信号（优先于静态映射，首个命中生效）：
#   infra        —— 依赖/安装类失败若带 registry/网络指纹 → 基础设施抖动，RETRY 不 REPAIR
#   test         —— 失败出自测试自身装置（fixture 未找到 / setup 报错 / DID NOT RAISE）
#                 → 修测试而非改产品代码
ORIGIN_SIGNALS: list[tuple[str, re.Pattern]] = [
    ("infra", re.compile(r"ConnectionError|ECONNREFUSED|ETIMEDOUT|getaddrinfo failed"
                         r"|connection reset|HTTP 5\d\d|registry .*timed out", re.I)),
    ("test", re.compile(r"fixture .{0,40}not found|error in .{0,40}(setup|teardown)"
                        r"|DID NOT RAISE", re.I)),
    ("environment", re.compile(r"environment variable .{0,40}not (set|defined)"
                               r"|missing (required )?env(ironment)? var", re.I)),
]

# origin → 推荐动作（喂 ref-18 假设环 / ref-22 升级阶梯；判定仍留 agent）
ACTION_BY_ORIGIN = {
    "code": "REPAIR",
    "test": "REPAIR_TEST",
    "dependency": "RETRY_THEN_REPAIR",
    "infra": "RETRY",
    "environment": "FIX_ENV",
    "flaky": "QUARANTINE",
    "unknown": "DIAGNOSE",
}

RULES: list[tuple[str, re.Pattern, str, float, str, str]] = [
    # (failure_type, regex, repair_strategy, confidence, risk)
    # 顺序敏感：unit_failure 的 FAILED 已改为大小写敏感（pytest 输出大写 FAILED；
    # 小写 "failed" 出现在 install/npm 错误里，不能被 unit_failure 抢先吃掉），
    # 且移除 `pytest.*failed`（跨词过度匹配，如 "pytest (build failed)" 会被误吞；
    # pytest 失败标记已由 FAILED + "1 failed" 摘要覆盖）。
    # v2.8.0 (T-09, AgentOS #8)：新增 permission / dependency / assertion 三类
    # （自查报告所列 "timeout" 实际 v1.0 已存在，不重复添加）。
    ("permission",
     re.compile(r"permission denied|EACCES|EPERM|Access is denied|403 Forbidden"
                r"|Operation not permitted", re.I),
     "check file/dir permissions and runner identity/token scope; avoid sudo; "
     "least-privilege fix (ref-17 risk-tier)",
     0.85, "medium"),
    ("dependency",
     re.compile(r"Could not find a version|ERESOLVE|peer dep|no matching distribution"
                r"|unable to resolve .+dependency|dependency resolution", re.I),
     "pin resolvable versions / refresh lockfile; check registry index and "
     "version constraints (toolstack.json)",
     0.8, "medium"),
    ("unit_failure",
     re.compile(r"FAILED|AssertionError|assert .+ ==|1 failed"),
     "inspect failing test output; fix assertion or code; re-run targeted test",
     0.9, "low"),
    ("timeout",
     re.compile(r"timed out|Timeout|operation was canceled|job.*canceled", re.I),
     "raise step timeout / split job; check for hanging subprocess (ref-22 retry budget)",
     0.85, "medium"),
    ("assertion",
     re.compile(r"expect\(received\)|Expected:.+Received:|Received:.+Expected:|✕"),
     "compare expected vs received values; fix the assertion or the producer; "
     "re-run the targeted test",
     0.75, "low"),
    ("command_missing",
     re.compile(r"command not found|No such file or directory|not found:|couldn't find", re.I),
     "add missing dependency / setup step; pin toolchain version (toolstack.json)",
     0.9, "low"),
    ("install_error",
     re.compile(r"error: .+install|Installation failed|pip .+ error|npm .+ error|npm ERR!", re.I),
     "fix dependency resolution / index URL; pin versions; clear caches",
     0.75, "medium"),
    ("syntax_error",
     re.compile(r"SyntaxError|NameError|ImportError|IndentationError", re.I),
     "fix syntax/import at the reported line; run lint gate locally first",
     0.9, "low"),
]


def _origin(ftype: str, log_text: str) -> str:
    """T-19: origin class = log-level signals first (first hit wins), else static map."""
    for origin, pat in ORIGIN_SIGNALS:
        if pat.search(log_text):
            return origin
    return ORIGIN_BY_TYPE.get(ftype, "unknown")


def analyze(log_text: str) -> dict:
    for ftype, pat, strategy, conf, risk in RULES:
        m = pat.search(log_text)
        if m:
            start = max(0, m.start() - 120)
            origin = _origin(ftype, log_text)
            return {"failure_type": ftype,
                    "origin": origin,
                    "recommended_action": ACTION_BY_ORIGIN.get(origin, "DIAGNOSE"),
                    "root_cause": log_text[start:m.end() + 120].strip()[:400],
                    "confidence": conf, "repair_strategy": strategy, "risk": risk}
    return {"failure_type": "generic",
            "origin": "unknown",
            "recommended_action": ACTION_BY_ORIGIN["unknown"],
            "root_cause": "(no known failure pattern matched)",
            "confidence": 0.4, "repair_strategy": "read log tail and classify manually",
            "risk": "medium"}


def affected_files(git_dir: str | None) -> list[str]:
    if not git_dir:
        return []
    try:
        r = subprocess.run(["git", "-C", git_dir, "diff", "--name-only"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return []
        return [ln for ln in r.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def per_test_results(path_str: str | None) -> tuple[list[dict], dict]:
    """vk B.6 (P3 清偿 v2.10.6): per-test structured fields from a test-results JSON.

    Accepts {"results": [...]} / {"cases": [...]} / {"rows": [...]} / a bare list;
    entries with ok/passed=False become per-test records {test_name, expected, actual}.
    Robustness discipline (F-53 pattern): malformed input raises, and main()
    turns it into a clean [fatal] + exit 2 — never a raw traceback.
    """
    if not path_str:
        return [], {"failed": 0, "total": 0}
    data = json.loads(Path(path_str).read_text(encoding="utf-8", errors="replace"))
    if isinstance(data, dict):
        entries = next((data[k] for k in ("results", "cases", "rows")
                        if isinstance(data.get(k), list)), [])
    elif isinstance(data, list):
        entries = data
    else:
        entries = []
    failed: list[dict] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if e.get("ok", e.get("passed", True)):
            continue
        exp, act = e.get("expected"), e.get("actual", e.get("exit"))
        if isinstance(exp, (list, dict)):
            exp = json.dumps(exp, ensure_ascii=False)
        if isinstance(act, (list, dict)):
            act = json.dumps(act, ensure_ascii=False)
        failed.append({"test_name": str(e.get("name") or e.get("id") or e.get("test") or "?"),
                       "expected": str(exp) if exp is not None else None,
                       "actual": str(act) if act is not None else None})
    return failed, {"failed": len(failed), "total": len(entries)}


def main() -> int:
    ap = argparse.ArgumentParser(description="CI failure log analyzer (GH 方案 §11)")
    ap.add_argument("--log", required=True, help="Actions failure log file path")
    ap.add_argument("--git-dir", default=None, help="repo dir for git diff affected_files")
    ap.add_argument("--results-json", default=None,
                    help="test-results JSON ({results|cases|rows} or list) — attach per-test "
                         "fields to the diagnostic (vk B.6)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"[fatal] log not found: {log_path}", file=sys.stderr)
        return 2
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[fatal] read error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    diag = analyze(text)
    diag.update({"schema": SCHEMA, "affected_files": affected_files(args.git_dir),
                 "source_log": str(log_path)})
    if args.results_json:  # vk B.6：per-test 结构化字段（畸形输入干净 exit 2，非 traceback）
        try:
            failed, summary = per_test_results(args.results_json)
        except Exception as e:
            print(f"[fatal] --results-json unreadable: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        diag["per_test"] = failed[:50]
        diag["per_test_summary"] = summary
        if failed:
            diag["failing_tests"] = [t["test_name"] for t in failed[:10]]
    if args.json:
        print(json.dumps(diag, ensure_ascii=False, indent=2))
    else:
        print(f"== ci-fail-analyze: {diag['failure_type']} "
              f"(origin={diag['origin']} -> {diag['recommended_action']}, "
              f"conf={diag['confidence']}, risk={diag['risk']}) ==")
        print(f"  root_cause: {diag['root_cause'][:160]}")
        print(f"  repair:     {diag['repair_strategy']}")
        if diag["affected_files"]:
            print(f"  files:      {', '.join(diag['affected_files'][:10])}")
        if diag.get("failing_tests"):
            print(f"  failing:    {'; '.join(diag['failing_tests'][:5])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
