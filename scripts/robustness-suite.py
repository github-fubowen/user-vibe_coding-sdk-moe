#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robustness-suite.py — SDK 鲁棒性回归套件 (v1.0, 2026-08-22)

Purpose: freeze the robustness audit's 20 fault-injection cases into a
deterministic regression suite (ref-19 建议 #2). Run after ANY script change:
`python scripts/robustness-suite.py` — exit 0 = all green, 2 = regression.

Design rules (SDK §3/G-gates, robustness-audit-2026-08-22):
  * Python 3.9+ stdlib only. JSON out via --json. Exit 0/2 (对齐 0/2 约定).
  * Each case = subprocess invocation with expected exit code + marker checks
    (must-contain / must-not-contain "Traceback").
  * Fixtures (bad JSON / bad regex set / empty set / missing store) built in
    a temp dir; NEVER touches the SDK repo or network (all offline cases).

Usage:
  python robustness-suite.py                # human PASS/FAIL table
  python robustness-suite.py --json         # machine-readable
  python robustness-suite.py --only golden-run  # filter by script name substring
Exit codes: 0 = all cases pass / 2 = at least one regression (or suite error).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable

# T-16：--timing 实测（2026-08-30，全量 83 用例 / 181s）按脚本聚合的头部：
#   toolstack-pipeline.py 41.3s（1 用例，gh api 上游核对）
#   git-pre-commit.py     33.4s（6 用例，内部递归跑 robustness 子集）
#   其余全部 < 12s
# 这两个占全量 41%，--quick 跳过它们；全量仍由 ci-smoke 定时跑。
SLOW_SCRIPTS = {"toolstack-pipeline.py", "git-pre-commit.py"}

BAD_JSON = "{bad json"
BAD_REGEX_SET = '{"samples":[{"id":"x","task_type":"qa","prompt":"p","accept":[{"type":"regex","pattern":"["}]}]}'
EMPTY_SET = '{"samples":[]}'
ONE_SET_NO_ACCEPT = '{"samples":[{"id":"a","task_type":"qa","prompt":"p"}]}'
ONE_SET_OK = '{"samples":[{"id":"a","task_type":"qa","prompt":"1+1","accept":[{"type":"contains","text":"2"}],"response":"2"}]}'
# F-01 回归（2026-08-31）：usage.completion_tokens 虚报 2048 但 text 为空 →
# 空响应检测必须用文本实导 token，否则被误判 quality 能力失败（Ollama length 截断实测）。
EMPTY_USAGE_SET = ('{"samples":[{"id":"e1","cell":"qa","task_type":"qa","prompt":"p",'
                   '"response":"","usage":{"prompt_tokens":5,"completion_tokens":2048},'
                   '"accept":[{"type":"contains","text":"x"}]}]}')
GARBAGE_LOG = "not json at all\n{\"partial\": true\nmore garbage\n"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run_case(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    """Run a case; returns (exit_code, combined_output). Never raises."""
    try:
        # Suite context is non-interactive by definition — declare it explicitly
        # (v2.7.1) so scripts with tty gates (e.g. toolstack-pipeline --push)
        # never block on input() even if the host's isatty() lies (ConPTY).
        env = dict(os.environ, SDK_NONINTERACTIVE="1")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             stdin=subprocess.DEVNULL, env=env)
        out = (res.stdout or "") + (res.stderr or "")
        return res.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 127, f"suite error: {type(e).__name__}: {e}"


def build_cases(tmp: Path, only: str | None = None) -> list[dict]:
    """Build the 20-case matrix. Returns [{name, script, args, expect, want, dont}].

    `only`（v2.9.0 F-40）：--only 过滤值提前透传，供昂贵夹具（git 仓库）惰性搭建。
    """
    (tmp / "bad.json").write_text(BAD_JSON, encoding="utf-8")
    (tmp / "badregex.json").write_text(BAD_REGEX_SET, encoding="utf-8")
    (tmp / "empty.json").write_text(EMPTY_SET, encoding="utf-8")
    (tmp / "noaccept.json").write_text(ONE_SET_NO_ACCEPT, encoding="utf-8")
    (tmp / "ok.json").write_text(ONE_SET_OK, encoding="utf-8")
    (tmp / "empty-usage.json").write_text(EMPTY_USAGE_SET, encoding="utf-8")
    (tmp / "garbage.jsonl").write_text(GARBAGE_LOG, encoding="utf-8")
    (tmp / "empty.log").write_text("", encoding="utf-8")

    # privacy-scan fixtures (v1.16.0)
    (tmp / "clean").mkdir()
    (tmp / "clean" / "ok.txt").write_text("hello world\n", encoding="utf-8")
    (tmp / "leak").mkdir()
    (tmp / "leak" / "secret.txt").write_text(
        'key = "sk-TEST-abcdefghijklmnopqrstuvwxyz"\npath = "C:\\\\Users\\\\alice\\\\x"\n',  # TEST fixture: fake key + fake path
        encoding="utf-8")
    # v2.7.1 F-15: host runtime pollution fixture (automation writes into cwd)
    poll = tmp / "polluted"
    (poll / ".workbuddy" / "automations" / "autoid").mkdir(parents=True)
    (poll / ".workbuddy" / "automations" / "autoid" / "memory.md").write_text(
        "cmd: D:\\WorkBuddy\\output\\sdk-smoke\\smoke.json\n", encoding="utf-8")
    (poll / ".workbuddy" / "memory").mkdir(parents=True)
    (poll / ".workbuddy" / "memory" / "2026-09-01.md").write_text(
        "log: D:/softlink/y.md\n", encoding="utf-8")
    # debug-cases is a shipped deliverable — .workbuddy itself must NOT be skipped wholesale
    (poll / ".workbuddy" / "debug-cases").mkdir(parents=True)
    (poll / ".workbuddy" / "debug-cases" / "case.md").write_text(
        "clean case text\n", encoding="utf-8")

    # task-state fixtures (v2.0.0): one valid INIT task + one garbage file
    tasks_dir = tmp / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "t-ok.json").write_text(json.dumps({
        "schema": "task-state.v1", "task_id": "t-ok", "title": "fixture", "mode": "Debug",
        "state": "INIT", "verdict": None,
        "created_at": "2026-08-26T00:00:00+08:00", "updated_at": "2026-08-26T00:00:00+08:00",
        "history": [{"ts": "2026-08-26T00:00:00+08:00", "from": None, "to": "INIT",
                     "verdict": None, "note": "created"}],
        "blackboard": {"recent_actions": [], "known_failures": [], "residuals": [], "facts": {}},
    }, ensure_ascii=False), encoding="utf-8")
    (tasks_dir / "t-bad.json").write_text("{bad task json", encoding="utf-8")

    # verify-runner layered fixtures (v2.0.0)
    (tmp / "layers-ok.json").write_text(json.dumps({
        "layers": [{"name": "syntax", "cmd": [PY, "-c", "print('ok')"]},
                   {"name": "lint", "cmd": [PY, "-c", "print('ok2')"]}],
        "short_circuit": True}, ensure_ascii=False), encoding="utf-8")
    (tmp / "layers-fail.json").write_text(json.dumps({
        "layers": [{"name": "syntax", "cmd": [PY, "-c", "print('ok')"]},
                   {"name": "lint", "cmd": [PY, "-c", "import sys; sys.exit(3)"]}],
        "short_circuit": True}, ensure_ascii=False), encoding="utf-8")
    (tmp / "layers-bad.json").write_text(json.dumps({
        "layers": [{"name": "syntax"}]}, ensure_ascii=False), encoding="utf-8")

    # router-stats fixtures (v2.2.0, T8)
    (tmp / "corrupt.db").write_bytes(b"this is not a sqlite database at all " * 10)

    # v2.7.1 F-17: legacy-shaped db (v2 columns exist but unpopulated — the exact
    # state of the production db before the backfill migration)
    legacy = tmp / "legacy.db"
    lc = sqlite3.connect(str(legacy))
    lc.executescript(
        "CREATE TABLE routing_log (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts TEXT NOT NULL, task TEXT, cell TEXT NOT NULL, model TEXT NOT NULL,"
        " level INTEGER DEFAULT 0, outcome TEXT NOT NULL, tokens INTEGER DEFAULT 0,"
        " cost REAL DEFAULT 0, latency_ms INTEGER DEFAULT 0,"
        " error_class TEXT, response_tokens INTEGER DEFAULT 0);"
        "CREATE TABLE bandit (model TEXT NOT NULL, cell TEXT NOT NULL,"
        " alpha INTEGER DEFAULT 0, beta INTEGER DEFAULT 0, n INTEGER DEFAULT 0,"
        " success_count INTEGER DEFAULT 0, cost_sum REAL DEFAULT 0,"
        " tokens_sum INTEGER DEFAULT 0, infra_count INTEGER DEFAULT 0,"
        " PRIMARY KEY (model, cell));")
    lc.execute("INSERT INTO routing_log (ts, cell, model, outcome, tokens)"
               " VALUES ('2026-08-28T00:00:00+08:00','qa','m-legacy','fail',2185)")
    lc.execute("INSERT INTO routing_log (ts, cell, model, outcome, tokens)"
               " VALUES ('2026-08-28T00:00:00+08:00','qa','m-legacy','fail',7)")
    lc.commit()
    lc.close()

    # memory-layer fixture for case-search --layer (v2.2.0, T9)
    mem_dir = tmp / "mem"
    mem_dir.mkdir()
    (mem_dir / "solutions.json").write_text(json.dumps({
        "schema": "memory.v1", "layer": "solutions", "entries": [
            {"id": "s1", "problem": "verify-runner crash on missing cmd",
             "solution": "guard with exit 2", "applies_to": "verify-runner", "verified": True}]},
        ensure_ascii=False), encoding="utf-8")

    # token-meter budget fixture (v2.2.0, T10): 60 simple records
    with (tmp / "many.jsonl").open("w", encoding="utf-8") as f:
        for _ in range(60):
            f.write('{"model_id":"m1","in_tokens":10,"out_tokens":5,"success":true}\n')

    # git hooks fixture (v2.4.0, P0-1): throwaway repo for install-hooks tests
    repo_dir = tmp / "hook-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-q", str(repo_dir)], capture_output=True, timeout=30)

    # C0-2 fixtures (v2.4.1): renamed SDK dir copy + second throwaway repo
    repo2 = tmp / "hook-repo2"
    repo2.mkdir()
    subprocess.run(["git", "init", "-q", str(repo2)], capture_output=True, timeout=30)
    # 负向覆盖审计：外来钩子拒绝路径（exit 1）此前无任何用例
    repo3 = tmp / "hook-repo-foreign"
    repo3.mkdir()
    subprocess.run(["git", "init", "-q", str(repo3)], capture_output=True, timeout=30)
    hooks3 = repo3 / ".git" / "hooks"
    hooks3.mkdir(parents=True, exist_ok=True)
    (hooks3 / "pre-commit").write_text("#!/bin/sh\n# foreign hook installed by someone else\nexit 0\n",
                                       encoding="utf-8")
    renamed_sdk = tmp / "renamed-sdk" / "scripts"
    renamed_sdk.mkdir(parents=True)
    # probe-tools.py is required by build_cases' isolated-copy fixture even under
    # --only (unconditional read) — copy it so the renamed suite builds offline.
    for fn in ("git-pre-commit.py", "install-hooks.py", "robustness-suite.py",
               "token-meter.py", "probe-tools.py"):
        (renamed_sdk / fn).write_text(
            (SCRIPT_DIR / fn).read_text(encoding="utf-8"), encoding="utf-8")

    # C0-4 fixtures (v2.4.1): data-file gate — valid baseline + bad golden set
    (tmp / "baseline-tmp.json").write_text('{"schema":"baseline.v1","pass_rate":1.0}', encoding="utf-8")
    (tmp / "golden-set-bad.json").write_text(BAD_JSON, encoding="utf-8")
    (tmp / "golden-set-ok.json").write_text(ONE_SET_OK, encoding="utf-8")

    # C1-1 fixtures (v2.5.0): task-workspace — root + worktree repo + marker-less dir
    ws_root = tmp / "ws"
    ws_root.mkdir()
    ws_repo = tmp / "ws-repo"
    ws_repo.mkdir()
    subprocess.run(["git", "init", "-q", str(ws_repo)], capture_output=True, timeout=30)
    no_marker = ws_root / "t-nomarker"
    no_marker.mkdir()

    # C1-2/C1-3 fixtures (v2.5.0): task-state production fields + CI/deploy states.
    # History chain builder — valid chain from INIT to the target state.
    def make_task(task_id: str, state: str, extra: dict | None = None) -> None:
        chain = ["INIT", "UNDERSTAND", "CLASSIFY", "PLAN", "IMPLEMENT", "VERIFY"]
        hist = []
        prev = None
        for i, st in enumerate(chain):
            hist.append({"ts": f"2026-08-28T00:00:{i:02d}+08:00", "from": prev,
                         "to": st, "verdict": None, "note": "fixture"})
            prev = st
        if state not in chain:
            hist.append({"ts": "2026-08-28T00:00:09+08:00", "from": prev,
                         "to": state, "verdict": None, "note": "fixture"})
        task = {"schema": "task-state.v1", "task_id": task_id, "title": "fixture",
                "mode": "Engineering", "state": state, "verdict": None,
                "created_at": "2026-08-28T00:00:00+08:00",
                "updated_at": "2026-08-28T00:00:00+08:00",
                "history": hist, "blackboard": {"recent_actions": [],
                                                "known_failures": [], "residuals": [], "facts": {}}}
        if extra:
            task.update(extra)
        (tasks_dir / f"{task_id}.json").write_text(json.dumps(task, ensure_ascii=False),
                                                   encoding="utf-8")

    make_task("t-ci", "VERIFY")
    make_task("t-ci-running", "CI_RUNNING")
    make_task("t-ci-failing", "CI_RUNNING")
    make_task("t-ci-failed", "CI_FAILED")
    make_task("t-ci-passed", "CI_PASSED")
    make_task("t-prod", "PROD_VERIFY")
    make_task("t-run", "INIT")
    make_task("t-badprio", "VERIFY", {"priority": "P9"})

    # C1-4 fixtures (v2.5.0): ci-fail-analyze log samples
    (tmp / "unit.log").write_text(
        "============================= short test summary =============================\n"
        "FAILED tests/test_x.py::test_x - assert 1 == 2\n1 failed in 3.42s\n",
        encoding="utf-8")
    (tmp / "timeout.log").write_text(
        "##[error]The operation was canceled.\nError: The operation was canceled.\n",
        encoding="utf-8")
    # C1-4 回归（2026-08-28 综合测试）：小写 "failed" 的安装错误不得被 unit_failure 抢先
    (tmp / "install.log").write_text(
        "error: failed to install pytest (build failed)\n",
        encoding="utf-8")
    # v2.9.0 fixtures（T-19 origin class）
    (tmp / "dep-infra.log").write_text(
        "ERROR: Could not find a version that satisfies the requirement x==9.9\n"
        "WARNING: Retrying after connection broken by ProtocolError: Connection reset by peer\n",
        encoding="utf-8")
    (tmp / "test-fixture.log").write_text(
        "FAILED tests/test_db.py - error in setup: fixture 'db_session' not found\n",
        encoding="utf-8")
    (tmp / "unclass.log").write_text(
        "##[error]Process completed with exit code 137.\n",
        encoding="utf-8")

    # C2-3 fixture (v2.6.0): empty .github dir for negative check
    (tmp / "empty-gh").mkdir()

    # C2-4 fixture (v2.6.0): sample spec-kit tasks.md
    (tmp / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [ ] **T-001** 实现登录模块 [P0]\n"
        "  - 表单校验\n"
        "  - 会话持久化\n"
        "- [ ] **T-002** 重构路由表 [P2]\n",
        encoding="utf-8")
    (tmp / "tasks-empty.md").write_text("# Tasks\n\nno checklist here\n", encoding="utf-8")

    # probe-tools "missing manifest" needs an isolated copy (its manifest lives in scripts/)
    isolated = tmp / "isolated"
    isolated.mkdir()
    (isolated / "probe-tools.py").write_text(
        (SCRIPT_DIR / "probe-tools.py").read_text(encoding="utf-8"), encoding="utf-8")

    # --- v2.7.0 fixtures (T-08/T-09/T-14 硬闸) ---
    def _task(task_id, state, **over):
        base = {
            "schema": "task-state.v1", "task_id": task_id, "title": "fixture", "mode": "Debug",
            "state": state, "verdict": None, "depends_on": [],
            "priority": "P2", "acceptance_criteria": "", "branch": None, "workspace": None,
            "runs": [], "checkpoint": None, "repair_budget": {"max": 3, "used": 0},
            "created_at": "2026-08-30T00:00:00+08:00", "updated_at": "2026-08-30T00:00:00+08:00",
            "history": [{"ts": "2026-08-30T00:00:00+08:00", "from": None, "to": state,
                         "verdict": None, "note": "fixture"}],
            "blackboard": {"recent_actions": [], "known_failures": [], "residuals": [], "facts": {}},
        }
        base.update(over)
        (tasks_dir / f"{task_id}.json").write_text(
            json.dumps(base, ensure_ascii=False), encoding="utf-8")

    # 预算耗尽：used=3/max=3 → 再进 REPAIR 必须被拒
    _task("t-budget", "DIAGNOSE", repair_budget={"max": 3, "used": 3})
    # 振荡：history 已有 3 次 DIAGNOSE->REPAIR，budget 不限以隔离循环闸
    loop_history = [{"ts": "2026-08-30T00:00:00+08:00", "from": None, "to": "VERIFY",
                     "verdict": None, "note": "fixture"}]
    for _i in range(3):
        for _frm, _to in (("VERIFY", "DIAGNOSE"), ("DIAGNOSE", "REPAIR"),
                          ("REPAIR", "REVERIFY"), ("REVERIFY", "VERIFY")):
            loop_history.append({"ts": "2026-08-30T00:01:%02d+08:00" % len(loop_history),
                                 "from": _frm, "to": _to, "verdict": None, "note": "f"})
    _task("t-loop", "DIAGNOSE", repair_budget={"max": 0, "used": 0},
          history=loop_history)
    # 可恢复暂停 / 崩溃恢复
    _task("t-waiting", "WAITING")
    _task("t-crashed", "CRASHED", checkpoint={
        "ts": "2026-08-30T00:00:00+08:00", "state": "VERIFY",
        "context_pointer": "sess:turn-42", "workspace_ref": "wt/x"})
    _task("t-nocp", "CRASHED")
    # DAG 依赖：dep-x 未完成
    _task("dep-x", "IMPLEMENT")
    _task("t-dep", "PLAN", depends_on=["dep-x"])
    _task("dep-ok", "DONE")
    _task("t-depok", "PLAN", depends_on=["dep-ok"])

    # --- v2.8.0 fixtures（T-07/T-08/T-09/T-10）---
    # 置信度分层 fixture：含 test-targeted 与 test-full（验证轻/中档 targeted 优先）
    (tmp / "conf-layers.json").write_text(json.dumps({"layers": [
        {"name": "syntax", "cmd": [PY, "-c", "print('s')"]},
        {"name": "typecheck", "cmd": [PY, "-c", "print('t')"]},
        {"name": "test-targeted", "cmd": [PY, "-c", "print('tt')"]},
        {"name": "test-full", "cmd": [PY, "-c", "print('tf')"]}],
        "short_circuit": True}), encoding="utf-8")
    # v2.8.2 fixtures（T-17 security 恒保）：含 security 层 + 会被 targeted 剔除的 test-full
    (tmp / "conf-sec.json").write_text(json.dumps({"layers": [
        {"name": "syntax", "cmd": [PY, "-c", "print('s')"]},
        {"name": "format", "cmd": [PY, "-c", "print('f')"]},
        {"name": "typecheck", "cmd": [PY, "-c", "print('t')"]},
        {"name": "test-targeted", "cmd": [PY, "-c", "print('tt')"]},
        {"name": "test-full", "cmd": [PY, "-c", "print('tf')"]},
        {"name": "security", "cmd": [PY, "-c", "print('sec')"]}],
        "short_circuit": True}), encoding="utf-8")
    # v2.8.2 fixtures（T-16 version-check）：三个文档根
    def _doc_root(name: str, skill_v: str, readme_v: str, heads: list) -> None:
        d = tmp / f"vc-{name}"
        d.mkdir(exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: x\ndescription: >-\n  SDK ({skill_v}).\n---\n\n# x {skill_v} — t\n",
            encoding="utf-8")
        (d / "README.md").write_text(
            f"> blurb {readme_v}\n\n- 版本：**{readme_v}**\n", encoding="utf-8")
        (d / "CHANGELOG.md").write_text(
            "# CHANGELOG\n\n" + "".join(f"## {h}（2026-09-01）\n\n- entry\n\n" for h in heads),
            encoding="utf-8")

    _doc_root("ok", "v1.2.3", "v1.2.3", ["v1.2.3", "v1.2.2", "v1.2.1"])
    _doc_root("badorder", "v1.2.3", "v1.2.3", ["v1.2.2", "v1.2.3"])   # F-26 形态
    _doc_root("badver", "v1.2.3", "v1.2.2", ["v1.2.3"])               # 版本串失配
    # v2.9.0 fixtures（T-18 随包预设可达性 / T-22 测试选择）
    (tmp / "empty-cwd").mkdir(exist_ok=True)
    (tmp / "sel-src").mkdir(exist_ok=True)
    (tmp / "sel-src" / "tests").mkdir(exist_ok=True)
    (tmp / "sel-src" / "tests" / "test_foo.py").write_text("# t\n", encoding="utf-8")
    (tmp / "sel-src" / "tests" / "test_bar.py").write_text("# t\n", encoding="utf-8")
    (tmp / "sel-src" / "tests" / "test_othersub.py").write_text("# t\n", encoding="utf-8")
    (tmp / "sel-verify.json").write_text(json.dumps({"layers": [
        {"name": "syntax", "cmd": [PY, "-c", "print('s')"]},
        {"name": "test-targeted", "cmd": [PY, "-c", "import sys; print('TARGETED_ARGS', sys.argv[1:])"]},
        {"name": "test-full", "cmd": [PY, "-c", "print('tf')"]}],
        "short_circuit": True}), encoding="utf-8")
    # v2.9.0 fixtures（T-20 flaky-check）：确定性交替通过/失败的脚本（标记文件翻转）
    (tmp / "flaky-toggle.py").write_text(
        "import os, sys\n"
        "m = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flaky-marker')\n"
        "if os.path.exists(m):\n"
        "    os.remove(m); sys.exit(1)\n"
        "open(m, 'w').close(); sys.exit(0)\n", encoding="utf-8")
    (tmp / "flaky-infra.py").write_text(
        "import os, sys\n"
        "m = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'infra-marker')\n"
        "if os.path.exists(m):\n"
        "    os.remove(m); print('connection reset by peer'); sys.exit(1)\n"
        "open(m, 'w').close(); sys.exit(0)\n", encoding="utf-8")
    # v2.9.0 fixtures（T-21 regression-guard）：三类微型 git 仓库（两提交）
    # F-40（实施期发现）：git 夹具昂贵——3×(init+2 commit) 在本机 ≈60-80s，把
    # `--only <script>` 子集（git-pre-commit 门禁内部调用）顶过了 60s 用例超时
    # （exit 124 假失败）。改为**惰性搭建**：仅当过滤器会跑 regression-guard 用例。
    def _git_repo(name: str, base_fails: bool, head_fails: bool) -> None:
        d = tmp / f"rg-{name}"
        (d / "tests").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(d)], check=True, capture_output=True)
        counter = {"n": 0}

        def commit(fails: bool) -> None:
            counter["n"] += 1  # 每次提交内容必有变化（否则 weak 仓库第二次 commit 无可提交）
            (d / "tests" / "test_x.py").write_text(
                f"import sys  # rev {counter['n']}\n"
                + ("sys.exit(1)\n" if fails else "sys.exit(0)\n"), encoding="utf-8")
            subprocess.run(["git", "-C", str(d), "add", "-A"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(d), "-c", "user.email=t@t", "-c", "user.name=t",
                            "commit", "-qm", "c"], check=True, capture_output=True)

        commit(base_fails)
        commit(head_fails)

    if only is None or "regression-guard" in only:
        _git_repo("valid", base_fails=True, head_fails=False)
        _git_repo("weak", base_fails=False, head_fails=False)
        _git_repo("incomplete", base_fails=True, head_fails=True)
    # v2.10.0 fixtures（T-23/T-25/T-26 patch-gate / action-gate / 幂等键）
    (tmp / "p2-numstat.txt").write_text("12\t3\tsrc/a.py\n5\t2\tsrc/b.py\n", encoding="utf-8")
    (tmp / "p2-numstat-bad.txt").write_text(
        "1\t1\ta.py\n1\t1\tb.py\n1\t1\tc.py\n1\t1\td.py\n1\t1\te.py\n1\t1\tf.py\n"
        "200\t130\tg.py\n", encoding="utf-8")
    (tmp / "p2-numstat-deps.txt").write_text(
        "1\t1\tsrc/x.py\n10\t2\trequirements.txt\n20\t5\trequirements-dev.txt\n", encoding="utf-8")
    # F-53 fixture：畸形 numstat（列序颠倒 → 非数字列），必须干净 exit 2 而非裸 traceback
    (tmp / "p2-numstat-malformed.txt").write_text(
        "src/a.py\t3\t120\n1\t10\tok.py\n", encoding="utf-8")
    _task("t-idem", "PLAN")
    _task("t-esc", "VERIFY")
    # T-09 新故障类日志
    (tmp / "perm.log").write_text("npm ERR! code EACCES\nEACCES: permission denied, mkdir '/x'\n",
                                  encoding="utf-8")
    (tmp / "dep.log").write_text(
        "ERROR: Could not find a version that satisfies the requirement x==9.9\n", encoding="utf-8")
    (tmp / "assertj.log").write_text(
        'expect(received).toBe(expected)\n    Expected: "ok"\n    Received: "fail"\n', encoding="utf-8")
    # T-08：FINALIZE 任务（done_when 有值 → 无证据拒 / 有证据放行）
    _task("t-done1", "FINALIZE", done_when="全部测试绿")

    # verify-runner allow_missing fixture (T-07)
    (tmp / "layers-missing.json").write_text(json.dumps({
        "layers": [{"name": "syntax", "cmd": [PY, "-c", "print('ok')"]},
                   {"name": "lint", "cmd": ["definitely-not-a-real-tool-xyz", "--check"],
                    "allow_missing": True}],
        "short_circuit": True}, ensure_ascii=False), encoding="utf-8")

    # v2.10.2 fixtures（F-43 漂移哨兵）：selfcheck-static --root 指向临时 SDK 树。
    # 真 scripts/ 目录不能拿来造 drift（会污染仓库），所以造一棵最小合规树。
    def _sdk_tree(tag: str, register: bool) -> Path:
        root = tmp / f"sdktree-{tag}"
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "references").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "zz-probe.py").write_text("# probe\n", encoding="utf-8")
        (root / "scripts" / "toolstack.json").write_text(json.dumps({
            "schema": 3, "last_check": "2026-09-01T00:00:00+08:00",
            "sdk_tools_exempt": [], "local_tools": {}, "refs": {},
            "sdk_tools": ({"zz-probe.py": {"risk_tier": 1}} if register else {}),
        }, ensure_ascii=False), encoding="utf-8")
        # frontmatter 名必须是 SDK 真名，否则用例会因别的原因失败
        (root / "SKILL.md").write_text(
            "---\nname: user-vibe_coding-sdk-moe\ndescription: fixture\n---\n"
            "\n# user-vibe_coding-sdk-moe v9.9.9\n", encoding="utf-8")
        # 不完整树（fixture / 部分检出）：必须干净 exit 2，绝不 traceback
        (tmp / "partial-sdk" / "scripts").mkdir(parents=True, exist_ok=True)
        (tmp / "partial-sdk" / "scripts" / "a.py").write_text("x = 1\n", encoding="utf-8")
        # 负向覆盖审计：toolstack-pipeline 是闸（drift → exit 2）但此前 0 条拦截用例。
        # 真实上游漂移不可控（依赖网络），故用 --manifest 指向篡改过 sha256 的副本，
        # 数据完整性检查离线且确定性 —— 断言 MISMATCH 而非笼统的 exit 2。
        # 注意：renamed-dir fixture 是 SDK 的部分副本（无 toolstack.json），build_cases
        # 会在那里被整体执行 —— 依赖真实仓库文件的 fixture 必须存在性守卫，否则
        # 复制体里直接 FileNotFoundError，把 C0-2 renamed-dir 用例连带打挂（F-48 同族）。
        _ts = SCRIPT_DIR / "toolstack.json"
        if _ts.exists():
            _m = json.loads(_ts.read_text(encoding="utf-8"))
            _m["refs"]["12-public-apis"]["data"]["sha256"] = "0" * 64
            (tmp / "toolstack-drift.json").write_text(
                json.dumps(_m, ensure_ascii=False), encoding="utf-8")
        # 负向覆盖审计：review-prefilter 文档明写 "0 = checks pass / 2 = a check failed
        # (blocker)"，但此前 1 条用例只有 expect=0 —— 拦截路径从未被证明过。
        # 用 --config 传 cmd 列表（`--checks` 走 str.split()，引号会碎），跨平台稳定。
        (tmp / "review-fail.json").write_text(json.dumps({
            "checks": [{"name": "always-fail",
                        "cmd": [PY, "-c", "import sys; sys.exit(1)"], "timeout": 30}]
        }, ensure_ascii=False), encoding="utf-8")
        (tmp / "review-pass.json").write_text(json.dumps({
            "checks": [{"name": "always-pass",
                        "cmd": [PY, "-c", "print('ok')"], "timeout": 30}]
        }, ensure_ascii=False), encoding="utf-8")
        return root

    def C(name, script, args, expect, want=(), dont=("Traceback",), expect_any=(), timeout=None):
        return {"name": name, "script": script,
                "cmd": [PY, str(SCRIPT_DIR / script), *[str(a) for a in args]],
                "expect": expect, "expect_any": tuple(expect_any),
                "want": want, "dont": dont, "timeout": timeout}

    return [
        # --- golden-run: universal boundaries ---
        C("golden-run: --help", "golden-run.py", ["--help"], 0, want=("usage",)),
        C("golden-run: missing --set", "golden-run.py", [], 2, want=("required",)),
        C("golden-run: nonexistent set", "golden-run.py", ["--set", tmp / "nope.json"], 2, want=("not found",)),
        C("golden-run: empty samples", "golden-run.py", ["--set", tmp / "empty.json"], 2, want=("no samples",)),
        # --- golden-run: validate-set pre-check (v1.15.0) ---
        C("golden-run: validate-set bad regex", "golden-run.py",
          ["--set", tmp / "badregex.json", "--validate-set"], 2, want=("regex compile failed",)),
        C("golden-run: validate-set ok set", "golden-run.py",
          ["--set", tmp / "ok.json", "--validate-set"], 0, want=("VALID",)),
        # --- golden-run: adversarial judging ---
        C("golden-run: bad regex offline judge", "golden-run.py",
          ["--set", tmp / "badregex.json", "--offline"], 2, want=("bad accept rule",)),
        C("golden-run: no accept key", "golden-run.py", ["--set", tmp / "noaccept.json", "--offline"], 2,
          want=("no accept rules",)),
        C("golden-run: LLM conn refused", "golden-run.py",
          ["--set", tmp / "ok.json", "--llm-url", "http://localhost:1/v1", "--timeout", "3"], 2,
          want=("LLM call failed",)),
        # --- verify-runner ---
        C("verify-runner: bad JSON config", "verify-runner.py", ["--config", tmp / "bad.json"], 2,
          want=("invalid JSON",)),
        C("verify-runner: cmd not found", "verify-runner.py",
          ["--json", "--cmd", "definitely-not-a-real-cmd-xyz"], 2, want=("exit_code", "127")),
        C("verify-runner: passing cmd", "verify-runner.py",
          ["--cmd", PY, "-c", "print('ok')"], 0, want=("ALL PASS",)),
        # --- verify-runner: layered + diagnostic.v1 (v2.0.0, T6/T7) ---
        C("verify-runner: layers all pass", "verify-runner.py",
          ["--config", tmp / "layers-ok.json"], 0, want=("ALL PASS",)),
        C("verify-runner: layers short-circuit", "verify-runner.py",
          ["--config", tmp / "layers-fail.json"], 2, want=("short-circuit",)),
        C("verify-runner: layers missing cmd", "verify-runner.py",
          ["--config", tmp / "layers-bad.json"], 2, want=("missing 'cmd'",)),
        C("verify-runner: diagnostic schema in json", "verify-runner.py",
          ["--json", "--cmd", PY, "-c", "print('ok')"], 0, want=('"schema": "diagnostic.v1"',)),
        # --- task-state (v2.0.0, T5) ---
        C("task-state: --help", "task-state.py", ["--help"], 0, want=("usage",)),
        C("task-state: legal transition", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ok", "--to", "UNDERSTAND",
           "--verdict", "SUCCESS"], 0, want=("UNDERSTAND",)),
        C("task-state: illegal transition", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ok", "--to", "DONE"], 2,
          want=("illegal transition",)),
        C("task-state: missing task", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-missing", "--to", "UNDERSTAND"], 2,
          want=("task not found",)),
        C("task-state: duplicate init", "task-state.py",
          ["--tasks-dir", tasks_dir, "init", "--task", "t-ok", "--title", "dup"], 2,
          want=("already exists",)),
        C("task-state: invalid verdict", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ok", "--to", "UNDERSTAND",
           "--verdict", "BOGUS"], 2, want=("invalid choice",)),
        C("task-state: bad JSON task file", "task-state.py",
          ["--tasks-dir", tasks_dir, "trace-export", "--task", "t-bad"], 2, want=("invalid JSON",)),
        C("task-state: validate ok", "task-state.py",
          ["--tasks-dir", tasks_dir, "validate", "--task", "t-ok"], 0, want=("valid",)),
        # --- router-stats (v2.2.0, T8) ---
        C("router-stats: --help", "router-stats.py", ["--help"], 0, want=("usage",)),
        C("router-stats: init", "router-stats.py", ["init", "--db", tmp / "rs.db"], 0, want=("created",)),
        C("router-stats: invalid outcome", "router-stats.py",
          ["record", "--db", tmp / "rs.db", "--cell", "bug_fix", "--model", "m1", "--outcome", "nope"], 2,
          want=("invalid outcome",)),
        C("router-stats: record pass", "router-stats.py",
          ["record", "--db", tmp / "rs.db", "--cell", "bug_fix", "--model", "deepseek-v4",
           "--outcome", "pass", "--tokens", "100", "--cost", "0.001"], 0, want=("recorded",)),
        C("router-stats: recommend with data", "router-stats.py",
          ["recommend", "--db", tmp / "rs.db", "--cell", "bug_fix"], 0, want=("deepseek-v4",)),
        C("router-stats: recommend empty db", "router-stats.py",
          ["recommend", "--db", tmp / "empty2.db", "--cell", "bug_fix"], 0, want=('"no_data": true',)),
        C("router-stats: report empty db", "router-stats.py",
          ["report", "--db", tmp / "empty2.db", "--json"], 0, want=('"records": 0',)),
        C("router-stats: corrupt db", "router-stats.py",
          ["record", "--db", tmp / "corrupt.db", "--cell", "x", "--model", "m1", "--outcome", "pass"], 2,
          want=("database error",)),
        # --- case-search --layer (v2.2.0, T9) ---
        C("case-search: layer hit", "case-search.py",
          ["--q", "verify-runner", "--layer", "solutions", "--dir", mem_dir, "--json"], 0,
          want=("results",)),
        C("case-search: layer nonexistent", "case-search.py",
          ["--q", "x", "--layer", "nope", "--dir", mem_dir], 0, want=("no match",)),
        # --- token-meter budget (v2.2.0, T10) ---
        # F-50：原用例名"budget exceeded"却 expect 0 —— 用例按错误的既成行为写的，
        # 把"永不拦截"固化为契约。现超预算必须 exit 2。
        C("token-meter: 超预算 → 拦截 exit 2（F-50）", "token-meter.py",
          ["--log", tmp / "many.jsonl", "--budget", '{"max_calls":10}', "--json"], 2,
          want=("exceeded", "ESCALATED")),
        C("token-meter: budget ok", "token-meter.py",
          ["--log", tmp / "many.jsonl", "--budget", '{"max_calls":100}', "--json"], 0,
          want=('"exceeded": false',), dont=('"exceeded": true',)),
        C("token-meter: 不传 --budget 仅计量 → exit 0（不受影响）", "token-meter.py",
          ["--log", tmp / "many.jsonl", "--json"], 0, want=("records",)),
        # --- golden-run --record feedback loop (v2.2.0, T11) ---
        C("golden-run: record outcomes", "golden-run.py",
          ["--offline", "--set", tmp / "ok.json", "--record", tmp / "rec.db"], 0, want=("[record]",)),
        # NOTE: 用 rs.db（同组前序用例自己写入），**不要**用 golden-run 组写的 rec.db ——
        # pre-commit 门禁是 `robustness --only <script>` 逐脚本跑的，跨组依赖会让
        # 子集必然失败（此前 --only router-stats 恒 16/17）。回归用例必须自洽。
        C("router-stats: report with data", "router-stats.py",
          ["report", "--db", tmp / "rs.db", "--json"], 0, want=('"pass": 1',)),
        # --- bump-version guards (v1.14.1) ---
        C("bump-version: invalid version", "bump-version.py", ["vX"], 1, want=("invalid version",)),
        C("bump-version: old==new abort", "bump-version.py", ["--apply", "v9.9.9", "--old", "v9.9.9"], 1,
          want=("nothing to bump",)),
        # --- error-sig / case-search / env-snapshot ---
        C("error-sig: match missing store", "error-sig.py",
          ["match", "--text", "x", "--store", tmp / "nosigs.json"], 2, want=("store not found",)),
        C("case-search: nonexistent dir", "case-search.py", ["--q", "x", "--dir", tmp / "nodir"], 0),
        C("env-snapshot: missing log (json)", "env-snapshot.py",
          ["--log", tmp / "nope.log", "--json"], 0, want=("not found",)),
        # --- token-meter / review-prefilter ---
        C("token-meter: empty file", "token-meter.py", ["--log", tmp / "empty.log"], 0, want=("no records",)),
        C("token-meter: garbage lines", "token-meter.py", ["--log", tmp / "garbage.jsonl"], 0, want=("records",)),
        C("review-prefilter: non-git dir", "review-prefilter.py",
          ["--base", "HEAD", "--cwd", str(tmp)], 0, want=("Not a git repository",)),
        C("review-prefilter: 检查失败 → 拦截 exit 2（负向覆盖）", "review-prefilter.py",
          ["--base", "HEAD", "--cwd", str(tmp), "--config", tmp / "review-fail.json", "--json"],
          2, want=('"blockers": true',)),
        C("review-prefilter: 检查通过 → exit 0", "review-prefilter.py",
          ["--base", "HEAD", "--cwd", str(tmp), "--config", tmp / "review-pass.json", "--json"],
          0, want=('"blockers": false',)),
        # --- probe-tools (isolated copy, no manifest) / toolstack gate ---
        {"name": "probe-tools: missing manifest", "script": "probe-tools.py",
         "cmd": [PY, str(isolated / "probe-tools.py")], "expect": 1, "expect_any": (1,),
         "want": ("manifest not found",), "dont": ("Traceback",)},
        C("toolstack-pipeline: push non-TTY", "toolstack-pipeline.py", ["--push"], 0,
          want=("skip",), expect_any=(0, 2)),
        C("toolstack-pipeline: 数据 SHA256 漂移 → exit 2（负向覆盖）", "toolstack-pipeline.py",
          ["--manifest", tmp / "toolstack-drift.json"], 2, want=("MISMATCH",), timeout=60),
        # --- mutation-audit (v2.10.3): 变异测试审计自身 ---
        C("mutation-audit: --only 未知脚本 → exit 2（不能静默通过）", "mutation-audit.py",
          ["--only", "no-such.py"], 2, want=("no mutation defined",), timeout=120),
        C("mutation-audit: --dry-run 仅校验锚点 → exit 0", "mutation-audit.py",
          ["--dry-run", "--only", "patch-gate.py"], 0, want=("anchor OK",), timeout=120),
        # --- privacy-scan (v1.16.0) ---
        C("privacy-scan: clean dir", "privacy-scan.py", [tmp / "clean"], 0, want=("CLEAN",)),
        C("privacy-scan: leak detection", "privacy-scan.py", [tmp / "leak"], 2,
          want=("blocker",)),
        C("privacy-scan: nonexistent dir", "privacy-scan.py", [tmp / "nodir"], 2,
          want=("not a directory",)),
        # --- v2.7.1 F-15: host runtime dirs excluded by default ---
        C("privacy-scan: host runtime 目录默认排除", "privacy-scan.py",
          [tmp / "polluted"], 0, want=("CLEAN",)),
        C("privacy-scan: --include-runtime 仍报", "privacy-scan.py",
          [tmp / "polluted", "--include-runtime"], 2, want=("drive-letter",)),
        # --- git hooks gate (v2.4.0, P0-1) ---
        C("install-hooks: install", "install-hooks.py", ["--repo", repo_dir], 0, want=("installed",)),
        C("install-hooks: idempotent", "install-hooks.py", ["--repo", repo_dir], 0, want=("already",)),
        # 负向覆盖：外来钩子未加 --force 必须拒绝（此前 3 条用例全是 expect=0）
        C("install-hooks: 外来钩子无 --force → 拒（exit 1）", "install-hooks.py",
          ["--repo", repo3], 1, want=("foreign hook",)),
        C("git-pre-commit: docs-only skip", "git-pre-commit.py",
          ["--dry-run", "--changed", "README.md"], 0, want=("skip",)),
        C("git-pre-commit: changed script gate", "git-pre-commit.py",
          ["--dry-run", "--changed", "user-vibe_coding-sdk-moe/scripts/token-meter.py"], 0,
          want=("PASS",), timeout=180),  # F-40：门禁内部递归跑 robustness 子集，夹具搭建在慢盘上可超 60s
        # --- v2.10.0: F-41 治本 —— SDK 内文档也过 privacy 闸 ---
        C("git-pre-commit: docs 触发 privacy 闸（F-41）", "git-pre-commit.py",
          ["--dry-run", "--changed", "user-vibe_coding-sdk-moe/ALIGNMENT.md"], 0,
          want=("privacy-scan", "PASS")),
        # --- C0-2 (v2.4.1): renamed-dir runtime derivation (F2) ---
        {"name": "git-pre-commit: renamed-dir gate", "script": "git-pre-commit.py",
         "cmd": [PY, str(renamed_sdk / "git-pre-commit.py"), "--dry-run", "--changed",
                 "renamed-sdk/scripts/token-meter.py"],
         "expect": 0, "want": ("PASS", "SKIPPED"), "dont": ("Traceback",), "timeout": 180},
        {"name": "install-hooks: renamed-dir relpath", "script": "install-hooks.py",
         "cmd": [PY, str(renamed_sdk / "install-hooks.py"), "--repo", repo2],
         "expect": 0, "want": ("installed", "renamed-sdk/scripts/git-pre-commit.py"),
         "dont": ("Traceback",)},
        # --- C0-4 (v2.4.1): data-file gate (F3) ---
        C("git-pre-commit: data json valid", "git-pre-commit.py",
          ["--dry-run", "--changed", tmp / "baseline-tmp.json"], 0, want=("PASS",)),
        C("git-pre-commit: data bad json blocked", "git-pre-commit.py",
          ["--dry-run", "--changed", tmp / "golden-set-bad.json"], 1,
          want=("invalid JSON", "BLOCKED")),
        C("git-pre-commit: golden-set validate", "git-pre-commit.py",
          ["--dry-run", "--changed", tmp / "golden-set-ok.json"], 0, want=("PASS",)),
        # --- C1-1 (v2.5.0): task-workspace Execution Plane ---
        C("task-workspace: create basic", "task-workspace.py",
          ["--dir", ws_root, "create", "--task", "t-ws1"], 0, want=("created",)),
        C("task-workspace: create worktree", "task-workspace.py",
          ["--dir", ws_root, "create", "--task", "t-ws2", "--worktree", ws_repo], 0,
          want=("worktree",)),
        C("task-workspace: verify worktree", "task-workspace.py",
          ["--dir", ws_root, "verify", "--task", "t-ws2", "--worktree-repo", ws_repo], 0,
          want=("valid",)),
        C("task-workspace: cleanup refuse no marker", "task-workspace.py",
          ["--dir", ws_root, "cleanup", "--task", "t-nomarker"], 2, want=("refuse",)),
        # --- C1-2 (v2.5.0): task-state production fields + run records ---
        C("task-state: init production fields", "task-state.py",
          ["--tasks-dir", tasks_dir, "init", "--task", "t-new", "--title", "prod",
           "--priority", "P1", "--acceptance", "all green", "--branch", "feat/x"], 0,
          want=("priority",)),
        C("task-state: transition run record", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-run", "--to", "UNDERSTAND",
           "--run-id", "12345", "--pr", "42", "--attempt", "1"], 0,
          want=("workflow_run_id",)),
        C("task-state: validate bad priority", "task-state.py",
          ["--tasks-dir", tasks_dir, "validate", "--task", "t-badprio"], 2,
          want=("invalid priority",)),
        # --- C1-3 (v2.5.0): CI/deploy state machine ---
        C("task-state: VERIFY->CI_QUEUED", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ci", "--to", "CI_QUEUED"], 0,
          want=("CI_QUEUED",)),
        C("task-state: CI_RUNNING->CI_PASSED", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ci-running",
           "--to", "CI_PASSED"], 0, want=("CI_PASSED",)),
        C("task-state: CI_RUNNING->CI_FAILED", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ci-failing",
           "--to", "CI_FAILED"], 0, want=("CI_FAILED",)),
        C("task-state: CI_FAILED->REPAIRING", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ci-failed",
           "--to", "REPAIRING"], 0, want=("REPAIRING",)),
        C("task-state: CI_PASSED->DONE illegal", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-ci-passed",
           "--to", "DONE"], 2, want=("illegal transition",)),
        C("task-state: PROD_VERIFY->DONE", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-prod", "--to", "DONE"], 0,
          want=("DONE",)),
        # --- C1-4 (v2.5.0): ci-fail-analyze ---
        C("ci-fail-analyze: unit failure", "ci-fail-analyze.py",
          ["--log", tmp / "unit.log", "--json"], 0,
          want=("unit_failure", "diagnostic.v1")),
        C("ci-fail-analyze: timeout", "ci-fail-analyze.py",
          ["--log", tmp / "timeout.log"], 0, want=("timeout",)),
        C("ci-fail-analyze: missing log", "ci-fail-analyze.py",
          ["--log", tmp / "nope.log"], 2, want=("not found",)),
        C("ci-fail-analyze: install error beats failed", "ci-fail-analyze.py",
          ["--log", tmp / "install.log", "--json"], 0,
          want=("install_error",), dont=("unit_failure",)),
        # --- C2-3 (v2.6.0): gh-workflow-check control-plane contract ---
        C("gh-workflow-check: sdk .github OK", "gh-workflow-check.py",
          ["--gh-dir", SCRIPT_DIR.parent / ".github"], 0, want=("OK",)),
        C("gh-workflow-check: missing dir", "gh-workflow-check.py",
          ["--gh-dir", tmp / "no-gh"], 2, want=("not found",)),
        C("gh-workflow-check: empty dir blocked", "gh-workflow-check.py",
          ["--gh-dir", tmp / "empty-gh"], 2, want=("missing workflows/",)),
        # --- C2-4 (v2.6.0): spec-tasks-import ---
        C("spec-tasks-import: parse and write", "spec-tasks-import.py",
          ["--tasks", tmp / "tasks.md", "--tasks-dir", tmp / "spec-tasks"], 0,
          want=("T-001", "T-002")),
        C("spec-tasks-import: missing tasks.md", "spec-tasks-import.py",
          ["--tasks", tmp / "nope.md", "--tasks-dir", tmp / "spec-tasks"], 2,
          want=("not found",)),
        C("spec-tasks-import: empty tasks list", "spec-tasks-import.py",
          ["--tasks", tmp / "tasks-empty.md", "--tasks-dir", tmp / "spec-tasks"], 2,
          want=("no '- [ ]'",)),
        # --- v2.7.0: F-01 基础设施失败不进能力后验 ---
        C("router-stats v2: record pass (seed)", "router-stats.py",
          ["record", "--db", tmp / "rs2.db", "--cell", "qa", "--model", "m1",
           "--outcome", "pass", "--tokens", "500", "--cost", "0.001"], 0, want=("recorded",)),
        C("router-stats v2: record infra_fail", "router-stats.py",
          ["record", "--db", tmp / "rs2.db", "--cell", "qa", "--model", "m1",
           "--outcome", "infra_fail", "--error-class", "empty", "--response-tokens", "7",
           "--tokens", "7"], 0, want=("infra_fail",)),
        C("router-stats v2: invalid error_class", "router-stats.py",
          ["record", "--db", tmp / "rs2.db", "--cell", "qa", "--model", "m1",
           "--outcome", "infra_fail", "--error-class", "bogus"], 2, want=("invalid error_class",)),
        C("router-stats v2: report 分离 infra（后验不被污染）", "router-stats.py",
          ["report", "--db", tmp / "rs2.db", "--json"], 0,
          want=('"infra_fail": 1', '"capability_trials": 1')),
        C("router-stats v2: snapshot 冻结先验", "router-stats.py",
          ["snapshot", "--db", tmp / "rs2.db"], 0, want=("frozen_cells",)),
        # --- v2.7.0: F-01 数据修复 rebuild ---
        C("router-stats v2: seed 低 token fail", "router-stats.py",
          ["record", "--db", tmp / "rs3.db", "--cell", "qa", "--model", "m1",
           "--outcome", "fail", "--tokens", "10"], 0, want=("recorded",)),
        C("router-stats v2: rebuild retag", "router-stats.py",
          ["rebuild", "--db", tmp / "rs3.db", "--retag-threshold", "50", "--no-backup"], 0,
          want=("retagged_rows",)),
        # --- v2.7.0: F-11 coverage ---
        C("router-stats v2: coverage 输出", "router-stats.py",
          ["report", "--db", tmp / "rs3.db", "--golden-set",
           SCRIPT_DIR / "data" / "golden-set-v3.json", "--json"], 0, want=('"coverage"',)),
        # --- v2.7.1 F-17: legacy NULL 行迁移回填 ---
        C("router-stats v2: legacy NULL 行回填", "router-stats.py",
          ["report", "--db", tmp / "legacy.db", "--json"], 0,
          want=('"unclassified_fail_rows": 0',)),
        C("router-stats v2: 回填后 retag 按 COALESCE 生效", "router-stats.py",
          ["rebuild", "--db", tmp / "legacy.db", "--retag-threshold", "50",
           "--no-backup"], 0, want=('"retagged_rows": 1',)),
        # --- v2.7.0: T-06 diff-risk 三档闸门 ---
        C("diff-risk: auto band", "diff-risk.py",
          ["--files", "docs/x.md", "--lines", "5", "--json"], 0, want=('"band": "auto"',)),
        C("diff-risk: review band", "diff-risk.py",
          ["--files", "scripts/foo.py", "--lines", "100", "--json"], 0, want=('"band": "review"',)),
        C("diff-risk: human gate 硬闸 exit=2", "diff-risk.py",
          ["--files", "scripts/a.py,scripts/b.py", "--lines", "600",
           "--known-failures", '["scripts/a.py"]', "--error-class", "quality", "--json"], 2,
          want=('"band": "human"',)),
        C("diff-risk: 无 diff 源 fail-closed", "diff-risk.py", ["--json"], 2,
          want=("no diff source",)),
        # --- v2.7.0: T-07 verify-runner allow_missing ---
        C("verify-runner: allow_missing 跳过缺失工具", "verify-runner.py",
          ["--config", tmp / "layers-missing.json", "--json"], 0, want=("skipped",)),
        # --- v2.7.0: T-09 修复预算 / 振荡闸门 ---
        C("task-state: 修复预算硬闸", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-budget", "--to", "REPAIR"], 2,
          want=("budget exhausted",)),
        C("task-state: 振荡检测硬闸", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-loop", "--to", "REPAIR"], 2,
          want=("oscillation",)),
        # --- v2.7.0: T-08 WAITING / CRASHED / checkpoint ---
        C("task-state: WAITING 可恢复", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-waiting", "--to", "IMPLEMENT"], 0,
          want=("IMPLEMENT",)),
        C("task-state: 手动 checkpoint", "task-state.py",
          ["--tasks-dir", tasks_dir, "checkpoint", "--task", "t-waiting",
           "--context-pointer", "sess:turn-9"], 0, want=("checkpoint",)),
        C("task-state: resume 恢复 checkpoint", "task-state.py",
          ["--tasks-dir", tasks_dir, "resume", "--task", "t-crashed"], 0,
          want=("restored_from_checkpoint", "VERIFY")),
        C("task-state: 无 checkpoint 的 resume 被拒", "task-state.py",
          ["--tasks-dir", tasks_dir, "resume", "--task", "t-nocp"], 2, want=("resume target",)),
        # --- v2.7.0: T-14 DAG 依赖 ---
        C("task-state: 依赖未完成禁止开工", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-dep", "--to", "IMPLEMENT"], 2,
          want=("blocked by dependencies",)),
        C("task-state: 依赖已完成放行", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-depok", "--to", "IMPLEMENT"], 0,
          want=('"ready": true',)),
        # --- v2.7.0: F-02 成本实算 ---
        C("golden-run: cost 实算（有价格表）", "golden-run.py",
          ["--offline", "--set", tmp / "ok.json", "--record", tmp / "cost.db",
           "--price-per-1k", "0.002", "--json"], 0, want=('"cost_basis": "flat"',)),
        C("golden-run: 无价格表显式标注 none", "golden-run.py",
          ["--offline", "--set", tmp / "ok.json", "--json"], 0, want=('"cost_basis": "none"',)),
        # F-01 回归：usage 虚报 2048 但文本为空 → empty（infra），不进 quality。
        # 样本必失败（contains 不匹配）→ exit 2 属预期，断言的是分类正确。
        C("golden-run: usage 虚报仍判 empty", "golden-run.py",
          ["--offline", "--set", tmp / "empty-usage.json", "--json"], 2,
          want=('"empty": 1', '"infra_failures": 1'),
          dont=('"quality": 1',)),
        # --- v2.7.0: T-15 体积同步 ---
        C("bump-version: --sync-size 独立模式", "bump-version.py", ["--sync-size"], 0,
          want=("size sync", "实测")),
        # --- v2.8.0: T-07 置信度自适应验证深度 ---
        C("verify-runner: confidence 0.9 light", "verify-runner.py",
          ["--config", tmp / "conf-layers.json", "--confidence", "0.9"], 0,
          want=("[depth] light",), dont=("test-full",)),
        C("verify-runner: confidence 0.5 medium", "verify-runner.py",
          ["--config", tmp / "conf-layers.json", "--confidence", "0.5"], 0,
          want=("[depth] medium", "typecheck"), dont=("test-full",)),
        C("verify-runner: confidence 0.2 full", "verify-runner.py",
          ["--config", tmp / "conf-layers.json", "--confidence", "0.2"], 0,
          want=("[depth] full", "test-full")),
        C("verify-runner: confidence 越界拒绝", "verify-runner.py",
          ["--config", tmp / "conf-layers.json", "--confidence", "1.5"], 2,
          want=("within [0, 1]",)),
        C("verify-runner: layers 显式优先于 confidence", "verify-runner.py",
          ["--config", tmp / "conf-layers.json", "--layers", "syntax", "--confidence", "0.2"], 0,
          want=("explicit",)),
        # --- v2.8.2: T-17 security 层恒保（F-27：轻/中档曾剔除安全扫描）---
        C("verify-runner: security 恒保（0.9 light）", "verify-runner.py",
          ["--config", tmp / "conf-sec.json", "--confidence", "0.9"], 0,
          want=("[depth] light", "security"), dont=("test-full",)),
        C("verify-runner: security 恒保（0.5 medium）", "verify-runner.py",
          ["--config", tmp / "conf-sec.json", "--confidence", "0.5"], 0,
          want=("[depth] medium", "security", "typecheck"), dont=("test-full",)),
        C("verify-runner: 无 security 配置时不虚增层", "verify-runner.py",
          ["--config", tmp / "conf-layers.json", "--confidence", "0.9"], 0,
          want=("[depth] light",), dont=("security", "test-full")),
        # --- v2.9.0: T-18 随包预设 targeted 分支可达（F-28 死代码修复）---
        C("verify-runner: 随包预设 targeted 可达（conf 0.9）", "verify-runner.py",
          ["--config", str(SCRIPT_DIR / "presets" / "verify.python.json"),
           "--cwd", str(tmp / "empty-cwd"), "--confidence", "0.9", "--json"], 0,
          want=("test-targeted", "security"), dont=("test-full",)),
        C("verify-runner: 随包预设 full 档含 test-full（conf 0.2）", "verify-runner.py",
          ["--config", str(SCRIPT_DIR / "presets" / "verify.python.json"),
           "--cwd", str(tmp / "empty-cwd"), "--confidence", "0.2", "--json"], 0,
          want=("test-full", "security")),
        C("verify-runner: --layers 别名匹配 typecheck（T-18 显式别名表）", "verify-runner.py",
          ["--config", tmp / "conf-layers.json", "--layers", "type", "--json"], 0,
          want=("typecheck",)),
        # --- v2.9.0: T-22 测试选择（--changed 约定映射，fail-open）---
        C("verify-runner: --changed 映射注入 test-targeted", "verify-runner.py",
          ["--config", tmp / "sel-verify.json", "--cwd", str(tmp / "sel-src"),
           "--changed", "src/foo.py,src/sub/bar.py", "--json"], 0,
          want=('"matched_tests"', "tests/test_foo.py", "tests/test_bar.py")),
        C("verify-runner: --changed 无映射 fail-open（原 cmd 保持）", "verify-runner.py",
          ["--config", tmp / "sel-verify.json", "--cwd", str(tmp / "sel-src"),
           "--changed", "src/zzz_none.py", "--json"], 0,
          want=('"matched_tests": []',)),
        C("verify-runner: --changed 变更即测试 → 直接收录", "verify-runner.py",
          ["--config", tmp / "sel-verify.json", "--cwd", str(tmp / "sel-src"),
           "--changed", "tests/test_bar.py", "--json"], 0,
          want=("tests/test_bar.py",)),
        # --- v2.8.2: T-16 version-check（F-26 门禁上移）---
        C("version-check: 一致 → 放行", "version-check.py",
          ["--root", tmp / "vc-ok", "--json"], 0, want=('"ok": true',)),
        C("version-check: CHANGELOG 顺序倒置 → 拒", "version-check.py",
          ["--root", tmp / "vc-badorder", "--json"], 2, want=("order violation",)),
        C("version-check: 版本串失配 → 拒", "version-check.py",
          ["--root", tmp / "vc-badver", "--json"], 2, want=("version mismatch",)),
        # --- v2.8.0: T-08 完成条件闸 + T-10 事件台账 ---
        C("task-state: FINALIZE→DONE 无证据拒绝", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-done1", "--to", "DONE"], 2,
          want=("--done-evidence",)),
        C("task-state: FINALIZE→DONE 证据放行", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-done1", "--to", "DONE",
           "--done-evidence", "112/112 suite green"], 0, want=('"ok": true', "done_gate")),
        C("task-state: trace-export 读事件台账", "task-state.py",
          ["--tasks-dir", tasks_dir, "trace-export", "--task", "t-done1"], 0,
          want=("events:", "transition")),
        # --- v2.8.0: T-09 故障分类 +3 ---
        C("ci-fail-analyze: permission", "ci-fail-analyze.py",
          ["--log", tmp / "perm.log"], 0, want=("permission",)),
        C("ci-fail-analyze: dependency", "ci-fail-analyze.py",
          ["--log", tmp / "dep.log"], 0, want=("dependency",)),
        C("ci-fail-analyze: assertion (jest)", "ci-fail-analyze.py",
          ["--log", tmp / "assertj.log"], 0, want=("assertion",)),
        # --- v2.9.0: T-19 origin class（F-30：origin 而非 leaf 决定动作）---
        C("ci-fail-analyze: origin infra 信号覆盖（dependency+网络指纹 → RETRY）", "ci-fail-analyze.py",
          ["--log", tmp / "dep-infra.log", "--json"], 0,
          want=('"origin": "infra"', '"recommended_action": "RETRY"')),
        C("ci-fail-analyze: origin test（fixture 未找到 → REPAIR_TEST）", "ci-fail-analyze.py",
          ["--log", tmp / "test-fixture.log", "--json"], 0,
          want=('"origin": "test"', '"REPAIR_TEST"')),
        C("ci-fail-analyze: origin environment（permission → FIX_ENV）", "ci-fail-analyze.py",
          ["--log", tmp / "perm.log", "--json"], 0,
          want=('"origin": "environment"', '"FIX_ENV"')),
        C("ci-fail-analyze: origin unknown → DIAGNOSE（不直接进修复环）", "ci-fail-analyze.py",
          ["--log", tmp / "unclass.log", "--json"], 0,
          want=('"origin": "unknown"', '"DIAGNOSE"')),
        # --- v2.9.0: T-20 flaky-check（F-31：单次失败不足证据；--json 必须在 --cmd 前）---
        C("flaky-check: 全失败 → REAL", "flaky-check.py",
          ["--runs", "3", "--json", "--cmd", PY, "-c", "import sys; sys.exit(3)"], 0,
          want=('"verdict": "REAL"', '"REPAIR"')),
        C("flaky-check: 全通过 → NOT_REPRODUCIBLE（fail-closed 不跳过验证）", "flaky-check.py",
          ["--runs", "3", "--json", "--cmd", PY, "-c", "pass"], 0,
          want=('"verdict": "NOT_REPRODUCIBLE"', '"TREAT_AS_UNKNOWN"')),
        C("flaky-check: 混合 N=5 → FLAKY quarantine", "flaky-check.py",
          ["--runs", "5", "--json", "--cwd", str(tmp), "--cmd", PY, str(tmp / "flaky-toggle.py")], 0,
          want=('"verdict": "FLAKY"', '"QUARANTINE"')),
        C("flaky-check: 混合 N<5 → UNKNOWN fail-closed 视同 REAL", "flaky-check.py",
          ["--runs", "2", "--json", "--cwd", str(tmp), "--cmd", PY, str(tmp / "flaky-toggle.py")], 0,
          want=('"verdict": "UNKNOWN"', '"TREAT_AS_REAL"')),
        C("flaky-check: 失败全带 infra 指纹 → INFRA RETRY", "flaky-check.py",
          ["--runs", "5", "--json", "--cwd", str(tmp), "--cmd", PY, str(tmp / "flaky-infra.py")], 0,
          want=('"verdict": "INFRA"', '"RETRY"')),
        C("flaky-check: runs<2 用法拒绝", "flaky-check.py",
          ["--runs", "1", "--json", "--cmd", PY, "-c", "pass"], 2, want=("must be >= 2",)),
        # --- v2.9.0: T-21 regression-guard（F-32：pre-FAIL / post-PASS 双向闸）---
        C("regression-guard: base FAIL + head PASS → VALID", "regression-guard.py",
          ["--cwd", str(tmp / "rg-valid"), "--base", "HEAD~1", "--json",
           "--test", PY, "tests/test_x.py"], 0,
          want=('"verdict": "VALID_REGRESSION_TEST"', '"ok_as_expected": true')),
        C("regression-guard: 两边都过 → WEAK_TEST 拒（自证式弱测试）", "regression-guard.py",
          ["--cwd", str(tmp / "rg-weak"), "--base", "HEAD~1", "--json",
           "--test", PY, "tests/test_x.py"], 2,
          want=('"verdict": "WEAK_TEST"', "proves nothing")),
        C("regression-guard: 两边都挂 → FIX_INCOMPLETE 拒", "regression-guard.py",
          ["--cwd", str(tmp / "rg-incomplete"), "--base", "HEAD~1", "--json",
           "--test", PY, "tests/test_x.py"], 2,
          want=('"verdict": "FIX_INCOMPLETE"',)),
        C("regression-guard: 缺 --test 拒", "regression-guard.py",
          ["--cwd", str(tmp / "rg-valid"), "--base", "HEAD~1", "--json"], 2,
          want=("--test required",)),
        # --- v2.10.0: T-23 patch-gate（F-29 补丁规模预算，kernel §I）---
        C("patch-gate: numstat 预算内 → 放行", "patch-gate.py",
          ["--numstat-file", tmp / "p2-numstat.txt", "--json"], 0, want=('"ok": true',)),
        C("patch-gate: 超 files/lines 预算 → exit2 ESCALATED", "patch-gate.py",
          ["--numstat-file", tmp / "p2-numstat-bad.txt", "--json"], 2,
          want=('"recommended_action": "ESCALATED"',)),
        C("patch-gate: 依赖清单超 1 → 拒", "patch-gate.py",
          ["--numstat-file", tmp / "p2-numstat-deps.txt", "--json"], 2,
          want=("dependency manifests",)),
        C("patch-gate: 缺 diff 源 fail-closed", "patch-gate.py", ["--json"], 2,
          want=("no diff source",)),
        # F-53：畸形 numstat → 干净拦截（报行号，exit 2），不得裸 traceback
        C("patch-gate: 畸形 numstat 行 → exit2 非 traceback", "patch-gate.py",
          ["--numstat-file", tmp / "p2-numstat-malformed.txt", "--json"], 2,
          want=("malformed numstat line",)),
        # --- v2.10.0: T-23b diff-risk repair_confidence 合成（B.21）---
        C("diff-risk: repair_confidence 合成（vc=0.9 低风险）", "diff-risk.py",
          ["--files", "docs/x.md", "--lines", "5", "--verify-confidence", "0.9", "--json"], 0,
          want=('"repair_confidence"', '"human_review_required": false')),
        C("diff-risk: repair_confidence 低 → 需人工", "diff-risk.py",
          ["--files", "scripts/a.py", "--lines", "200", "--verify-confidence", "0.4", "--json"], 0,
          want=('"human_review_required": true',)),
        # --- v2.10.0: T-25 action-gate（F-38 Action Validator / F-35 idempotent 首个消费方）---
        C("action-gate: alias 命中 tier1 → ALLOW", "action-gate.py",
          ["--tool", "ocr", "--json"], 0,
          want=('"decision": "ALLOW"', '"open-code-review (ocr)"', '"idempotent": true')),
        C("action-gate: 未知工具 → DENY", "action-gate.py",
          ["--tool", "no-such-tool-xyz", "--json"], 2,
          want=('"decision": "DENY"', "not in toolstack")),
        C("action-gate: args 非法 JSON → DENY", "action-gate.py",
          ["--tool", "ocr", "--args-json", "{bad", "--json"], 2, want=('"decision": "DENY"',)),
        C("action-gate: tier3 → 放行但附强制条件", "action-gate.py",
          ["--tool", "strix", "--json"], 0,
          want=('"decision": "ALLOW"', "rollback validated")),
        # --- v2.10.0: T-26 task-state 幂等键（F-35：重试/重放不得双执行）---
        C("task-state: 幂等键首次应用", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-idem", "--to", "IMPLEMENT",
           "--idempotency-key", "k1"], 0, want=('"to": "IMPLEMENT"',)),
        C("task-state: 同键重放 → no-op（不耗修复预算）", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-idem", "--to", "IMPLEMENT",
           "--idempotency-key", "k1"], 0, want=('"duplicate": true',)),
        C("task-state: 同键换目标 → 拒（caller bug）", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-idem", "--to", "VERIFY",
           "--idempotency-key", "k1"], 2, want=("already used for",)),
        # --- v2.10.0: T-24 escalation-pack（F-34 七字段升级包）---
        C("task-state: escalation-pack 七字段输出", "task-state.py",
          ["--tasks-dir", tasks_dir, "escalation-pack", "--task", "t-esc",
           "--failed-tests", "tests/test_x.py", "--json"], 0,
          want=('"schema": "escalation-pack.v1"', '"attempted_fixes"', '"relevant_diff"',
                '"recommended_action"')),
        C("task-state: FAILED verdict → 升级包建议 revert", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-esc", "--to", "REVIEW",
           "--verdict", "FAILED"], 0, want=('"to": "REVIEW"',)),
        C("task-state: escalation-pack 读到 FAILED → revert 建议", "task-state.py",
          ["--tasks-dir", tasks_dir, "escalation-pack", "--task", "t-esc", "--json"], 0,
          want=("reverting the last repair",)),
        # --- v2.10.1: F-42 回归 —— action-gate 必须认得自有脚本（原仅查 local_tools）---
        C("action-gate: 自有脚本 sdk_tools → ALLOW（F-42 回归）", "action-gate.py",
          ["--tool", "diff-risk.py", "--json"], 0,
          want=('"decision": "ALLOW"', '"toolstack_key": "diff-risk.py"')),
        C("action-gate: stem 匹配 diff-risk ≡ diff-risk.py（F-42）", "action-gate.py",
          ["--tool", "diff-risk", "--args-json", '{"files":"a.py"}', "--json"], 0,
          want=('"decision": "ALLOW"', '"tool": "diff-risk"')),
        # --- v2.10.1: F-44 回归 —— push 闸门有落点（tier-4 结构性人工）---
        C("action-gate: git-push tier4 → DENY（F-44 回归）", "action-gate.py",
          ["--tool", "git-push", "--json"], 2,
          want=('"decision": "DENY"', '"risk_tier": 4', "explicit human approval")),
        C("action-gate: git-push --user-approved → ALLOW（F-44）", "action-gate.py",
          ["--tool", "git-push", "--user-approved", "--json"], 0,
          want=('"decision": "ALLOW"', "human approval recorded")),
        # --- v2.10.1: F-47 回归 —— --json 不得吞掉 --apply（dry-run 契约显式化）---
        C("bump-version: --json 无 --apply → dry_run 显式表态（F-47 回归）", "bump-version.py",
          ["v9.9.9", "--json"], 0,
          want=('"applied": false', '"dry_run": true')),
        # --- v2.10.1: selfcheck-static 自身（sdk_tools 漂移哨兵）---
        C("selfcheck-static: 结构自检通过（frontmatter/refs/scripts/toolstack）",
          "selfcheck-static.py", [], 0,
          want=('"schema": "selfcheck-static.v1"', '"ok": true')),
        C("selfcheck-static: --quiet 仅退码不打印", "selfcheck-static.py",
          ["--quiet"], 0, want=()),
        # --- v2.10.2: F-43 回归 —— 未登记脚本必须拦（提交时刻 + 巡检两条线）---
        C("selfcheck-static: 未登记脚本 → exit 2（F-43 回归）", "selfcheck-static.py",
          ["--root", _sdk_tree("drift", register=False)], 2,
          want=("NOT in toolstack.json sdk_tools", "zz-probe.py")),
        C("selfcheck-static: --root 已登记树 → exit 0", "selfcheck-static.py",
          ["--root", _sdk_tree("clean", register=True)], 0,
          want=('"ok": true',)),
        # 不完整树必须 fail-closed 且不 traceback（C0-2 renamed-dir fixture 抓到）
        C("selfcheck-static: 不完整树 → exit 2 且不 traceback", "selfcheck-static.py",
          ["--root", tmp / "partial-sdk"], 2,
          want=("incomplete SDK tree",)),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK robustness regression suite")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", default=None, help="filter by script-name substring")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--timing", action="store_true",
                    help="T-16: 逐用例计时 + 按脚本聚合，定位慢点（全量 ~3min 的来源）")
    ap.add_argument("--timing-top", type=int, default=10, help="--timing 展示的最慢用例数")
    ap.add_argument("--quick", action="store_true",
                    help=f"T-16: 跳过慢脚本用例 {sorted(SLOW_SCRIPTS)}（pre-commit 子集用）")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="rob-suite-") as td:
        tmp = Path(td)
        cases = build_cases(tmp, only=args.only)
        if args.only:
            cases = [c for c in cases if args.only in c["script"]]
        skipped = 0
        if args.quick:
            kept = [c for c in cases if c["script"] not in SLOW_SCRIPTS]
            skipped = len(cases) - len(kept)
            cases = kept

        results = []
        for c in cases:
            t0 = time.monotonic()
            code, out = run_case(c["cmd"], timeout=c.get("timeout") or args.timeout)
            dur_ms = int((time.monotonic() - t0) * 1000)
            expect_ok = code == c["expect"] or (c.get("expect_any") and code in c["expect_any"])
            ok = expect_ok and all(w in out for w in c["want"]) and not any(d in out for d in c["dont"])
            results.append({"name": c["name"], "script": c["script"], "exit": code,
                            "expected": c["expect"], "ok": ok, "duration_ms": dur_ms})

        passed = sum(1 for r in results if r["ok"])
        total_ms = sum(r["duration_ms"] for r in results)
        report = {"time": now_iso(), "total": len(results), "passed": passed,
                  "pass_rate": round(passed / len(results), 3) if results else 0.0,
                  "duration_ms_total": total_ms, "skipped_quick": skipped,
                  "results": results}
        if args.timing:
            by_script: dict[str, dict] = {}
            for r in results:
                s = by_script.setdefault(r["script"], {"cases": 0, "ms": 0})
                s["cases"] += 1
                s["ms"] += r["duration_ms"]
            report["timing_by_script"] = dict(
                sorted(by_script.items(), key=lambda kv: -kv[1]["ms"]))
            report["timing_slowest"] = sorted(
                [{"name": r["name"], "script": r["script"], "ms": r["duration_ms"]}
                 for r in results], key=lambda x: -x["ms"])[:args.timing_top]

        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"== robustness-suite ({len(results)} cases, {total_ms}ms"
                  f"{f', skipped {skipped} (--quick)' if skipped else ''}) ==")
            for r in results:
                mark = "OK " if r["ok"] else "!! "
                tail = f" {r['duration_ms']}ms" if args.timing else ""
                print(f"  {mark}[{r['exit']}/{r['expected']}] {r['name']}{tail}")
            if args.timing:
                print("  -- 按脚本聚合（慢点定位） --")
                for s, v in report["timing_by_script"].items():
                    print(f"    {v['ms']:>7}ms  {s:<28} ({v['cases']} cases)")
            print(f"Verdict: {passed}/{len(results)} passed")

        return 0 if passed == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
