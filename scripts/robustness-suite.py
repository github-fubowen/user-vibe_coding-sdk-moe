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
import shutil
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


def run_case(cmd: list[str], timeout: int = 60,
             env_extra: dict | None = None) -> tuple[int, str]:
    """Run a case; returns (exit_code, combined_output). Never raises."""
    try:
        # Suite context is non-interactive by definition — declare it explicitly
        # (v2.7.1) so scripts with tty gates (e.g. toolstack-pipeline --push)
        # never block on input() even if the host's isatty() lies (ConPTY).
        env = dict(os.environ, SDK_NONINTERACTIVE="1")
        if env_extra:
            env.update(env_extra)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             stdin=subprocess.DEVNULL, env=env)
        out = (res.stdout or "") + (res.stderr or "")
        # R-3 debug aid: `ROBUST_DEBUG_OUT=<file>` appends every case's combined
        # output, so a red case can be diagnosed without re-plumbing the runner.
        _dbg = os.environ.get("ROBUST_DEBUG_OUT")
        if _dbg:
            with open(_dbg, "a", encoding="utf-8") as fh:
                fh.write(f"\n===== exit={res.returncode} cmd={' '.join(cmd[-4:])}\n{out[:4000]}\n")
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

    # token-meter 分类观测 fixture (R-7)：五类齐全 + 1 条漏标 + 1 条未知类
    (tmp / "cat.jsonl").write_text("".join(
        json.dumps(r, ensure_ascii=False) + "\n" for r in [
            {"model_id": "m1", "in_tokens": 1500, "out_tokens": 300, "category": "task"},
            {"model_id": "m1", "in_tokens": 9000, "out_tokens": 400, "category": "refs"},
            {"model_id": "m1", "in_tokens": 800, "out_tokens": 200, "category": "memory"},
            {"model_id": "m1", "in_tokens": 700, "out_tokens": 150, "category": "results"},
            {"model_id": "m1", "in_tokens": 500, "out_tokens": 100},
            {"model_id": "m1", "in_tokens": 400, "out_tokens": 100, "category": "bogus"},
        ]), encoding="utf-8")

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
    def _doc_root(name: str, skill_v: str, readme_v: str, heads: list,
                  eng_v: str | None = None, align_v: str | None = None) -> None:
        """T-16 文档根夹具。eng_v/align_v 为 None = 造"文件在但**没有戳**"的形态，
        用于验证 R-B1 的容错口径：缺戳 warning 不 fail、错戳 fail。"""
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
        (d / "ENGINEERING.md").write_text(
            f"> {eng_v} · 2026-09-01 · x\n" if eng_v else "# ENGINEERING\n\nno stamp here\n",
            encoding="utf-8")
        (d / "ALIGNMENT.md").write_text(
            f"> 吸收对象本体：`x`（{align_v}）\n" if align_v else "# ALIGNMENT\n\nno stamp\n",
            encoding="utf-8")

    _doc_root("ok", "v1.2.3", "v1.2.3", ["v1.2.3", "v1.2.2", "v1.2.1"],
              eng_v="v1.2.3", align_v="v1.2.3")
    _doc_root("badorder", "v1.2.3", "v1.2.3", ["v1.2.2", "v1.2.3"],
              eng_v="v1.2.3", align_v="v1.2.3")   # F-26 形态
    _doc_root("badver", "v1.2.3", "v1.2.2", ["v1.2.3"],
              eng_v="v1.2.3", align_v="v1.2.3")   # 版本串失配
    # T-511（F-60）：头部戳错 → fail；缺戳 → warning 不 fail
    _doc_root("badstamp-eng", "v1.2.3", "v1.2.3", ["v1.2.3"],
              eng_v="v1.2.0", align_v="v1.2.3")
    _doc_root("badstamp-align", "v1.2.3", "v1.2.3", ["v1.2.3"],
              eng_v="v1.2.3", align_v="v1.2.0")
    _doc_root("nostamp", "v1.2.3", "v1.2.3", ["v1.2.3"])
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
    # v2.10.6 fixtures（P3 清偿）：vk B.6 per-test / cicd §15 策略钉 / §29 跨版本对比
    (tmp / "p6-cifail.log").write_text(
        "pytest: 1 failed, 2 passed in 0.5s\nFAILED test_x.py::test_alpha\n", encoding="utf-8")
    (tmp / "p6-cifail-results.json").write_text(json.dumps({
        "results": [{"name": "case-alpha", "ok": False, "expected": ["ok"], "exit": 2},
                    {"name": "case-beta", "ok": True, "exit": 0}]}, ensure_ascii=False),
        encoding="utf-8")
    (tmp / "p6-cifail-results-bad.json").write_text('{"results": [ {"name": "x", ', encoding="utf-8")
    (tmp / "p6-golden-old.json").write_text(json.dumps({
        "model": "model-a", "pass_rate": 2 / 3,
        "rows": [{"id": "qa-01", "ok": True, "in_tokens": 10, "out_tokens": 5,
                  "latency_ms": 100, "detail": "ok"},
                 {"id": "qa-02", "ok": False, "in_tokens": 10, "out_tokens": 5,
                  "latency_ms": 100, "detail": "regex not matched"},
                 {"id": "qa-03", "ok": True, "in_tokens": 10, "out_tokens": 5,
                  "latency_ms": 100, "detail": "ok"}]}, ensure_ascii=False),
        encoding="utf-8")
    (tmp / "p6-golden-new.json").write_text(json.dumps({
        "model": "model-b", "pass_rate": 2 / 3,
        "rows": [{"id": "qa-01", "ok": False, "in_tokens": 12, "out_tokens": 5,
                  "latency_ms": 150, "detail": "regex not matched: x"},
                 {"id": "qa-02", "ok": True, "in_tokens": 10, "out_tokens": 4,
                  "latency_ms": 90, "detail": "all accept rules matched"},
                 {"id": "qa-03", "ok": True, "in_tokens": 10, "out_tokens": 5,
                  "latency_ms": 100, "detail": "ok"}]}, ensure_ascii=False),
        encoding="utf-8")
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

    # v2.10.9 fixtures（R-9 重复登记检测）：需要"一个未登记但和已有条目同名能力"的
    # 脚本，真 scripts/ 不能造 —— 故用 --scripts-dir 指向临时目录。
    (tmp / "tsp-dup.py").write_text(
        "import json, subprocess, sys, tempfile, pathlib\n"
        f"TSP = {str(SCRIPT_DIR / 'toolstack-pipeline.py')!r}\n"
        "t = pathlib.Path(tempfile.mkdtemp()); sd = t / 'scripts'; sd.mkdir()\n"
        "for n in ['verify-runner.py', 'verify-runner-alt.py', 'totally-new-thing.py']:\n"
        "    (sd / n).write_text('# fixture\\n', encoding='utf-8')\n"
        "mp = t / 'ts.json'\n"
        "mp.write_text(json.dumps({\n"
        "    'schema': 4, 'refs': {}, 'local_tools': {}, 'sdk_tools_exempt': [],\n"
        "    'capability_vocab': ['verify.static'],\n"
        "    'sdk_tools': {'verify-runner.py': {'note': '确定性验证运行器',\n"
        "                                       'category': 'EXECUTE', 'risk_tier': 3,\n"
        "                                       'capabilities': ['verify.static',\n"
        "                                                        'verify.dynamic']}}},\n"
        "                 ensure_ascii=False), encoding='utf-8')\n"
        "base = [sys.executable, TSP, '--manifest', str(mp), '--scripts-dir', str(sd),\n"
        "        *sys.argv[1:]]\n"
        "# 1) 只读检查：疑似重复必须出现在报告里\n"
        "r1 = subprocess.run(base + ['--json'], capture_output=True, text=True)\n"
        "rep = json.loads(r1.stdout)\n"
        "dups = [x for x in rep['sdk_tools'] if x.get('status') == 'suspect-duplicate']\n"
        "print('dups=' + (','.join(d['script'] + '->' + d['duplicate_of']\n"
        "                          for d in dups) or 'none'))\n"
        "# 2) --update：重复条目被扣住，全新条目照常登记\n"
        "subprocess.run(base + ['--update'], capture_output=True, text=True)\n"
        "after = sorted(json.loads(mp.read_text(encoding='utf-8'))['sdk_tools'])\n"
        "print('registered=' + ','.join(after))\n"
        "print('held=' + ','.join(n for n in ['verify-runner-alt.py'] if n not in after))\n",
        encoding="utf-8")

    # v2.10.8 fixtures（R-4 健康态阶梯）：probe-tools 的降级/回边必须是可重复验证的，
    # 但一次 C() 只能跑一条命令，而阶梯要连跑 N 次 —— 故生成一个夹具脚本代跑。
    # PROBE 路径在生成期烘焙（夹具文件在 tmp 下，运行期拿不到 SCRIPT_DIR）。
    (tmp / "probe-health.py").write_text(
        "import json, subprocess, sys, tempfile, pathlib\n"
        f"PROBE = {str(SCRIPT_DIR / 'probe-tools.py')!r}\n"
        "mode = sys.argv[1]\n"
        "t = pathlib.Path(tempfile.mkdtemp()); m = t / 'ts.json'\n"
        "def entry(code):\n"
        "    return {'cmd': [sys.executable, '-c', code], 'risk_tier': 1,\n"
        "            'group': 't', 'capabilities': ['tool.probe'], 'health': 'active'}\n"
        "FAIL = 'import sys;sys.exit(3)'\n"
        "data = {'schema': 4, 'capability_vocab': ['tool.probe'],\n"
        "        'local_tools': {'zz': entry(FAIL)}, 'sdk_tools': {}}\n"
        "m.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')\n"
        "def run(): subprocess.run([sys.executable, PROBE, '--manifest', str(m),\n"
        "                           '--write-back'], capture_output=True)\n"
        "if mode == 'readonly':\n"
        "    before = m.read_text(encoding='utf-8')\n"
        "    subprocess.run([sys.executable, PROBE, '--manifest', str(m)], capture_output=True)\n"
        "    print('readonly-unchanged=%s' % (m.read_text(encoding='utf-8') == before))\n"
        "    sys.exit(0)\n"
        "for _ in range(int(mode)):\n"
        "    run()\n"
        "if len(sys.argv) > 2 and sys.argv[2] == 'recover':\n"
        "    d = json.loads(m.read_text(encoding='utf-8'))\n"
        "    d['local_tools']['zz'] = entry(\"print('ok 1.0')\")\n"
        "    m.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')\n"
        "    run()\n"
        "final = json.loads(m.read_text(encoding='utf-8'))['local_tools']['zz']\n"
        "print('health=%s streak=%s' % (final.get('health'), final.get('_fail_streak')))\n",
        encoding="utf-8")

    # v2.10.9 fixtures（R-8 声誉时间维度）：EMA + freshness 需要回溯时间戳的
    # routing_log，CLI 的 record 只能写"现在" —— 故用夹具脚本直接灌 SQL。
    (tmp / "rs-reputation.py").write_text(
        "import json, sqlite3, subprocess, sys, tempfile, pathlib\n"
        "from datetime import datetime, timezone, timedelta\n"
        f"RS = {str(SCRIPT_DIR / 'router-stats.py')!r}\n"
        "mode = sys.argv[1]\n"
        "now = datetime.now(timezone.utc)\n"
        "db = pathlib.Path(tempfile.mkdtemp()) / 'rep.db'\n"
        "subprocess.run([sys.executable, RS, 'init', '--db', str(db)], capture_output=True)\n"
        "con = sqlite3.connect(db)\n"
        "def add(model, outcome, days_ago):\n"
        "    con.execute('INSERT INTO routing_log (ts,task,cell,model,level,outcome,"
        "tokens,response_tokens,cost) VALUES (?,?,?,?,?,?,?,?,?)',\n"
        "               ((now - timedelta(days=days_ago)).isoformat(), 't', 'bug_fix',\n"
        "                model, 0, outcome, 1000, 1000, 0.001))\n"
        "if mode == 'degraded':\n"
        "    for i in range(20): add('m_old', 'pass', 60 - i)\n"
        "    for i in range(10): add('m_old', 'fail', 10 - i)\n"
        "    for i in range(8):  add('m_new', 'pass', 8 - i)\n"
        "elif mode == 'lowsample':\n"
        "    for i in range(3):  add('m_a', 'pass', 1)\n"
        "con.commit(); con.close()\n"
        "subprocess.run([sys.executable, RS, 'rebuild', '--db', str(db), '--no-backup'],\n"
        "               capture_output=True)\n"
        "extra = sys.argv[2:]\n"
        "out = subprocess.run([sys.executable, RS, 'recommend', '--db', str(db),\n"
        "                      '--cell', 'bug_fix', '--seed', '1', *extra],\n"
        "                     capture_output=True, text=True).stdout\n"
        "d = json.loads(out)\n"
        "top = {c['model']: c for c in d['top']}\n"
        "rank1 = d['top'][0]['model'] if d['top'] else None\n"
        "print('fallback_to_static=%s' % d.get('fallback_to_static'))\n"
        "print('insufficient=%s' % (d.get('insufficient') or []))\n"
        "if mode == 'degraded':\n"
        "    print('conf_old=%s conf_new=%s rank1=%s' % (\n"
        "        top['m_old']['confidence'], top['m_new']['confidence'], rank1))\n"
        "    print('ema_old=%s fresh_days_old=%s cum_sr_old=%s' % (\n"
        "        top['m_old']['ema'], top['m_old']['freshness_days'],\n"
        "        top['m_old']['success_rate']))\n"
        "else:\n"
        "    print('label=%s' % top['m_a']['confidence_label'])\n",
        encoding="utf-8")

    # T-541 fixtures（F-61 尺寸闸）：造不同体积的 SKILL.md。尺寸闸读 `st_size`
    # （磁盘字节，CRLF 计入），夹具用 ASCII 填充，不与换行符换算纠缠。
    def _sdk_tree_sized(tag: str, size_bytes: int) -> Path:
        root = _sdk_tree4(tag, {}, vocab=["verify.static"])
        p = root / "SKILL.md"
        base = p.read_text(encoding="utf-8")
        pad = max(0, size_bytes - len(base.encode("utf-8")) - 20)
        p.write_text(base + "\n<!-- pad " + ("x" * pad) + " -->\n", encoding="utf-8")
        return root

    # v2.10.8 fixtures（R-5 resolve 三态）：健康态 + fallback 组合决定 READY/DEGRADED/BLOCKED。
    (tmp / "toolstack-resolve.json").write_text(json.dumps({
        "schema": 4, "capability_vocab": ["verify.static"], "refs": {},
        "local_tools": {},
        "sdk_tools": {
            "a.py": {"risk_tier": 1, "health": "degraded", "fallback": "b.py",
                     "capabilities": ["verify.static"]},
            "b.py": {"risk_tier": 1, "health": "active", "fallback": None,
                     "capabilities": ["verify.static"]},
            "c.py": {"risk_tier": 1, "health": "unavailable", "fallback": None,
                     "capabilities": []},
        }}, ensure_ascii=False), encoding="utf-8")
    # R-5 ci-steps manifest 夹具：空清单 / 指向不存在脚本 —— 两种都必须 fail-closed，
    # 否则"加第 8 步"变成改坏清单却静默放行。
    (tmp / "ci-steps-empty.json").write_text(
        json.dumps({"schema": "ci-steps.v1", "steps": []}, ensure_ascii=False), encoding="utf-8")
    # ⚠️ 用 json.dumps 而非内联 JSON 文本：内联文本里的 `"script": "..."` 会被
    # selfcheck-static 的 collect_blocking_cases 正则当成用例起点，一路贪婪吞到
    # 下一个 `"expect":`，把真正的拦截用例吃掉 → probe-tools 被误报为「无拦截用例」。
    (tmp / "ci-steps-broken.json").write_text(json.dumps({
        "schema": "ci-steps.v1",
        "steps": [{"name": "ghost", "script": "zz-ghost.py", "args": [], "timeout": 30,
                   "tier": 0, "optional": False, "skip_flag": None}]},
        ensure_ascii=False), encoding="utf-8")

    # F-63 retention fixture：8 份带日期报告 + 单步 manifest 驱动脚本。
    # 断言对象是"写新报告后同前缀旧报告被清理"这一落盘副作用 —— 外层用例只能 grep
    # 输出，故由 fixture 代跑 ci-smoke 并自检文件系统状态再打印判定行。
    # 前缀用 ci-steps-retention-check-*（日期收尾），与真实 data/ 报告互不干扰。
    # F-59 Phase 1: manifest loader 夹具（importlib 直载套件模块做契约测试，
    # 不递归跑套件 —— 嵌套 TemporaryDirectory 清理在沙箱 D:\Temp 下会被过滤
    # 驱动阻塞，v2.10.12 已把套件自身清理改为分离进程，但测试不引入嵌套为上）。
    # 坏 manifest → SystemExit(2)；好 manifest → 契约字段 + {tmp} 替换逐一断言。
    (tmp / "cases-bad").mkdir()
    (tmp / "cases-bad" / "bad-schema.json").write_text(
        json.dumps({"schema": "nope.v9", "cases": []}), encoding="utf-8")
    (tmp / "cases-good").mkdir()
    (tmp / "cases-good" / "extra.json").write_text(json.dumps({
        "schema": "robustness-cases.v1", "domain": "loader-test",
        "cases": [{"name": "version-check: fixture root (manifest loader)",
                   "script": "version-check.py",
                   "args": ["--root", "{tmp}/vc-probe", "--json"],
                   "expect": 0, "want": ["usage"]}]},
        ensure_ascii=False), encoding="utf-8")
    (tmp / "manifest-loader-fixture.py").write_text(
        "import importlib.util, sys\n"
        "from pathlib import Path\n"
        "suite_path, bad_dir, good_dir, tmp = map(Path, sys.argv[1:5])\n"
        "spec = importlib.util.spec_from_file_location('rob_suite_under_test', suite_path)\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "mod.CASES_DIR = bad_dir\n"
        "try:\n"
        "    mod.load_manifest_cases(tmp)\n"
        "    print('bad=fail-no-raise')\n"
        "except SystemExit as e:\n"
        "    print('bad_exit=%s' % e.code)\n"
        "mod.CASES_DIR = good_dir\n"
        "cases = mod.load_manifest_cases(tmp)\n"
        "print('good_n=%d' % len(cases))\n"
        "c = cases[0]\n"
        "print('script_ok=%s' % (c['script'] == 'version-check.py'))\n"
        "print('expect_ok=%s' % (c['expect'] == 0))\n"
        "print('want_ok=%s' % (c['want'] == ('usage',)))\n"
        "print('tmp_subst_ok=%s' % (str(tmp) in ' '.join(c['cmd'])))\n",
        encoding="utf-8")
    (tmp / "retention-fixture.py").write_text(
        "import json, subprocess, sys\n"
        "from pathlib import Path\n"
        "d = Path(sys.argv[1]); sdk = Path(sys.argv[2])\n"
        "for i in range(1, 9):\n"
        "    (d / ('ci-steps-retention-check-2026-08-%02d.json' % i)).write_text('{\"seed\":%d}' % i, encoding='utf-8')\n"
        "mp = d / 'retention-steps.json'\n"
        "mp.write_text(json.dumps({'steps': [{'name': 'vc', 'script': 'version-check.py'}]}), encoding='utf-8')\n"
        "r = subprocess.run([sys.executable, str(sdk / 'ci-smoke.py'), '--steps', str(mp),\n"
        "                    '--report', str(d / 'ci-steps-retention-check-2099-01-01.json')],\n"
        "                   capture_output=True, text=True)\n"
        "left = sorted(f.name for f in d.glob('ci-steps-retention-check-*.json'))\n"
        "print('exit=%d' % r.returncode)\n"
        "print('left=%d' % len(left))\n"
        "print('oldest_gone=%s' % ('ci-steps-retention-check-2026-08-01.json' not in left))\n"
        "print('new_present=%s' % ('ci-steps-retention-check-2099-01-01.json' in left))\n",
        encoding="utf-8")
    # --- v2.11.1 A-8 canary #1：验收契约失配必须 exit 2（AOS §33 golden invariant）---
    # 用**真实契约**改一个字段（sdk_version）造漂移 + 单步清单（快），显式 --contract
    # 让契约在非默认清单下也生效。坏产物必须被闸拦下，否则"绿"不可信。
    (tmp / "contract-drift-fixture.py").write_text(
        "import json, subprocess, sys\n"
        "from pathlib import Path\n"
        "d = Path(sys.argv[1]); sdk = Path(sys.argv[2])\n"
        "src = sdk / 'data' / 'acceptance-contract.v1.json'\n"
        "c = json.loads(src.read_text(encoding='utf-8'))\n"
        "c['sdk_version'] = 'v0.0.1'\n"
        "cp = d / 'drifted-contract.json'\n"
        "cp.write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')\n"
        "mp = d / 'drift-steps.json'\n"
        "mp.write_text(json.dumps({'steps': [{'name': 'version-check',\n"
        "                                     'script': 'version-check.py'}]}), encoding='utf-8')\n"
        "r = subprocess.run([sys.executable, str(sdk / 'ci-smoke.py'), '--steps', str(mp),\n"
        "                    '--contract', str(cp), '--skip-privacy', '--json'],\n"
        "                   capture_output=True, text=True)\n"
        "out = r.stdout + r.stderr\n"
        "print('exit=%d' % r.returncode)\n"
        "print('drift_detected=%s' % ('DRIFT' in out))\n",
        encoding="utf-8")
    # --- v2.11.1 A-8 canary #2：植入盘符路径的坏产物必须被隐私闸拦下 ---
    (tmp / "privacy-canary-fixture.py").write_text(
        "import json, subprocess, sys\n"
        "from pathlib import Path\n"
        "d = Path(sys.argv[1]); sdk = Path(sys.argv[2])\n"
        "bad = d / 'leak'; bad.mkdir(exist_ok=True)\n"
        "(bad / 'note.md').write_text('key at C:\\\\Users\\\\someone\\\\.ssh\\\\id_rsa\\n',\n"
        "                             encoding='utf-8')\n"
        "r = subprocess.run([sys.executable, str(sdk / 'privacy-scan.py'), str(bad), '--json'],\n"
        "                   capture_output=True, text=True)\n"
        "out = r.stdout + r.stderr\n"
        "print('exit=%d' % r.returncode)\n"
        "print('blocked=%s' % (r.returncode == 2 and '\"clean\": false' in out))\n",
        encoding="utf-8")

    # v2.10.8 fixtures（R-3 schema-4）：能力词表/健康态/fallback 三项的拦截与向后兼容。
    # 与 _sdk_tree 同构，但 sdk_tools 条目内容可注入，用于造非法 schema-4 数据。
    # ⚠️ 位置敏感：必须放在 _sdk_tree **之后** —— 插进它函数体内会把 `_sdk_tree`
    # 的 `return root` 变成死代码，两条既有 F-43 用例会拿到 `--root None`。
    def _sdk_tree4(tag: str, entry: dict, vocab=None) -> Path:
        root = tmp / f"sdktree4-{tag}"
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "references").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "zz-probe.py").write_text("# probe\n", encoding="utf-8")
        data = {
            "schema": 4, "last_check": "2026-09-01T00:00:00+08:00",
            "sdk_tools_exempt": [], "local_tools": {}, "refs": {},
            "sdk_tools": {"zz-probe.py": dict({"risk_tier": 1}, **entry)},
        }
        if vocab is not None:
            data["capability_vocab"] = vocab
        (root / "scripts" / "toolstack.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        (root / "SKILL.md").write_text(
            "---\nname: user-vibe_coding-sdk-moe\ndescription: fixture\n---\n"
            "\n# user-vibe_coding-sdk-moe v9.9.9\n", encoding="utf-8")
        return root

    def C(name, script, args, expect, want=(), dont=("Traceback",), expect_any=(), timeout=None):
        return {"name": name, "script": script,
                "cmd": [PY, str(SCRIPT_DIR / script), *[str(a) for a in args]],
                "expect": expect, "expect_any": tuple(expect_any),
                "want": want, "dont": dont, "timeout": timeout}

    return [
        # --- golden-run: universal boundaries ---
        # --- golden-run: validate-set pre-check (v1.15.0) ---
        # --- golden-run: adversarial judging ---
        # --- verify-runner ---
        C("verify-runner: passing cmd", "verify-runner.py",
          ["--cmd", PY, "-c", "print('ok')"], 0, want=("ALL PASS",)),
        # --- verify-runner: layered + diagnostic.v1 (v2.0.0, T6/T7) ---
        C("verify-runner: diagnostic schema in json", "verify-runner.py",
          ["--json", "--cmd", PY, "-c", "print('ok')"], 0, want=('"schema": "diagnostic.v1"',)),
        # --- task-state (v2.0.0, T5) ---
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
        # --- case-search --layer (v2.2.0, T9) ---
        C("case-search: layer hit", "case-search.py",
          ["--q", "verify-runner", "--layer", "solutions", "--dir", mem_dir, "--json"], 0,
          want=("results",)),
        C("case-search: layer nonexistent", "case-search.py",
          ["--q", "x", "--layer", "nope", "--dir", mem_dir], 0, want=("no match",)),
        # --- token-meter budget (v2.2.0, T10) ---
        # F-50：原用例名"budget exceeded"却 expect 0 —— 用例按错误的既成行为写的，
        # 把"永不拦截"固化为契约。现超预算必须 exit 2。
        # --- golden-run --record feedback loop (v2.2.0, T11) ---
        # NOTE: 用 rs.db（同组前序用例自己写入），**不要**用 golden-run 组写的 rec.db ——
        # pre-commit 门禁是 `robustness --only <script>` 逐脚本跑的，跨组依赖会让
        # 子集必然失败（此前 --only router-stats 恒 16/17）。回归用例必须自洽。
        # --- bump-version guards (v1.14.1) ---
        # --- error-sig / case-search / env-snapshot ---
        # --- token-meter / review-prefilter ---
        # --- v2.10.9: R-7 上下文分类观测（只观测、不分配、不拦截）---
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
        # --- mutation-audit (v2.10.3): 变异测试审计自身 ---
        # --- privacy-scan (v1.16.0) ---
        # --- v2.7.1 F-15: host runtime dirs excluded by default ---
        # --- git hooks gate (v2.4.0, P0-1) ---
        C("install-hooks: install", "install-hooks.py", ["--repo", repo_dir], 0, want=("installed",)),
        C("install-hooks: idempotent", "install-hooks.py", ["--repo", repo_dir], 0, want=("already",)),
        # 负向覆盖：外来钩子未加 --force 必须拒绝（此前 3 条用例全是 expect=0）
        C("install-hooks: 外来钩子无 --force → 拒（exit 1）", "install-hooks.py",
          ["--repo", repo3], 1, want=("foreign hook",)),
        # --- v2.10.0: F-41 治本 —— SDK 内文档也过 privacy 闸 ---
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
        # --- R-10 (v2.10.9): trace_id 贯穿 —— 一次任务一个主键，全链可重建 ---
        # 前三步用外部指定的 trace_id，这样第 4 步能直接按字面量反查（否则只能
        # 在测试里解析上一条命令的输出，脆弱且不可读）。
        C("task-state: init 自动生成 trace_id（R-10）", "task-state.py",
          ["--tasks-dir", tasks_dir, "init", "--task", "t-auto", "--title", "auto id"], 0,
          want=("trace_id",)),
        C("task-state: init 支持外部指定 trace_id（R-10）", "task-state.py",
          ["--tasks-dir", tasks_dir, "init", "--task", "t-trace", "--title", "traced",
           "--trace-id", "01JR10TRACEZDR10TRACEZDR10"], 0,
          want=("01JR10TRACEZDR10TRACEZDR10",)),
        C("task-state: transition 回传同一 trace_id（R-10）", "task-state.py",
          ["--tasks-dir", tasks_dir, "transition", "--task", "t-trace", "--to", "UNDERSTAND"], 0,
          want=("01JR10TRACEZDR10TRACEZDR10",)),
        C("task-state: trace-export --trace 重建全链（R-10）", "task-state.py",
          ["--tasks-dir", tasks_dir, "trace-export", "--trace",
           "01JR10TRACEZDR10TRACEZDR10", "--json"], 0,
          want=('"schema": "trace.v1"', '"tasks": [\n    "t-trace"\n  ]',
                '"event_count": 2', '"event": "created"', '"event": "transition"')),
        C("task-state: trace-export 未知 trace_id → exit 2（R-10 负向）", "task-state.py",
          ["--tasks-dir", tasks_dir, "trace-export", "--trace",
           "01JZZZZZZZZZZZZZZZZZZZZZZZ"], 2, want=("trace_id not found",)),
        C("task-state: trace-export 都不传 → exit 2（R-10 负向）", "task-state.py",
          ["--tasks-dir", tasks_dir, "trace-export"], 2,
          want=("requires --task or --trace",)),
        # --- C1-4 (v2.5.0): ci-fail-analyze ---
        # --- C2-3 (v2.6.0): gh-workflow-check control-plane contract ---
        C("gh-workflow-check: sdk .github OK", "gh-workflow-check.py",
          ["--gh-dir", SCRIPT_DIR.parent / ".github"], 0, want=("OK",)),
        # --- C2-4 (v2.6.0): spec-tasks-import ---
        # --- v2.7.0: F-01 基础设施失败不进能力后验 ---
        # --- v2.7.0: F-01 数据修复 rebuild ---
        # --- v2.7.0: F-11 coverage ---
        C("router-stats v2: coverage 输出", "router-stats.py",
          ["report", "--db", tmp / "rs3.db", "--golden-set",
           SCRIPT_DIR / "data" / "golden-set-v3.json", "--json"], 0, want=('"coverage"',)),
        # --- v2.7.1 F-17: legacy NULL 行迁移回填 ---
        # --- v2.7.0: T-06 diff-risk 三档闸门 ---
        # --- v2.7.0: T-07 verify-runner allow_missing ---
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
        # F-01 回归：usage 虚报 2048 但文本为空 → empty（infra），不进 quality。
        # 样本必失败（contains 不匹配）→ exit 2 属预期，断言的是分类正确。
        # --- v2.7.0: T-15 体积同步 ---
        # --- v2.8.0: T-07 置信度自适应验证深度 ---
        # --- v2.8.2: T-17 security 层恒保（F-27：轻/中档曾剔除安全扫描）---
        # --- v2.9.0: T-18 随包预设 targeted 分支可达（F-28 死代码修复）---
        C("verify-runner: 随包预设 targeted 可达（conf 0.9）", "verify-runner.py",
          ["--config", str(SCRIPT_DIR / "presets" / "verify.python.json"),
           "--cwd", str(tmp / "empty-cwd"), "--confidence", "0.9", "--json"], 0,
          want=("test-targeted", "security"), dont=("test-full",)),
        C("verify-runner: 随包预设 full 档含 test-full（conf 0.2）", "verify-runner.py",
          ["--config", str(SCRIPT_DIR / "presets" / "verify.python.json"),
           "--cwd", str(tmp / "empty-cwd"), "--confidence", "0.2", "--json"], 0,
          want=("test-full", "security")),
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
        # --- T-511（F-60）：ENGINEERING/ALIGNMENT 头部版本戳两点 ---
        # T-511 配套：闸门从 5 点扩到 7 点后，bump-version **必须**同步这两枚戳，
        # 否则下一次发版会立刻把新闸打红 —— 闸门与发布工具必须成对改，这条守这个对。
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
        # --- v2.9.0: T-19 origin class（F-30：origin 而非 leaf 决定动作）---
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
        # F-53：畸形 numstat → 干净拦截（报行号，exit 2），不得裸 traceback
        # --- v2.10.6: P3 清偿 — vk B.6 per-test / cicd §15 策略钉 / §29 跨版本对比 ---
        C("golden-run: 跨版本对比检出回归 → exit2（§29）", "golden-run.py",
          ["--compare", str(tmp / "p6-golden-old.json") + "," + str(tmp / "p6-golden-new.json")],
          2, want=("REGRESSION", "regressions=1", "fixed=1")),
        C("golden-run: 跨版本对比无回归 → exit0（§29）", "golden-run.py",
          ["--compare", str(tmp / "p6-golden-old.json") + "," + str(tmp / "p6-golden-old.json")],
          0, want=("regressions=0",)),
        # --- v2.10.0: T-23b diff-risk repair_confidence 合成（B.21）---
        # --- v2.10.0: T-25 action-gate（F-38 Action Validator / F-35 idempotent 首个消费方）---
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
        # --- v2.10.1: F-44 回归 —— push 闸门有落点（tier-4 结构性人工）---
        # --- v2.10.1: F-47 回归 —— --json 不得吞掉 --apply（dry-run 契约显式化）---
        # --- v2.10.1: selfcheck-static 自身（sdk_tools 漂移哨兵）---
        # --- v2.10.2: F-43 回归 —— 未登记脚本必须拦（提交时刻 + 巡检两条线）---
        C("selfcheck-static: 未登记脚本 → exit 2（F-43 回归）", "selfcheck-static.py",
          ["--root", _sdk_tree("drift", register=False)], 2,
          want=("NOT in toolstack.json sdk_tools", "zz-probe.py")),
        C("selfcheck-static: --root 已登记树 → exit 0", "selfcheck-static.py",
          ["--root", _sdk_tree("clean", register=True)], 0,
          want=('"ok": true',)),
        # 不完整树必须 fail-closed 且不 traceback（C0-2 renamed-dir fixture 抓到）
        # --- v2.10.8: R-3 schema-4 四项拦截 + 向后兼容（负向覆盖：只验成功路径
        #     等于没验 —— 三条拦截用例证明闸真的会落，两条兼容用例证明不误伤）---
        C("selfcheck-static: schema-4 未知 capability → exit 2（R-3 负向）",
          "selfcheck-static.py",
          ["--root", _sdk_tree4("bad-cap", {"capabilities": ["not.in.vocab"]},
                                vocab=["verify.static"])], 2,
          want=("capabilities invalid", "unknown capability")),
        C("selfcheck-static: schema-4 health 非法枚举 → exit 2（R-3 负向）",
          "selfcheck-static.py",
          ["--root", _sdk_tree4("bad-health", {"health": "broken"})], 2,
          want=("health not in",)),
        C("selfcheck-static: schema-4 fallback 断链 → exit 2（R-3 负向）",
          "selfcheck-static.py",
          ["--root", _sdk_tree4("bad-fb", {"fallback": "nope.py"})], 2,
          want=("fallback dangling",)),
        C("selfcheck-static: schema-4 capabilities 非 list[str] → exit 2（R-3 负向）",
          "selfcheck-static.py",
          ["--root", _sdk_tree4("bad-type", {"capabilities": "verify.static"})], 2,
          want=("capabilities must be list[str]",)),
        C("selfcheck-static: schema-4 四字段全缺 → exit 0（向后兼容，仅 note）",
          "selfcheck-static.py",
          ["--root", _sdk_tree4("legacy", {}, vocab=["verify.static"])], 0,
          want=('"ok": true',)),
        C("selfcheck-static: schema-4 fallback=null 视作未声明 → exit 0",
          "selfcheck-static.py",
          ["--root", _sdk_tree4("null-fb", {"fallback": None, "health": "active",
                                            "capabilities": ["verify.static"]},
                                vocab=["verify.static"])], 0,
          want=('"ok": true',)),
        # --- v2.10.8: R-4 工具健康态阶梯（§19 三态 + DEGRADED→ACTIVE 回边）---
        {"name": "probe-tools: 连败 1 次仍 active（不误降级）", "script": "probe-tools.py",
         "cmd": [PY, str(tmp / "probe-health.py"), "1"], "expect": 0,
         "want": ("health=active", "streak=1")},
        {"name": "probe-tools: 连败 2 次 → degraded（R-4）", "script": "probe-tools.py",
         "cmd": [PY, str(tmp / "probe-health.py"), "2"], "expect": 0,
         "want": ("health=degraded", "streak=2")},
        {"name": "probe-tools: 连败 4 次 → unavailable（R-4）", "script": "probe-tools.py",
         "cmd": [PY, str(tmp / "probe-health.py"), "4"], "expect": 0,
         "want": ("health=unavailable", "streak=4")},
        {"name": "probe-tools: 探测恢复 → 回 active 且连败清零（R-4 回边）",
         "script": "probe-tools.py",
         "cmd": [PY, str(tmp / "probe-health.py"), "5", "recover"], "expect": 0,
         "want": ("health=active", "streak=0")},
        {"name": "probe-tools: 默认只读不改盘（R-4 副作用闸）", "script": "probe-tools.py",
         "cmd": [PY, str(tmp / "probe-health.py"), "readonly"], "expect": 0,
         "want": ("readonly-unchanged=True",)},
        # --- v2.10.8: R-5 resolve（§10 七动词之 resolve：纯规划零副作用）---
        # --- v2.10.8: R-5 ci-steps manifest fail-closed ---
        # --- v2.10.12: F-63 --report 保留策略 ---
        # 8 份旧报告 + 写入第 9 份 → 同前缀只留最近 7 份（最旧 2 份被清，新报告在）。
        # script 字段挂 ci-smoke.py：--only ci-smoke 可选中，且 selfcheck 拦截用例收集命中。
        {"name": "ci-smoke: --report keep-last-7 清理同前缀旧报告（F-63）",
         "script": "ci-smoke.py", "expect": 0,
         "cmd": [PY, str(tmp / "retention-fixture.py"), str(tmp), str(SCRIPT_DIR)],
         "want": ("exit=0", "left=7", "oldest_gone=True", "new_present=True")},
        # --- v2.11.1: A-8 canary（AOS §33 golden invariant）---
        # 坏产物必须触发对应硬闸：① 契约失配 → ci-smoke exit 2；② 植入盘符路径
        # → privacy-scan exit 2 且 findings>0。二者被 mutation-audit 反向利用：
        # 把闸改成恒放行后这两条必须变红，否则该闸无有效约束。
        {"name": "canary: 验收契约失配 → exit 2（A-5 fail-closed）",
         "script": "ci-smoke.py", "expect": 0,
         "cmd": [PY, str(tmp / "contract-drift-fixture.py"), str(tmp), str(SCRIPT_DIR)],
         "want": ("exit=2", "drift_detected=True")},
        {"name": "canary: 植入盘符路径 → 隐私闸拦截（exit 2 + clean=false）",
         "script": "privacy-scan.py", "expect": 0,
         "cmd": [PY, str(tmp / "privacy-canary-fixture.py"), str(tmp), str(SCRIPT_DIR)],
         "want": ("exit=2", "blocked=True")},
        # --- v2.10.12: F-59 Phase 1 manifest loader（契约测试，不递归）---
        # script 挂 robustness-suite.py：--only robustness-suite 可选中。
        # 断言：坏 manifest fail-closed（SystemExit 2）+ 好 manifest 字段契约
        # （cmd 构造 / PY 前缀 / want 元组 / {tmp} 占位符替换）。
        # 不递归跑套件：嵌套 TemporaryDirectory 清理在沙箱 D:\Temp 下会被
        # 过滤驱动阻塞（v2.10.12 已把套件自身清理改为分离进程）。
        {"name": "robustness: manifest loader 契约（F-59 fail-closed + {tmp} 替换）",
         "script": "robustness-suite.py", "expect": 0,
         "cmd": [PY, str(tmp / "manifest-loader-fixture.py"),
                 str(SCRIPT_DIR / "robustness-suite.py"),
                 str(tmp / "cases-bad"), str(tmp / "cases-good"), str(tmp)],
         "want": ("bad_exit=2", "good_n=1", "script_ok=True", "expect_ok=True",
                  "want_ok=True", "tmp_subst_ok=True")},
        # --- v2.10.9: R-8 声誉时间维度（§18 EMA + freshness）---
        # 累积成功率 0.667 的 m_old 看着还行，但它的成功都发生在 41 天前 ——
        # 时间维度必须把它和"近期 8 连胜"的 m_new 分开，否则旧数据继续背书退化模型。
        {"name": "router-stats: 早期全胜近期连败 → confidence 被 freshness 压低（R-8）",
         "script": "router-stats.py", "expect": 0,
         "cmd": [PY, str(tmp / "rs-reputation.py"), "degraded"],
         "want": ("rank1=m_new", "conf_old=0.1022", "conf_new=0.9512")},
        {"name": "router-stats: EMA 与累积成功率并列输出（R-8 可解释性）",
         "script": "router-stats.py", "expect": 0,
         "cmd": [PY, str(tmp / "rs-reputation.py"), "degraded"],
         "want": ("ema_old=0.7937", "fresh_days_old=41.0", "cum_sr_old=0.667")},
        {"name": "router-stats: 低样本 → insufficient + 回退静态矩阵（R-8）",
         "script": "router-stats.py", "expect": 0,
         "cmd": [PY, str(tmp / "rs-reputation.py"), "lowsample"],
         "want": ("label=insufficient", "fallback_to_static=True")},
        {"name": "router-stats: --min-sample 可调（阈值常量可配，R-8）",
         "script": "router-stats.py", "expect": 0,
         "cmd": [PY, str(tmp / "rs-reputation.py"), "lowsample", "--min-sample", "3"],
         "want": ("label=ok", "fallback_to_static=False")},
        # --- v2.10.9: R-9 重复登记检测（§21.1 只标记、不自动合并）---
        {"name": "toolstack-pipeline: 疑似重复登记 → 标记进评审队列（R-9）",
         "script": "toolstack-pipeline.py", "expect": 0,
         "cmd": [PY, str(tmp / "tsp-dup.py")],
         "want": ("dups=verify-runner-alt.py->verify-runner.py",)},
        {"name": "toolstack-pipeline: --update 扣住重复项、放行全新项（R-9）",
         "script": "toolstack-pipeline.py", "expect": 0,
         "cmd": [PY, str(tmp / "tsp-dup.py")],
         "want": ("registered=totally-new-thing.py,verify-runner.py",
                  "held=verify-runner-alt.py",),
         "dont": ("registered=totally-new-thing.py,verify-runner-alt.py,",)},
        {"name": "toolstack-pipeline: --allow-duplicate 放行（人工确认后，R-9）",
         "script": "toolstack-pipeline.py", "expect": 0,
         "cmd": [PY, str(tmp / "tsp-dup.py"), "--allow-duplicate"],
         "want": ("registered=totally-new-thing.py,verify-runner-alt.py,verify-runner.py",
                  "held=",)},
        {"name": "toolstack-pipeline: --dup-threshold 可调（阈值常量可配，R-9）",
         "script": "toolstack-pipeline.py", "expect": 0,
         "cmd": [PY, str(tmp / "tsp-dup.py"), "--dup-threshold", "1.1"],
         "want": ("dups=none",)},
        # --- T-541（F-61）：SKILL.md 热路径尺寸闸 ---
        # 热路径每长 1KB，所有任务都要多付这 1KB —— 尺寸是成本与 cache 命中率
        # 问题，不是观感问题。warn 只提示、fail 才拦；S-4 判据更严但仅 advisory。
        C("selfcheck-static: SKILL.md 超 fail 阈 → exit 2（T-541 负向）",
          "selfcheck-static.py", ["--root", _sdk_tree_sized("sz-fail", 46_000)], 2,
          want=("SKILL.md", "fail 阈值", "下沉 refs")),
        C("selfcheck-static: SKILL.md 超 warn 阈 → 仅提示不拦截（T-541）",
          "selfcheck-static.py", ["--root", _sdk_tree_sized("sz-warn", 41_000)], 0,
          want=("warn 阈值",), dont=("fail 阈值",)),
        C("selfcheck-static: SKILL.md 超 S-4 判据 37KB → advisory note（T-541）",
          "selfcheck-static.py", ["--root", _sdk_tree_sized("sz-s4", 38_000)], 0,
          want=("S-4 判据",), dont=("fail 阈值",)),
        C("selfcheck-static: --max-skill-bytes 覆盖阈值（T-541）",
          "selfcheck-static.py",
          ["--root", _sdk_tree_sized("sz-warn", 41_000), "--max-skill-bytes", "50000"], 0,
          want=('"verdict": "ok"',), dont=("warn 阈值",)),
    ]

    # --- R-3 建表后自检：夹具返回 None 的静默失败 -------------------------------
    # 若某个 `_sdk_tree*` 夹具漏了 return，参数会变成字面量 "None"；更糟的是
    # 期望 exit 2 的负向用例会**碰巧通过**（--root None → 结构不全 → exit 2），
    # 真正被覆盖的断言一个都没跑到。这里在**建表时刻**就拦，不留给 CI 去猜。
    _none_args = [c["name"] for c in cases
                  if any(a is None or str(a) == "None" for a in c["args"])]
    if _none_args:
        raise SystemExit(
            "robustness: 用例参数出现 'None'（夹具函数可能漏了 return）："
            f"{_none_args}")
    return cases


# --- F-59 Phase 1: 声明式用例 manifest（scripts/cases/*.json，v2.10.12）---------
# 用例注册从"改代码"变"改数据"：常量参数用例外置 JSON（首批 135 条，AST 提取保真迁移）；
# tmp 夹具引用用 {tmp} 占位符，加载时替换为本轮临时目录。判定逻辑与 C() 完全同构
# （cmd=[PY, SCRIPT_DIR/script, *args]，want/dont/timeout 语义一致）。
# fail-closed：任何 manifest 不可读 / schema 不符 / 缺字段 → exit 2，绝不静默跳过。
# 测试钩子：ROBUSTNESS_CASES_DIR 可把加载目录指向临时夹具（不触碰真实 scripts/cases/）。
CASES_DIR = Path(os.environ.get("ROBUSTNESS_CASES_DIR") or SCRIPT_DIR / "cases")
MANIFEST_SCHEMA = "robustness-cases.v1"


def load_manifest_cases(tmp: Path) -> list[dict]:
    """读 cases/*.json 声明式用例，与 build_cases 产物同构合并。"""
    if not CASES_DIR.exists():
        return []
    out: list[dict] = []
    for mf in sorted(CASES_DIR.glob("*.json")):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            print(f"robustness-suite: case manifest unreadable: {mf.name}: {e}",
                  file=sys.stderr)
            raise SystemExit(2)
        if not isinstance(data, dict) or data.get("schema") != MANIFEST_SCHEMA:
            print(f"robustness-suite: case manifest schema mismatch: {mf.name} "
                  f"(expect {MANIFEST_SCHEMA})", file=sys.stderr)
            raise SystemExit(2)
        for idx, c in enumerate(data.get("cases", [])):
            try:
                name, script = c["name"], c["script"]
                args, expect = c["args"], c["expect"]
            except (KeyError, TypeError):
                print(f"robustness-suite: manifest {mf.name} cases[{idx}] "
                      f"missing name/script/args/expect", file=sys.stderr)
                raise SystemExit(2)
            cmd = [PY, str(SCRIPT_DIR / script),
                   *[str(a).replace("{tmp}", str(tmp)) for a in args]]
            out.append({"name": name, "script": script, "cmd": cmd, "expect": expect,
                        "want": tuple(c.get("want", ())),
                        "dont": tuple(c.get("dont", ("Traceback",))),
                        "timeout": c.get("timeout")})
    return out


def _bg_cleanup(td: str) -> None:
    """v2.10.12: 临时目录清理与套件主体解耦（沙箱兼容）。

    背景：本机沙箱把 TMP 重定向到 D:\\Temp，Windows 原生 os.rmdir 偶发被过滤
    驱动（实时扫描）阻塞数十秒 —— with TemporaryDirectory() 的退出清理会把
    整个套件拖死（实测：全量 --quick 在 200+ 用例全绿后卡死于 cleanup）。
    处置：清理交给分离进程（Windows rd /s /q，POSIX rmtree），套件永不等待；
    若删除仍被阻塞则留下垃圾，由系统临时目录的周期清理兜底。
    """
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(["cmd", "/c", "rd", "/s", "/q", td], creationflags=flags,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.rmtree(td, ignore_errors=True)


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

    td = tempfile.mkdtemp(prefix="rob-suite-")
    try:
        tmp = Path(td)
        cases = build_cases(tmp, only=args.only)
        cases += load_manifest_cases(tmp)
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
            code, out = run_case(c["cmd"], timeout=c.get("timeout") or args.timeout,
                                 env_extra=c.get("env"))
            dur_ms = int((time.monotonic() - t0) * 1000)
            expect_ok = code == c["expect"] or (c.get("expect_any") and code in c["expect_any"])
            ok = (expect_ok
                  and all(w in out for w in c.get("want", ()))
                  and not any(d in out for d in c.get("dont", ())))
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
    finally:
        _bg_cleanup(td)


if __name__ == "__main__":
    sys.exit(main())
