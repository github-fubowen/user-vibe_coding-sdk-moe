#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mutation-audit.py — 门禁变异测试审计（v2.10.3）

Why: blocking-coverage（selfcheck-static 第五项）只做**静态**检查——它证明"有一条用例断言
非零退出"，但证明不了"**如果闸坏了，那条用例真的会红**"。F-50 的教训正是：
用例名写 "budget exceeded" 却 expect 0，测试存在但**测错了方向**。

本脚本补上动态那一半：对门禁脚本注入定点变异（把"拦截"改成"放行"），跑对应 robustness
子集，看有没有用例失败：
  KILLED    = 至少一个用例变红  → 测试真的咬住了这个行为 ✅
  SURVIVED  = 全部用例仍绿      → 该行为无有效约束，测试空转 ❌
  STALE     = 变异锚点在源码里找不到了（代码重构后需更新本表）⚠️

Safety: 内存中备份**原始字节**，finally 里按字节恢复并校验 sha256 一致；锚点不存在只报
STALE 不改文件。**不可并发运行**（会临时改写 scripts/ 下的源码）。

Line endings (v2.10.3): 一律用 bytes 读写后再 decode/encode 做替换 —— 用 `read_text/write_text`
会触发 Python 文本模式的换行翻译（LF↔CRLF），把没参与变异的文件也改成 CRLF，
在 git 里表现为一堆无关 diff。变异审计必须**字节级无损**。

Usage:
  python scripts/mutation-audit.py                 # 跑全部变异
  python scripts/mutation-audit.py --json          # 机器可读
  python scripts/mutation-audit.py --only patch-gate.py
  python scripts/mutation-audit.py --dry-run       # 只校验锚点是否还有效，不改文件
Exit: 0 = 全部 KILLED / 2 = 存在 SURVIVED 或 STALE。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE = SCRIPT_DIR / "robustness-suite.py"
SCHEMA = "mutation-audit.v1"

# (script, anchor, replacement, 中文描述)
# 锚点必须是**决定性判断**所在那一行——变异的语义是"让这个闸永远放行"。
MUTATIONS: list[dict] = [
    {
        "script": "patch-gate.py",
        "anchor": '        "ok": not exceeded,',
        "replacement": '        "ok": True,',
        "desc": "补丁规模预算闸恒放行（超 files/lines/deps 也不拦）",
    },
    {
        "script": "privacy-scan.py",
        "anchor": "    return 0 if clean else 2",
        "replacement": "    return 0",
        "desc": "隐私泄漏闸恒放行（检出泄漏仍 exit 0）",
    },
    {
        "script": "version-check.py",
        "anchor": '    return 0 if rep["ok"] else 2',
        "replacement": "    return 0",
        "desc": "版本串/CHANGELOG 顺序闸恒放行",
    },
    {
        "script": "token-meter.py",
        "anchor": "    if budget_block and budget_block[\"exceeded\"]:\n        return 2",
        "replacement": "    if False:\n        return 2",
        "desc": "F-50 回归：预算闸退回永不拦截（原缺陷）",
    },
    {
        "script": "action-gate.py",
        "anchor": "    if tier >= 4:",
        "replacement": "    if False:",
        "desc": "tier-4 人工闸门失效（push 无需确认即放行）",
    },
    {
        "script": "selfcheck-static.py",
        "anchor": "    if unregistered:",
        "replacement": "    if False:",
        "desc": "F-43 回归：未登记脚本不再拦截",
    },
]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_subset(stem: str, timeout: int = 300) -> tuple[int, list[dict]]:
    """Run robustness-suite --only <stem>; returns (exit, failed-case list)."""
    try:
        r = subprocess.run([sys.executable, str(SUITE), "--only", stem, "--json"],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, [{"name": "<timeout>"}]
    try:
        data = json.loads(r.stdout[r.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return 127, [{"name": f"<unparseable output: {r.stdout[:120]}>"}]
    failed = [{"name": c.get("name"), "expected": c.get("expected"), "exit": c.get("exit")}
              for c in data.get("results", []) if not c.get("ok")]
    return r.returncode, failed


def audit(only: str | None = None, dry_run: bool = False,
          verbose: bool = True) -> tuple[list[dict], int]:
    rows: list[dict] = []
    for mut in MUTATIONS:
        if only and mut["script"] != only:
            continue
        path = SCRIPT_DIR / mut["script"]
        row = {"script": mut["script"], "desc": mut["desc"], "status": None,
               "killed_by": [], "note": None}
        if not path.exists():
            row["status"], row["note"] = "STALE", "script not found"
            rows.append(row)
            continue

        raw = path.read_bytes()
        original_sha = hashlib.sha256(raw).hexdigest()
        original = raw.decode("utf-8")
        if mut["anchor"] not in original:
            row["status"] = "STALE"
            row["note"] = ("mutation anchor not found in source — update MUTATIONS "
                           "(code was refactored)")
            rows.append(row)
            if verbose:
                print(f"  ??  {mut['script']:<24} STALE   {row['note']}", flush=True)
            continue

        if dry_run:
            row["status"] = "ANCHOR-OK"
            rows.append(row)
            if verbose:
                print(f"  --  {mut['script']:<24} anchor OK (dry-run)", flush=True)
            continue

        try:
            mutated = original.replace(mut["anchor"], mut["replacement"], 1)
            path.write_bytes(mutated.encode("utf-8"))
            _, failed = run_subset(Path(mut["script"]).stem)
            if failed:
                row["status"] = "KILLED"
                row["killed_by"] = failed[:5]
            else:
                row["status"] = "SURVIVED"
                row["note"] = ("no case failed when the gate was broken — "
                               "tests do not constrain this behaviour")
        finally:
            path.write_bytes(raw)  # byte-exact restore (line endings preserved)
            if hashlib.sha256(path.read_bytes()).hexdigest() != original_sha:
                print(f"[FATAL] restore failed for {mut['script']} — source may be "
                      f"mutated, recover from git: git checkout -- {path}",
                      file=sys.stderr, flush=True)
                sys.exit(3)

        rows.append(row)
        if verbose:
            mark = "OK " if row["status"] == "KILLED" else "!! "
            extra = f" ({len(failed)} case(s) failed)" if row["status"] == "KILLED" else ""
            print(f"  {mark} {mut['script']:<24} {row['status']:<9}{extra}", flush=True)
    # `--only X` matching nothing must FAIL, not silently pass: a CI job asking to
    # audit one gate would otherwise report success while auditing nothing.
    if only and not rows:
        rows.append({"script": only, "desc": "--only selector", "status": "STALE",
                     "killed_by": [], "note": f"no mutation defined for {only}"})
        if verbose:
            print(f"  !!  {only:<24} STALE   no mutation defined", flush=True)

    bad = sum(1 for r in rows if r["status"] in ("SURVIVED", "STALE"))
    return rows, bad


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate mutation audit (do the tests bite?)")
    ap.add_argument("--json", action="store_true", help="machine-readable report to stdout")
    ap.add_argument("--only", default=None, help="run mutations for one script only")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate anchors only; never modify files")
    args = ap.parse_args()

    if not args.json:
        print("== mutation audit: 把闸改成恒放行，看有没有用例变红 ==", flush=True)
    rows, bad = audit(only=args.only, dry_run=args.dry_run, verbose=not args.json)

    rep = {"schema": SCHEMA, "mutations": len(rows), "bad": bad, "rows": rows,
           "verdict": "ALL KILLED" if bad == 0 else f"{bad} UNCONSTRAINED"}
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(f"\nVerdict: {rep['verdict']}")
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
