#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch-gate.py — 补丁规模预算闸（T-23 / F-29，v2.10.0）

Why: verification-kernel §I 的 8 项修复预算中，SDK 只落了「次数」（max_repair_attempts=3）。
缺规模预算 = 单次修复可以产出 20 文件 / 500 行 / 动依赖清单的超大补丁而不触任何闸
—— diff-risk 是**评分**（>0.7 转人工建议），不是**预算闸**（硬拒绝），两者不可互替。

Budgets (defaults from kernel §I, configurable):
  max_files        单补丁触碰文件数（默认 5）
  max_lines        单补丁变更行数 added+deleted（默认 300）
  max_dep_changes  依赖清单文件数（requirements*/pyproject/package.json/lock…，默认 1；
                   超限须升级 ref-22 L3+ —— 依赖变更是行为变更，不是"顺手改"）

Input (any one):
  --numstat-file <file>   `git diff --numstat` 输出（首选：added/deleted 精确）
  --diff-file <file>      unified diff（自行统计 +/- 行与文件）
  --stat "<files>,<added>+<deleted>"   手工声明，如 "12,340"（测试/无 git 环境）

Verdict: exit 0 = 预算内；exit 2 = 超限（fail-closed），输出的 exceeded 预算与
recommended_action=ESCALATED 供 ref-22 阶梯消费。

Usage:
  git diff --numstat > n.txt && python patch-gate.py --numstat-file n.txt --json
  python patch-gate.py --diff-file p.patch --max-files 8
  python patch-gate.py --stat "7,320" --json
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from _common import (EXIT_OK, EXIT_ERROR, EXIT_GATE, emit_json,
                   now_iso, schema, build_parser, add_json_flag)

SCHEMA = schema("patch-gate")

# cicd §15（P3 清偿 v2.10.6）：硬闸参数策略版本钉。预算参数（files/lines/deps）是
# 策略面而非实现细节 —— 变更默认预算 = 变策略 = 必须显式 bump 本常量并在 CHANGELOG
# 记录。调用方可传 --policy-version 校验自己钉住的版本（不匹配 → fail-closed exit 2）。
POLICY_VERSION = "gate-policy.v1"

# 依赖清单文件（T-23：dependency changes 预算的判定面）
DEP_MANIFEST_RE = re.compile(
    r"(^|/)(requirements[\w.-]*\.txt|pyproject\.toml|uv\.lock|poetry\.lock"
    r"|package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock"
    r"|Cargo\.toml|Cargo\.lock|go\.mod|go\.sum|Pipfile.*|Gemfile.*)$", re.I)



def parse_numstat(text: str) -> tuple[list[str], int]:
    files: list[str] = []
    lines = 0
    for idx, ln in enumerate(text.splitlines(), 1):
        parts = ln.split("\t")
        if len(parts) < 3:
            continue
        add, dele, path = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not path or path.startswith("("):  # numstat 摘要尾行
            continue
        try:  # F-53：畸形行不得以裸 traceback 崩溃——报行号 + 干净 exit 2（fail-closed）
            n_add = 0 if add == "-" else int(add)
            n_del = 0 if dele == "-" else int(dele)
        except ValueError:
            raise ValueError(
                f"malformed numstat line {idx} (expected 'added<TAB>deleted<TAB>path'): {ln!r}")
        files.append(path)
        lines += n_add + n_del
    return files, lines


def parse_unified_diff(text: str) -> tuple[list[str], int]:
    files: list[str] = []
    lines = 0
    for ln in text.splitlines():
        if ln.startswith("+++") or ln.startswith("---") or ln.startswith("Index: "):
            m = re.search(r"\s(\S+)$", ln)
            if m and m.group(1) not in ("/dev/null",):
                p = m.group(1).removeprefix("a/").removeprefix("b/")
                if p not in files:
                    files.append(p)
        elif ln.startswith("+") or ln.startswith("-"):
            lines += 1
        elif ln.startswith("@@"):
            lines += 1  # hunk 头计入变更噪声（保守）
    return files, lines


def gate(files: list[str], changed_lines: int, max_files: int, max_lines: int,
         max_deps: int) -> dict:
    dep_files = [f for f in files if DEP_MANIFEST_RE.search(f.replace("\\", "/"))]
    exceeded = []
    if len(files) > max_files:
        exceeded.append(f"files {len(files)} > {max_files}")
    if changed_lines > max_lines:
        exceeded.append(f"changed lines {changed_lines} > {max_lines}")
    if len(dep_files) > max_deps:
        exceeded.append(f"dependency manifests {len(dep_files)} > {max_deps}: {dep_files}")
    return {
        "schema": SCHEMA, "time": now_iso(), "policy_version": POLICY_VERSION,
        "files": len(files), "changed_lines": changed_lines,
        "dep_manifests": dep_files,
        "budget": {"max_files": max_files, "max_lines": max_lines, "max_dep_changes": max_deps},
        "ok": not exceeded,
        "exceeded": exceeded,
        "recommended_action": "ESCALATED" if exceeded else None,
        "note": ("patch exceeds budget — split the patch or escalate (ref-22 §I / L3+); "
                 "do NOT auto-proceed" if exceeded
                 else "patch within budget (verification-kernel §I)"),
    }


def main() -> int:
    ap = build_parser("Patch budget gate (T-23, F-29; kernel §I)")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--numstat-file", default=None, help="`git diff --numstat` output file")
    src.add_argument("--diff-file", default=None, help="unified diff file")
    src.add_argument("--stat", default=None, help='manual "<files>,<added+deleted>" e.g. "7,320"')
    ap.add_argument("--max-files", type=int, default=5)
    ap.add_argument("--max-lines", type=int, default=300)
    ap.add_argument("--max-deps", type=int, default=1)
    ap.add_argument("--policy-version", default=None,
                    help="caller-pinned gate policy version (cicd §15); mismatch → exit 2")
    add_json_flag(ap)
    args = ap.parse_args()

    if args.policy_version and args.policy_version != POLICY_VERSION:  # §15 策略版本钉
        print(f"[fatal] policy version mismatch: caller pinned {args.policy_version!r}, "
              f"gate enforces {POLICY_VERSION!r} — budget params are policy, bump the "
              f"POLICY_VERSION constant (with CHANGELOG) if the change is intended",
              file=sys.stderr)
        return EXIT_GATE

    files: list[str] = []
    changed = 0
    if args.numstat_file:
        p = Path(args.numstat_file)
        if not p.exists():
            print(f"[fatal] numstat file not found: {p}", file=sys.stderr)
            return EXIT_GATE
        try:
            files, changed = parse_numstat(p.read_text(encoding="utf-8", errors="replace"))
        except ValueError as e:  # F-53：畸形 numstat → 干净拦截（exit 2），非裸 traceback
            print(f"[fatal] patch-gate: {e}", file=sys.stderr)
            return EXIT_GATE
    elif args.diff_file:
        p = Path(args.diff_file)
        if not p.exists():
            print(f"[fatal] diff file not found: {p}", file=sys.stderr)
            return EXIT_GATE
        files, changed = parse_unified_diff(p.read_text(encoding="utf-8", errors="replace"))
    elif args.stat:
        m = re.fullmatch(r"\s*(\d+)\s*,\s*(\d+)\s*", args.stat)
        if not m:
            print('[fatal] --stat format: "<files>,<added+deleted>" e.g. "7,320"', file=sys.stderr)
            return EXIT_GATE
        files, changed = [], int(m.group(2))
        rep = gate(files, changed, args.max_files, args.max_lines, args.max_deps)
        rep["files_declared"] = int(m.group(1))
        if rep["files_declared"] > args.max_files:
            rep["ok"] = False
            rep["exceeded"].append(f"files {rep['files_declared']} > {args.max_files}")
            rep["recommended_action"] = "ESCALATED"
        _emit(rep, args)
        return EXIT_OK if rep["ok"] else EXIT_GATE
    else:
        print("[fatal] no diff source: use --numstat-file / --diff-file / --stat", file=sys.stderr)
        return EXIT_GATE

    rep = gate(files, changed, args.max_files, args.max_lines, args.max_deps)
    _emit(rep, args)
    return EXIT_OK if rep["ok"] else EXIT_GATE


def _emit(rep: dict, args) -> None:
    if args.json:
        emit_json(rep)
    else:
        mark = "OK " if rep["ok"] else "!! "
        print(f"== patch-gate: {mark}files={rep['files']} lines={rep['changed_lines']} "
              f"deps={len(rep['dep_manifests'])} policy={rep['policy_version']} ==")
        for e in rep["exceeded"]:
            print(f"  [exceeded] {e}", file=sys.stderr)
        print(f"  budget: {rep['budget']}")


if __name__ == "__main__":
    sys.exit(main())
