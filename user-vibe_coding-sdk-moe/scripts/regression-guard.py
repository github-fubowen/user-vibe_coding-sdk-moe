#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regression-guard.py — 回归测试双向验证闸（T-21 / F-32，v2.9.0）

Why: verification-kernel §B.11 —— 防止"自证式弱测试"的确定性保障。agent 生成的
回归测试必须**机械验证两次**：
    在修复前（--base）必须 FAIL  —— 证明它复现的是那个 bug，不是恒真断言
    在修复后（--head）必须 PASS  —— 证明修复真的修好了
两边都过 = 测试什么都没证明（tautology）→ 拒绝；两边都挂 = 修复未完成 → 拒绝。

Mechanics (stdlib only, no working-tree mutation):
  * `git worktree add --detach <tmp> <ref>` 物化每个 ref 到临时目录（不碰当前
    工作树、不 stash、不 checkout），命令在 worktree 内执行，finally 里
    `worktree remove --force` + `worktree prune` 清理。
  * 隐含纪律：**未提交的修复不在此闸覆盖范围内**（worktree 只看已提交历史）
    —— 与 §10 规则 1"本地提交=默认"衔接：先 commit，再过闸。

Verdicts (exit 0 only for VALID):
  VALID_REGRESSION_TEST  base FAIL 且 head PASS —— 双向验证通过
  WEAK_TEST              base PASS 且 head PASS —— 自证式弱测试，拒绝并要求重写
  FIX_INCOMPLETE         base FAIL 且 head FAIL —— 修复未生效，拒绝
  NOT_A_REGRESSION       base PASS 且 head FAIL —— 测试坏掉或修复引入回归，拒绝

Usage:
  python regression-guard.py --cwd <repo> --base HEAD~1 --json --test pytest -q tests/test_x.py
  python regression-guard.py --cwd <repo> --base <sha> --head <sha> --test python tests/test_x.py
Exit: 0 = VALID / 2 = 任何其他情形（fail-closed）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "regression-guard.v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run_cmd(cmd: list, cwd: str, timeout: int, tail_lines: int) -> dict:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
        out = (r.stdout or "") + (r.stderr or "")
        return {"exit_code": r.returncode, "ok": r.returncode == 0,
                "tail": [ln for ln in out.splitlines() if ln.strip()][-tail_lines:]}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "ok": False, "tail": ["[timeout] exceeded --timeout"]}


def git(repo: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, timeout=timeout)


def materialize_worktree(repo: Path, ref: str, wt_root: Path, tag: str) -> tuple[Path, str | None]:
    wt = wt_root / f"wt-{tag}"
    r = git(repo, "worktree", "add", "--detach", str(wt), ref)
    if r.returncode != 0:
        return wt, (r.stderr or r.stdout or "worktree add failed").strip()[:300]
    return wt, None


def remove_worktree(repo: Path, wt: Path) -> None:
    try:
        git(repo, "worktree", "remove", "--force", str(wt))
        git(repo, "worktree", "prune")
    except Exception:
        pass  # 清理失败不改变判定（临时目录由系统回收），但不能吞掉主流程


def main() -> int:
    ap = argparse.ArgumentParser(description="Regression-test double-check gate (T-21, F-32)")
    ap.add_argument("--base", required=True, help="pre-fix ref (commit/sha) — the test MUST FAIL here")
    ap.add_argument("--head", default="HEAD", help="post-fix ref (default: HEAD) — must PASS here")
    ap.add_argument("--cwd", default=".", help="repo dir (default: current dir)")
    ap.add_argument("--timeout", type=int, default=300, help="per-run timeout seconds")
    ap.add_argument("--tail", type=int, default=8, help="bounded tail lines kept per run")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    ap.add_argument("--test", nargs=argparse.REMAINDER, default=None,
                    help="the regression-test command (put it LAST, runs inside each worktree)")
    args = ap.parse_args()

    problems: list[str] = []
    if not args.test:
        problems.append("--test required (put the test command last)")
    repo = Path(args.cwd).resolve()
    if not (repo / ".git").exists():
        problems.append(f"--cwd is not a git repo (no .git): {repo}")

    base_row = head_row = None
    verdict = "ERROR"
    if not problems:
        with tempfile.TemporaryDirectory(prefix="rg-worktrees-") as td:
            wt_root = Path(td)
            runs: dict[str, dict] = {}
            for tag, ref in (("base", args.base), ("head", args.head)):
                wt, err = materialize_worktree(repo, ref, wt_root, tag)
                if err:
                    problems.append(f"cannot materialize {tag} ref {ref!r}: {err}")
                    break
                try:
                    runs[tag] = run_cmd(list(args.test), str(wt), args.timeout, args.tail)
                finally:
                    remove_worktree(repo, wt)
            if not problems and {"base", "head"} <= runs.keys():
                base_row, head_row = runs["base"], runs["head"]
                base_fail, head_pass = (not base_row["ok"]), head_row["ok"]
                if base_fail and head_pass:
                    verdict = "VALID_REGRESSION_TEST"
                elif not base_fail and head_pass:
                    verdict = "WEAK_TEST"
                    problems.append("test PASSES on pre-fix code too — it proves nothing "
                                    "(tautology); rewrite it to reproduce the bug")
                elif base_fail and not head_pass:
                    verdict = "FIX_INCOMPLETE"
                    problems.append("test still fails post-fix — the fix does not resolve the bug")
                else:
                    verdict = "NOT_A_REGRESSION"
                    problems.append("test passes pre-fix but FAILS post-fix — broken test "
                                    "or the fix introduced a regression")

    report = {
        "schema": SCHEMA,
        "time": now_iso(),
        "repo": str(repo),
        "base_ref": args.base, "head_ref": args.head,
        "verdict": verdict,
        "problems": problems,
        "base": ({"ref": args.base, "expected": "FAIL", "ok_as_expected": (base_row or {}).get("ok") is False,
                  "exit_code": (base_row or {}).get("exit_code"), "tail": (base_row or {}).get("tail", [])}),
        "head": ({"ref": args.head, "expected": "PASS", "ok_as_expected": (head_row or {}).get("ok") is True,
                  "exit_code": (head_row or {}).get("exit_code"), "tail": (head_row or {}).get("tail", [])}),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"== regression-guard: {report['verdict']} ==")
        print(f"  base({args.base}) expected FAIL -> exit={report['base']['exit_code']}")
        print(f"  head({args.head}) expected PASS -> exit={report['head']['exit_code']}")
        for p in problems:
            print(f"  [!!] {p}", file=sys.stderr)
    return 0 if verdict == "VALID_REGRESSION_TEST" else 2


if __name__ == "__main__":
    sys.exit(main())
