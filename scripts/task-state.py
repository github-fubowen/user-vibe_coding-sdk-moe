#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
task-state.py — 任务状态机持久化 (v2.0, 2026-08-30)

Purpose: implement ref-20 (task state machine + blackboard) as a deterministic
CLI. Task state lives in `.workbuddy/tasks/<task_id>.json` — the LLM never
needs to "remember" what the software already knows (coding-agent-os §10).
The transition table is DATA, not prompt text (ref-20 §2).

Design rules (ref-20, SDK §3/G-gates, §5.6):
  * Python 3.9+ stdlib only. JSON out. Exit: 0 = ok / 2 = error (illegal
    transition, missing task, bad JSON, invalid verdict, terminal state).
  * Five-state judgment (SUCCESS/PARTIAL_SUCCESS/FAILED/REGRESSION/UNKNOWN)
    stays with the agent (§5.6); this script only validates + persists facts.
  * Read-only commands: history / trace-export / validate.
  * Writes: init / transition / checkpoint / resume (tier-2 controlled
    modification, reversible — task files are git-tracked JSON).
  * Never pushes; never touches anything outside --tasks-dir.

v2.0 changes (2026-08-30, 自查 F-06/F-07 + T-14):
  * **WAITING**（可恢复暂停，非终态）—— 此前 ESCALATED 是唯一"停下来"的方式且为终态，
    §10.9 tier-4（push 需人工批准）无法建模为"暂停→批准→继续"。
  * **CRASHED + checkpoint/resume** —— 会话中断可恢复。checkpoint 只在 VERIFY/
    REVIEW/WAITING 打点（在 CRASHED 打点会用崩溃态覆盖上一个好状态）。
  * **修复预算硬闸** —— 进入 REPAIR/REPAIRING 前检查 repair_budget（默认 3，
    --max-repair 可调，0=不限）。此前 ref-22 §7 明言"超限判定留 agent"，等于没有闸。
  * **振荡检测** —— 同一 (from,to) 转移超过 3 次即拒绝（--allow-loop 显式放行）。
  * **DAG 依赖** —— depends_on 字段；依赖未 DONE 不得进入 IMPLEMENT（AgentOS F.3）。

v2.1 changes (2026-09-01, 自查 F-21 批次 T-08/T-10):
  * **done-when 完成条件闸**（AgentOS #3）—— init --done-when 记录结构化完成条件；
    FINALIZE→DONE 必须附 --done-evidence（无 done-when/acceptance 的任务不得 finalize）。
  * **append-only 事件日志**（survey G4）—— 每次 init/transition/resume 向
    `<tasks-dir>/events.jsonl` 追加一行 {ts,event,task,from,to,verdict,actor}；
    trace-export 读事件流。任务 JSON 仍是主真相源；ledger 写失败仅告警不阻断。

Usage:
  python task-state.py --tasks-dir .workbuddy/tasks init --task t-001 --title "fix X"
  python task-state.py --tasks-dir .workbuddy/tasks transition --task t-001 --to VERIFY --verdict SUCCESS --note "..."
  python task-state.py --tasks-dir .workbuddy/tasks transition --task t-001 --to REVIEW --bb-add last_verdict=SUCCESS
  python task-state.py --tasks-dir .workbuddy/tasks history --task t-001
  python task-state.py --tasks-dir .workbuddy/tasks trace-export --task t-001 --json
  python task-state.py --tasks-dir .workbuddy/tasks validate --task t-001
  python task-state.py --tasks-dir .workbuddy/tasks checkpoint --task t-001 --context-pointer "sess:turn-42"
  python task-state.py --tasks-dir .workbuddy/tasks resume --task t-001
Exit codes: 0 = ok / 2 = error.
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "task-state.v1"

STATES = {
    "INIT", "UNDERSTAND", "CLASSIFY", "EXPLORE", "PLAN", "IMPLEMENT",
    "VERIFY", "REVIEW", "FINALIZE", "DONE", "DIAGNOSE", "REPAIR",
    "REVERIFY", "ESCALATED", "FAILED",
    # CI/deploy 阶段（v2.5.0, C1-3 — GH 方案 §12）
    "CI_QUEUED", "CI_RUNNING", "CI_PASSED", "CI_FAILED", "REPAIRING",
    "MERGE_PENDING", "STAGING_DEPLOY", "STAGING_VERIFY",
    "PROD_DEPLOY", "PROD_VERIFY", "ROLLBACK",
    # v2.0 (T-08)：可恢复等待态 + 崩溃态。此前 ESCALATED 是唯一"停下来"的方式，
    # 而它是**终态** —— §10.9 tier-4（push 需人工批准）无法建模为"暂停→批准→继续"，
    # 会话崩溃也无处恢复（低配机长会话的实痛）。
    "WAITING", "CRASHED",
}
TERMINAL = {"DONE", "FAILED", "ESCALATED"}
# 从 checkpoint 恢复的目标态（AgentOS F.2：Crash recovery 从 checkpoint 恢复，不重放上下文）
RESUMABLE_STATES = {"IMPLEMENT", "VERIFY", "REVIEW", "FINALIZE", "MERGE_PENDING",
                    "STAGING_DEPLOY", "PROD_DEPLOY", "CI_QUEUED", "REPAIR", "DIAGNOSE"}
VERDICTS = {"SUCCESS", "PARTIAL_SUCCESS", "FAILED", "REGRESSION", "UNKNOWN"}
# Transition table as DATA (ref-20 §2) — editing this table IS the protocol change.
TRANSITIONS: dict[str, set[str]] = {
    "INIT": {"UNDERSTAND"},
    "UNDERSTAND": {"CLASSIFY"},
    "CLASSIFY": {"EXPLORE", "PLAN"},
    "EXPLORE": {"PLAN"},
    "PLAN": {"IMPLEMENT"},
    "IMPLEMENT": {"VERIFY", "FAILED", "WAITING"},
    "VERIFY": {"REVIEW", "DIAGNOSE", "FAILED", "CI_QUEUED", "WAITING"},
    # DIAGNOSE 增 ESCALATED：修复预算耗尽时的**合法出口**（否则 budget 硬闸会死锁）
    "DIAGNOSE": {"REPAIR", "ESCALATED"},
    "REPAIR": {"REVERIFY", "WAITING"},
    "REVERIFY": {"REVIEW", "DIAGNOSE", "ESCALATED"},
    "REVIEW": {"FINALIZE", "DIAGNOSE", "WAITING"},
    "FINALIZE": {"DONE", "WAITING"},
    # WAITING = 可恢复暂停（tier-4 人工批准 / 子代理返回 / 外部门禁）
    "WAITING": set(RESUMABLE_STATES) | {"ESCALATED", "FAILED"},
    # CRASHED = 会话中断/超时，可从 checkpoint 恢复
    "CRASHED": {"REPAIR", "DIAGNOSE", "WAITING", "ESCALATED", "FAILED"},
    # CI/deploy 阶段（C1-3）: CI_QUEUED → CI_RUNNING → CI_PASSED/CI_FAILED；
    # CI_FAILED → REPAIRING（重试预算见 ref-22，超限 → ESCALATED → L5 人类）→ CI_QUEUED；
    # CI_PASSED → MERGE_PENDING → STAGING_DEPLOY → STAGING_VERIFY → PROD_DEPLOY →
    # PROD_VERIFY → DONE；任何部署态可 ROLLBACK。
    "CI_QUEUED": {"CI_RUNNING"},
    "CI_RUNNING": {"CI_PASSED", "CI_FAILED"},
    "CI_FAILED": {"REPAIRING"},
    "REPAIRING": {"CI_QUEUED", "ESCALATED"},
    "CI_PASSED": {"MERGE_PENDING", "REVIEW"},
    "MERGE_PENDING": {"STAGING_DEPLOY", "REVIEW"},
    "STAGING_DEPLOY": {"STAGING_VERIFY", "ROLLBACK"},
    "STAGING_VERIFY": {"PROD_DEPLOY", "ROLLBACK", "REVIEW"},
    "PROD_DEPLOY": {"PROD_VERIFY", "ROLLBACK"},
    "PROD_VERIFY": {"DONE", "ROLLBACK"},
    "ROLLBACK": {"REPAIRING", "DONE", "FAILED"},
    "DONE": set(),
    "FAILED": set(),
    "ESCALATED": set(),
}

# 任意活动态都可能崩溃（会话中断/超时/被杀）——逐条枚举会漏，用数据驱动补齐。
for _s in list(TRANSITIONS):
    if _s not in TERMINAL and _s != "CRASHED":
        TRANSITIONS[_s] = set(TRANSITIONS[_s]) | {"CRASHED"}

# v2.0 (T-09)：确定性循环闸。同一 (from,to) 转移超过阈值 = 振荡（A→B→A→B…），
# ref-22 §7 只写了"有界重试"协议而脚本不判定，等于靠 agent 自觉。
LOOP_GUARD_THRESHOLD = 3
# 消耗修复预算的转移（ref-22 §7 max_repair_attempts）
REPAIR_ENTRY_STATES = {"REPAIR", "REPAIRING"}
# T-10：append-only 事件日志（survey G4）。放 tasks-dir 内，与任务文件同生命周期。
EVENTS_FILENAME = "events.jsonl"


def append_event(tasks_dir: Path, event: dict) -> None:
    """T-10：追加一行 JSONL 事件。ledger 是辅助审计流 —— 写失败仅告警，
    不回滚已发生的状态转移（任务 JSON 才是主真相源，ref-20 §7）。"""
    try:
        tasks_dir.mkdir(parents=True, exist_ok=True)
        with (tasks_dir / EVENTS_FILENAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[warn] event ledger write failed ({type(e).__name__}: {e}) — "
              f"transition persisted, ledger is best-effort", file=sys.stderr)


def read_events(tasks_dir: Path, task_id: str | None = None) -> list[dict]:
    """T-10：读事件流（trace-export 用）。文件缺失/损坏行跳过，不炸读取端。"""
    p = tasks_dir / EVENTS_FILENAME
    if not p.exists():
        return []
    events = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if task_id is None or ev.get("task") == task_id:
            events.append(ev)
    return events


# --- R-10: trace_id 贯穿（ResourceOS §24.2 trace 全链重建）---------------------
# 此前 events.jsonl 有事件但无主键，一次任务的事件散在多条记录里，审计只能靠
# task 字段人工拼 —— 跨任务/跨脚本的链路（workspace 事件、verify 结果引用）更是
# 无从串起。trace_id 是"一次任务"的最小主键：init 生成 → 写入 task JSON 头 →
# 每条 transition 事件 → events.jsonl 每行；trace-export --trace 一键重建。
# ULID 风格（10 字符毫秒时间戳 + 16 字符随机，Crockford base32）—— 时间有序、
# 可按前缀粗排序，且不依赖 uuid 模块以外的任何东西。
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TRACE_ID_LEN = 26


def new_trace_id() -> str:
    """ULID 风格 trace_id：时间有序 + 随机，stdlib only。"""
    n = int(time.time() * 1000)
    ts_part = []
    for _ in range(10):
        ts_part.append(_CROCKFORD[n % 32])
        n //= 32
    rnd = "".join(secrets.choice(_CROCKFORD) for _ in range(16))
    return "".join(reversed(ts_part)) + rnd


def task_trace_id(task: dict | None) -> str | None:
    """取任务的 trace_id；老任务（本字段落地前创建）返回 None，不伪造。"""
    if not isinstance(task, dict):
        return None
    tid = task.get("trace_id")
    return tid if isinstance(tid, str) and tid else None


def events_for_trace(tasks_dir: Path, trace_id: str) -> list[dict]:
    """按 trace_id 跨任务收事件（events.jsonl 全扫 + 过滤）。"""
    return [ev for ev in read_events(tasks_dir) if ev.get("trace_id") == trace_id]


def tasks_for_trace(tasks_dir: Path, trace_id: str) -> list[str]:
    """反查带有该 trace_id 的任务文件（任务 JSON 头也写了 trace_id）。"""
    if not tasks_dir.exists():
        return []
    out = []
    for p in sorted(tasks_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and data.get("trace_id") == trace_id:
            out.append(p.stem)
    return out


def make_event(kind: str, task_id: str, actor: str, trace_id: str | None = None,
               **extra) -> dict:
    ev: dict = {"ts": now_iso(), "event": kind, "task": task_id,
                "actor": actor or "agent"}
    # R-10：trace_id 放在 task 之后，保持既有字段顺序（读取端按 key 取值，不受影响）
    if trace_id:
        ev["trace_id"] = trace_id
    ev.update(extra)
    return ev


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def task_path(tasks_dir: Path, task_id: str) -> Path:
    return tasks_dir / f"{task_id}.json"


def load_task(path: Path) -> dict:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[fatal] invalid JSON in {path}", file=sys.stderr)
        sys.exit(2)
    return data


def save_task(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def new_task(task_id: str, title: str, mode: str, bb: dict,
             priority: str = "P2", acceptance: str = "", branch: str = "",
             workspace: str = "", max_repair: int = 3,
             depends_on: list[str] | None = None,
             done_when: str = "", trace_id: str | None = None) -> dict:
    ts = now_iso()
    return {
        "schema": SCHEMA, "task_id": task_id,
        # R-10：一次任务的主键，贯穿 task JSON 头 / transition 事件 / events.jsonl
        "trace_id": trace_id or new_trace_id(),
        "title": title, "mode": mode,
        "state": "INIT", "verdict": None,
        "priority": priority, "acceptance_criteria": acceptance,
        # T-08（AgentOS #3）：任务级显式完成条件 + finalize 证据位
        "done_when": done_when, "done_evidence": None,
        "branch": branch or None, "workspace": workspace or None,
        # T-14：DAG 依赖（AgentOS F.3）
        "depends_on": list(depends_on or []),
        "runs": [],
        # v2.0: 崩溃恢复点（T-08）+ 修复预算（T-09）
        "checkpoint": None,
        "repair_budget": {"max": max_repair, "used": 0},
        "created_at": ts, "updated_at": ts,
        "history": [{"ts": ts, "from": None, "to": "INIT", "verdict": None, "note": "created"}],
        "blackboard": {"recent_actions": [], "known_failures": [], "residuals": [], "facts": bb or {}},
    }


def check_repair_budget(task: dict, nxt: str) -> dict:
    """T-09：进入 REPAIR/REPAIRING 前检查预算。确定性闸门，不靠 agent 自觉。"""
    budget = task.setdefault("repair_budget", {"max": 3, "used": 0})
    used, mx = budget.get("used", 0), budget.get("max", 3)
    if nxt not in REPAIR_ENTRY_STATES:
        return {"applies": False, "used": used, "max": mx, "exhausted": False}
    # max <= 0 = 无限制（显式选择，不是"零次"）
    exhausted = mx > 0 and used >= mx
    return {"applies": True, "used": used, "max": mx,
            "exhausted": exhausted,
            "reason": (f"repair budget exhausted ({used}/{mx}) — max_repair_attempts 见 ref-22 §7；"
                       f"转 ESCALATED（L5 人类）是唯一合法出口") if used >= mx else None}


def check_dependencies(task: dict, tasks_dir: Path) -> dict:
    """T-14：DAG 依赖检查（AgentOS F.3 —— actor + 事件状态机 + DAG 混合模型）。

    只有 DONE 的依赖算完成；缺失的任务文件单独列出（悬空依赖，拼写错误的常见症状）。
    """
    deps = task.get("depends_on") or []
    if not deps:
        return {"applies": False, "ready": True, "unfinished": [], "missing": []}
    unfinished, missing = [], []
    for dep in deps:
        p = task_path(tasks_dir, dep)
        if not p.exists():
            missing.append(dep)
            continue
        dep_task = load_task(p)
        state = (dep_task or {}).get("state")
        if state != "DONE":
            unfinished.append({"task": dep, "state": state})
    return {"applies": True, "ready": not unfinished and not missing,
            "unfinished": unfinished, "missing": missing,
            "reason": (f"blocked by dependencies: "
                       f"{[u['task'] for u in unfinished]}{' (missing: %s)' % missing if missing else ''}"
                       f" — 先完成依赖任务，或 --depends-on 修正") if unfinished or missing else None}


def detect_loop(task: dict, frm: str, to: str) -> dict:
    """T-09：同一 (from,to) 转移次数超阈值 = 振荡。确定性检测，可 --allow-loop 显式放行。"""
    hist = task.get("history", [])
    seen = sum(1 for h in hist if h.get("from") == frm and h.get("to") == to)
    occurrences = seen + 1
    detected = occurrences > LOOP_GUARD_THRESHOLD
    return {"detected": detected, "pair": f"{frm}->{to}", "occurrences": occurrences,
            "threshold": LOOP_GUARD_THRESHOLD,
            "reason": (f"oscillation: {frm}->{to} repeated {occurrences}x "
                       f"(> {LOOP_GUARD_THRESHOLD}) — 转 ESCALATED（L5 人类）或 --allow-loop 显式放行")
                      if detected else None}


def check_done_gate(task: dict, nxt: str, evidence: str | None,
                    cur: str | None = None) -> dict:
    """T-08（AgentOS #3）：FINALIZE→DONE 完成条件闸 —— 任务级显式完成条件。
    有 done-when/acceptance：必须附 --done-evidence（如何满足条件）；
    两者皆无：不得 finalize（无完成条件的任务谈不上完成）。
    作用域仅 FINALIZE→DONE —— PROD_VERIFY→DONE 等 CI/部署链路有自己的
    分层验证（CI_QUEUED→…→PROD_VERIFY），不重复设卡（C1-3 契约不变）。"""
    if nxt != "DONE" or cur != "FINALIZE":
        return {"applies": False, "ok": True}
    condition = (task.get("done_when") or task.get("acceptance_criteria") or "").strip()
    if evidence:
        return {"applies": True, "ok": True, "condition": condition,
                "reason": (None if condition else
                           "no done-when/acceptance recorded — evidence accepted but "
                           "condition is empty (建议 init --done-when 补结构化条件)")}
    return {"applies": True, "ok": False, "condition": condition,
            "reason": ("done-when 未附完成证据 —— FINALIZE→DONE 必须带 "
                       "--done-evidence <如何满足条件>（AgentOS #3 完成条件闸）"
                       if condition else
                       "任务无 done-when/acceptance —— 先 init --done-when 定义完成条件 "
                       "再 finalize（AgentOS #3 任务级显式完成条件）")}


def write_checkpoint(task: dict, context_pointer: str = "", workspace_ref: str = "") -> dict:
    """T-08：快照 {state, context_pointer, workspace_ref}，供崩溃后精确恢复。"""
    cp = {"ts": now_iso(), "state": task["state"],
          "context_pointer": context_pointer or task.get("branch") or "",
          "workspace_ref": workspace_ref or task.get("workspace") or ""}
    task["checkpoint"] = cp
    return cp


def validate_transitions(task: dict) -> list[str]:
    problems = []
    state = task.get("state")
    if state not in STATES:
        problems.append(f"unknown state: {state!r}")
        return problems
    for i in range(1, len(task.get("history", []))):
        prev = task["history"][i - 1].get("to")
        cur = task["history"][i].get("from")
        if prev != cur:
            problems.append(f"history[{i}] from={cur!r} does not match previous to={prev!r}")
    return problems


def cmd_autonomy(tasks_dir: Path, args) -> int:
    """A-10（AOS §12）：AutonomyScore —— report-only，绝不做成放行闸。

    关键区分（否则指标会被"永不追问"反向游戏）：
      necessary = WAITING/ESCALATED 且命中 tier-4 语义（push/凭据/不可逆 —— §10 规则 2
                  的结构性人审，是**必须**停下来的）
      avoidable = 其余 WAITING/ESCALATED（本可自己查到/脚本已知答案却去问人）
    """
    tasks: list[dict] = []
    if args.task:
        t = load_task(task_path(tasks_dir, args.task))
        if t is None:
            print(f"[fatal] task not found: {args.task}", file=sys.stderr)
            return 2
        tasks = [t]
    else:
        if not tasks_dir.exists():
            print(f"[fatal] tasks dir not found: {tasks_dir}", file=sys.stderr)
            return 2
        for p in sorted(tasks_dir.glob("*.json")):
            t = load_task(p)
            if t:
                tasks.append(t)

    HINTS = ("push", "tier-4", "tier4", "credential", "凭据", "secret",
             "irreversible", "不可逆", "human approval", "人审")
    total = len(tasks)
    necessary = avoidable = 0
    per_task = []
    for t in tasks:
        n_i = a_i = 0
        for e in t.get("history") or []:
            if e.get("to") not in ("WAITING", "ESCALATED"):
                continue
            note = f"{e.get('note') or ''} {e.get('verdict') or ''}".lower()
            if any(h in note for h in HINTS):
                necessary += 1
                n_i += 1
            else:
                avoidable += 1
                a_i += 1
        per_task.append({"task": t.get("id"), "state": t.get("state"),
                         "necessary": n_i, "avoidable": a_i})
    interventions = necessary + avoidable
    score = (1.0 - (avoidable / total)) if total else None
    out = {"schema": "autonomy.v1", "tasks": total, "interventions": interventions,
           "necessary": necessary, "avoidable": avoidable,
           "blocking_intervention_rate": round(interventions / total, 6) if total else None,
           "autonomy_score": None if score is None else round(max(0.0, min(1.0, score)), 6),
           "report_only": True,
           "note": ("report-only：tier-4 人审是 §10 规则 2 的结构性要求，不计入扣分；"
                    "本指标只用于观察「可避免干预」是否变多（D3 裁决）"
                    if total else "no tasks — 无样本，不给分（不猜）"),
           "per_task": per_task}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"== autonomy · tasks={total} ==")
        print(f"  interventions: {interventions} (necessary={necessary} avoidable={avoidable})")
        print(f"  autonomy_score: {'-' if score is None else f'{score:.4f}'}  (report-only)")
        print(f"  note: {out['note']}")
    return 0


def cmd_bisect(tasks_dir: Path, args) -> int:
    """A-7（AOS §25.4）：沿 checkpoint 二分定位"最早不可恢复点"。

    谓词由调用方提供：exit 0 = 从该 checkpoint 起仍可能通过。单调性不成立时
    退回线性扫描并标注 non_monotonic —— 二分在非单调序列上给出的答案是错的，
    不能装作是对的（§40.2-5 正是这个工程难题）。
    """
    t = load_task(task_path(tasks_dir, args.task))
    if t is None:
        print(f"[fatal] task not found: {args.task}", file=sys.stderr)
        return 2
    cps = t.get("checkpoints") or []
    if not cps:
        print("[fatal] no checkpoints for this task — 无打点可二分", file=sys.stderr)
        return 2

    def check_cmd(state_path: Path) -> list[str]:
        """模板 → argv。Windows 下不能用 posix 切分（反斜杠会被当转义吃掉），
        故 posix=False 保留原样，再剥掉成对引号（支持 `--check "cmd with args"`）。"""
        try:
            import shlex
            toks = shlex.split(args.check, posix=False)
        except ValueError:
            toks = args.check.split()
        out = []
        for raw in toks:
            t = raw.replace("{state}", str(state_path))
            if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
                t = t[1:-1]
            out.append(t)
        return out

    def probe(idx: int) -> bool:
        with tempfile.TemporaryDirectory() as d:
            sp = Path(d) / f"cp-{idx}.json"
            sp.write_text(json.dumps(cps[idx], ensure_ascii=False), encoding="utf-8")
            try:
                r = subprocess.run(check_cmd(sp), capture_output=True, text=True, timeout=120)
                return r.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                return False

    lo, hi = 0, len(cps) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if probe(mid):
            lo = mid + 1
        else:
            hi = mid
    seq = [probe(i) for i in range(len(cps))]
    first_false = next((i for i, v in enumerate(seq) if not v), None)
    # 单调 = 首个 False 之后不再出现 True
    monotonic = first_false is None or not any(seq[first_false:])
    idx = lo if monotonic else first_false
    out = {"schema": "bisect.v1", "task": args.task, "checkpoints": len(cps),
           "diverged_index": idx, "diverged_checkpoint": cps[idx] if idx is not None else None,
           "sequence": "".join("T" if v else "F" for v in seq), "monotonic": monotonic,
           "note": ("二分有效（单调）" if monotonic else
                    "非单调：二分结果不可信，已退回线性扫描取首个不可恢复点")}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"== bisect · task={args.task} · checkpoints={len(cps)} ==")
        print(f"  sequence: {out['sequence']}")
        print(f"  diverged_index: {idx}   monotonic={monotonic}")
        print(f"  note: {out['note']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Task state machine persistence (ref-20)")
    ap.add_argument("--tasks-dir", default=".workbuddy/tasks", help="task store dir (default: ./.workbuddy/tasks)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="create a new task (state=INIT)")
    i.add_argument("--task", required=True)
    i.add_argument("--title", required=True)
    i.add_argument("--mode", default="Engineering", help="SDK mode (Vibe/Engineering/SDD/Debug/Review/Quick Edit)")
    i.add_argument("--bb", default=None, help='JSON: initial blackboard facts {"k":"v"}')
    i.add_argument("--priority", default="P2", choices=["P0", "P1", "P2", "P3"],
                   help="task priority (production field, C1-2)")
    i.add_argument("--acceptance", default="", help="acceptance criteria (C1-2)")
    i.add_argument("--branch", default="", help="feature branch (C1-2)")
    i.add_argument("--workspace", default="", help="task workspace dir (C1-2, see task-workspace.py)")
    i.add_argument("--max-repair", type=int, default=3,
                   help="max_repair_attempts (ref-22 §7, T-09) — 0 = unlimited")
    i.add_argument("--depends-on", default="",
                   help="comma-separated task ids this task blocks on (T-14, DAG)")
    i.add_argument("--done-when", default="",
                   help="structured completion condition (T-08, AgentOS #3) — checked at FINALIZE->DONE")
    i.add_argument("--actor", default="agent", help="actor for the event ledger (T-10)")
    i.add_argument("--trace-id", default=None,
                   help="R-10：外部指定 trace_id（不传则自动生成 ULID 风格 id）")

    t = sub.add_parser("transition", help="advance state (transition table is data)")
    t.add_argument("--task", required=True)
    t.add_argument("--to", required=True)
    t.add_argument("--verdict", default=None, choices=sorted(VERDICTS),
                   help="five-state verdict (§5.6) — judgment stays with agent")
    t.add_argument("--note", default="")
    t.add_argument("--bb-add", default=None, help="key=value (JSON value) written to blackboard.facts")
    t.add_argument("--run-id", default=None, help="CI workflow_run_id for run record (C1-2)")
    t.add_argument("--pr", default=None, help="PR number for run record (C1-2)")
    t.add_argument("--attempt", default=None, help="attempt number for run record (C1-2)")
    t.add_argument("--allow-loop", action="store_true",
                   help="explicitly allow a repeating transition (人类显式放行振荡)")
    t.add_argument("--context-pointer", default="", help="checkpoint: pointer to context (T-08)")
    t.add_argument("--workspace-ref", default="", help="checkpoint: workspace ref (T-08)")
    t.add_argument("--done-evidence", default=None,
                   help="how done-when/acceptance was met — REQUIRED for FINALIZE->DONE (T-08)")
    t.add_argument("--actor", default="agent", help="actor for the event ledger (T-10)")
    t.add_argument("--idempotency-key", default=None,
                   help="T-26 (v2.10.0): same key + same (from,to) is a no-op replay "
                        "(budget NOT consumed, ledger records duplicate_ignored); "
                        "same key with a different target -> exit 2 (caller bug)")

    ck = sub.add_parser("checkpoint", help="manually snapshot {state, context, workspace} (T-08)")
    ck.add_argument("--task", required=True)
    ck.add_argument("--context-pointer", default="")
    ck.add_argument("--workspace-ref", default="")

    rs = sub.add_parser("resume", help="resume a CRASHED task from its checkpoint (T-08)")
    rs.add_argument("--task", required=True)
    rs.add_argument("--to", default=None,
                    help="explicit resume target state (default: checkpoint.state)")
    rs.add_argument("--note", default="resumed from checkpoint")
    rs.add_argument("--actor", default="agent", help="actor for the event ledger (T-10)")

    h = sub.add_parser("history", help="show history")
    h.add_argument("--task", required=True)
    h.add_argument("--json", action="store_true")

    te = sub.add_parser("trace-export", help="full task JSON (state + history + blackboard)")
    te.add_argument("--task", default=None, help="按任务导出（task JSON + 其事件）")
    te.add_argument("--trace", default=None,
                    help="R-10：按 trace_id 跨任务重建全链（events.jsonl 全扫 + 反查带该 id 的任务）")
    te.add_argument("--json", action="store_true")

    ep = sub.add_parser("escalation-pack",
                        help="L5 human escalation packet: 7 high-signal fields (T-24, agentic-cicd §16)")
    ep.add_argument("--task", required=True)
    ep.add_argument("--diff-file", default=None, help="unified diff file (truncated to --max-diff-lines)")
    ep.add_argument("--failed-tests", default="", help="comma-separated failing tests")
    ep.add_argument("--risk", default=None, help="risk line (default: derived from priority+state)")
    ep.add_argument("--recommended", default=None, help="override recommended_action")
    ep.add_argument("--max-diff-lines", type=int, default=100)
    ep.add_argument("--json", action="store_true")

    au = sub.add_parser("autonomy", help="A-10：自主性评分（report-only，区分必要/可避免干预）")
    au.add_argument("--task", default=None, help="单任务；不给则统计整个 --tasks-dir")
    au.add_argument("--json", action="store_true")
    bs = sub.add_parser("bisect", help="A-7：沿 checkpoint 二分定位最早分歧点（AOS §25.4）")
    bs.add_argument("--task", required=True)
    bs.add_argument("--check", required=True,
                    help='谓词命令模板，{state} 会被替换为该 checkpoint 状态的临时 JSON 路径；'
                         'exit 0 = "从这里起仍可能通过"')
    bs.add_argument("--json", action="store_true")
    v = sub.add_parser("validate", help="schema + transition-chain validation")
    v.add_argument("--task", required=True)

    args = ap.parse_args()
    tasks_dir = Path(args.tasks_dir)

    if args.cmd == "init":
        path = task_path(tasks_dir, args.task)
        if path.exists():
            print(f"[fatal] task already exists: {path}", file=sys.stderr)
            return 2
        bb = {}
        if args.bb:
            try:
                bb = json.loads(args.bb)
            except json.JSONDecodeError:
                print("[fatal] --bb is not valid JSON", file=sys.stderr)
                return 2
            if not isinstance(bb, dict):
                print("[fatal] --bb must be a JSON object", file=sys.stderr)
                return 2
        task = new_task(args.task, args.title, args.mode, bb,
                        priority=args.priority, acceptance=args.acceptance,
                        branch=args.branch, workspace=args.workspace,
                        max_repair=args.max_repair,
                        depends_on=[d.strip() for d in args.depends_on.split(",") if d.strip()],
                        done_when=args.done_when,
                        trace_id=getattr(args, "trace_id", None))
        save_task(path, task)
        append_event(tasks_dir, make_event("created", args.task, args.actor,
                                           trace_id=task_trace_id(task),
                                           to="INIT", done_when=args.done_when or None))
        print(json.dumps({"created": args.task, "state": "INIT",
                          "priority": task["priority"], "branch": task["branch"],
                          "workspace": task["workspace"], "done_when": task["done_when"],
                          "trace_id": task["trace_id"],
                          "path": str(path)},
                         ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "transition":
        path = task_path(tasks_dir, args.task)
        task = load_task(path)
        if task is None:
            print(f"[fatal] task not found: {path}", file=sys.stderr)
            return 2
        cur = task["state"]
        if cur in TERMINAL:
            print(f"[fatal] terminal state {cur} — no further transitions", file=sys.stderr)
            return 2
        nxt = args.to.upper()
        if nxt not in STATES:
            print(f"[fatal] unknown state: {nxt}", file=sys.stderr)
            return 2
        # T-26 硬闸（v2.10.0, F-35）：幂等键 —— 重试/重放不得双执行（agentic-cicd 原则 9）。
        # 必须先于合法性/预算/振荡闸：真正的重放发生在 cur==已应用目标态 时
        # （PLAN->IMPLEMENT 已生效后重试，cur 已是 IMPLEMENT），此时合法性检查
        # 会先报 illegal —— 幂等键要在它之前接住。判据：seen.to == nxt 即为重放。
        idem = getattr(args, "idempotency_key", None)
        if idem:
            seen = (task.setdefault("idempotency_keys", {}) or {}).get(idem)
            if seen:
                if seen.get("to") == nxt:
                    append_event(tasks_dir, make_event("duplicate_ignored", args.task, args.actor,
                                                       trace_id=task_trace_id(task),
                                                       **{"from": cur, "to": nxt, "verdict": None,
                                                          "reason": "idempotency_key"}))
                    print(json.dumps({"task": args.task, "duplicate": True, "key": idem,
                                      "state": cur, "to": nxt,
                                      "note": "already applied — repair budget not consumed"},
                                     ensure_ascii=False, indent=2))
                    return 0
                print(f"[fatal] idempotency key {idem!r} already used for "
                      f"{seen.get('from')}->{seen.get('to')} — reuse with a different "
                      f"target is a caller bug", file=sys.stderr)
                return 2
        if nxt not in TRANSITIONS.get(cur, set()):
            print(f"[fatal] illegal transition: {cur} -> {nxt} (allowed: {sorted(TRANSITIONS[cur])})",
                  file=sys.stderr)
            return 2
        # T-14 硬闸：依赖未完成不得开工（IMPLEMENT = 实际动工点）
        deps = check_dependencies(task, tasks_dir)
        if deps["applies"] and nxt == "IMPLEMENT" and not deps["ready"]:
            print(f"[fatal] {deps['reason']}", file=sys.stderr)
            return 2
        # T-09 硬闸 1：修复预算（ref-22 §7 max_repair_attempts=3）
        budget = check_repair_budget(task, nxt)
        if budget["exhausted"]:
            print(f"[fatal] {budget['reason']}", file=sys.stderr)
            return 2
        # T-09 硬闸 2：振荡/循环检测（A→B→A…）
        loop = detect_loop(task, cur, nxt)
        if loop["detected"] and not getattr(args, "allow_loop", False):
            print(f"[fatal] {loop['reason']}", file=sys.stderr)
            task["blackboard"]["facts"]["loop_guard"] = loop
            task["updated_at"] = now_iso()
            save_task(path, task)
            append_event(tasks_dir, make_event("transition_rejected", args.task, args.actor,
                                               trace_id=task_trace_id(task),
                                               **{"from": cur, "to": nxt, "verdict": None,
                                                  "reason": "loop_guard"}))
            return 2
        # T-08 硬闸 3：完成条件（FINALIZE→DONE 必须附证据 / 无条件不得 finalize）
        done_gate = check_done_gate(task, nxt, getattr(args, "done_evidence", None), cur)
        if done_gate.get("applies") and not done_gate.get("ok"):
            print(f"[fatal] {done_gate['reason']}", file=sys.stderr)
            return 2
        if args.bb_add:
            key, _, raw = args.bb_add.partition("=")
            try:
                task["blackboard"]["facts"][key] = json.loads(raw)
            except json.JSONDecodeError:
                print("[fatal] --bb-add value must be JSON", file=sys.stderr)
                return 2
        task["history"].append({"ts": now_iso(), "from": cur, "to": nxt,
                                "verdict": args.verdict, "note": args.note})
        task["state"] = nxt
        if nxt in REPAIR_ENTRY_STATES:
            task.setdefault("repair_budget", {"max": 3, "used": 0})
            task["repair_budget"]["used"] = task["repair_budget"].get("used", 0) + 1
        # T-08：关键节点自动 checkpoint（AgentOS F.2 —— 崩溃恢复从 checkpoint，不重放上下文）
        # 注意：**不能**在 CRASHED 上打点 —— 那会用崩溃态覆盖上一个好状态，
        # 使 resume 恢复到 CRASHED 自己（恢复了个寂寞）。CRASHED 只消费 checkpoint，不写。
        if nxt in ("VERIFY", "REVIEW", "WAITING"):
            write_checkpoint(task, getattr(args, "context_pointer", "") or "",
                             getattr(args, "workspace_ref", "") or "")
        if args.verdict:
            task["verdict"] = args.verdict
        # T-08：完成证据随 DONE 落位（审计可回溯：条件 + 证据 + 时间）
        if nxt == "DONE" and getattr(args, "done_evidence", None):
            task["done_evidence"] = {"ts": now_iso(), "text": args.done_evidence,
                                     "condition": done_gate.get("condition") or ""}
        if args.run_id or args.pr or args.attempt:
            task.setdefault("runs", []).append({
                "ts": now_iso(), "state": nxt,
                "workflow_run_id": args.run_id, "pr_number": args.pr,
                "attempt": args.attempt,
            })
        if idem:
            task.setdefault("idempotency_keys", {})[idem] = {
                "from": cur, "to": nxt, "ts": now_iso()}
        task["updated_at"] = now_iso()
        save_task(path, task)
        append_event(tasks_dir, make_event("transition", args.task, args.actor,
                                           trace_id=task_trace_id(task),
                                           **{"from": cur, "to": nxt, "verdict": args.verdict}))
        out = {"task": args.task, "from": cur, "to": nxt, "verdict": args.verdict,
               # R-10：每次转移都把 trace_id 吐出来，调用方无需回读任务文件即可串联
               "trace_id": task_trace_id(task)}
        if done_gate.get("applies"):
            out["done_gate"] = done_gate
        if budget["applies"]:
            out["repair_budget"] = task["repair_budget"]
        if deps["applies"]:
            out["dependencies"] = deps
        if loop["occurrences"] > 1:
            out["loop"] = loop
        if task.get("checkpoint") and nxt in ("VERIFY", "REVIEW", "WAITING"):
            out["checkpoint"] = task["checkpoint"]
        if task.get("runs"):
            out["last_run"] = task["runs"][-1]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "checkpoint":
        path = task_path(tasks_dir, args.task)
        task = load_task(path)
        if task is None:
            print(f"[fatal] task not found: {path}", file=sys.stderr)
            return 2
        cp = write_checkpoint(task, args.context_pointer, args.workspace_ref)
        task["updated_at"] = now_iso()
        save_task(path, task)
        print(json.dumps({"task": args.task, "checkpoint": cp}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "resume":
        path = task_path(tasks_dir, args.task)
        task = load_task(path)
        if task is None:
            print(f"[fatal] task not found: {path}", file=sys.stderr)
            return 2
        cur = task["state"]
        if cur != "CRASHED":
            print(f"[fatal] resume only valid from CRASHED (current: {cur})", file=sys.stderr)
            return 2
        cp = task.get("checkpoint") or {}
        target = (args.to or cp.get("state") or "").upper()
        if not target:
            print("[fatal] no checkpoint and no --to: cannot determine resume target",
                  file=sys.stderr)
            return 2
        if target not in RESUMABLE_STATES:
            print(f"[fatal] resume target {target} not resumable (allowed: {sorted(RESUMABLE_STATES)})",
                  file=sys.stderr)
            return 2
        task["history"].append({"ts": now_iso(), "from": cur, "to": target,
                                "verdict": None, "note": args.note})
        task["state"] = target
        task["updated_at"] = now_iso()
        save_task(path, task)
        append_event(tasks_dir, make_event("resume", args.task, args.actor,
                                           trace_id=task_trace_id(task),
                                           **{"from": cur, "to": target, "verdict": None}))
        print(json.dumps({"task": args.task, "from": cur, "to": target,
                          "restored_from_checkpoint": cp, "note": args.note},
                         ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "history":
        path = task_path(tasks_dir, args.task)
        task = load_task(path)
        if task is None:
            print(f"[fatal] task not found: {path}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps({"task": args.task, "history": task["history"]},
                             ensure_ascii=False, indent=2))
        else:
            print(f"== task {args.task}: state={task['state']} verdict={task['verdict']}")
            for e in task["history"]:
                print(f"  {e['ts'][:19]}  {str(e['from']):<10} -> {e['to']:<10} "
                      f"v={e['verdict'] or '-'}  {e['note'][:60]}")
        return 0

    if args.cmd == "autonomy":
        return cmd_autonomy(tasks_dir, args)

    if args.cmd == "bisect":
        return cmd_bisect(tasks_dir, args)

    if args.cmd == "trace-export":
        # R-10：--trace 按 trace_id 跨任务重建（§24.2）。--task 与 --trace 二选一，
        # 都不给 = 用法错误 exit 2（不猜调用方意图）。
        if not args.task and not args.trace:
            print("[fatal] trace-export requires --task or --trace", file=sys.stderr)
            return 2
        if args.trace:
            tid = args.trace.strip()
            events = events_for_trace(tasks_dir, tid)
            task_ids = tasks_for_trace(tasks_dir, tid)
            if not events and not task_ids:
                print(f"[fatal] trace_id not found: {tid}", file=sys.stderr)
                return 2
            out = {"schema": "trace.v1", "trace_id": tid, "tasks": task_ids,
                   "event_count": len(events), "events": events}
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=2))
            else:
                print(f"== trace {tid} ==")
                print(f"  tasks: {', '.join(task_ids) or '-'}")
                print(f"  events: {len(events)}")
                for ev in events:
                    print(f"  - {ev.get('ts')} [{ev.get('event')}] "
                          f"{ev.get('task')} {ev.get('from')} -> {ev.get('to')}")
            return 0
        path = task_path(tasks_dir, args.task)
        task = load_task(path)
        if task is None:
            print(f"[fatal] task not found: {path}", file=sys.stderr)
            return 2
        # T-10：trace 改读 append-only 事件流（ledger 缺失 = 旧任务，events 为空列表）
        events = read_events(tasks_dir, args.task)
        if args.json:
            out = dict(task)
            out["events"] = events
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"== task {args.task} (state={task['state']}) ==")
            print(f"  trace_id: {task_trace_id(task) or '-'}")
            print(f"  title: {task['title']}  mode: {task['mode']}")
            print(f"  done_when: {task.get('done_when') or '-'}")
            print(f"  blackboard.facts: {json.dumps(task['blackboard']['facts'], ensure_ascii=False)}")
            print(f"  known_failures: {task['blackboard']['known_failures']}")
            print(f"  residuals: {task['blackboard']['residuals']}")
            print(f"  events: {len(events)} in ledger (last 10)")
            for ev in events[-10:]:
                print(f"    {ev.get('ts', '?')[:19]}  {ev.get('event', '?'):<20}"
                      f" {str(ev.get('from')):>10} -> {str(ev.get('to')):<10}"
                      f" actor={ev.get('actor', '-')}")
            print("  (full trace with --json)")
        return 0

    if args.cmd == "escalation-pack":
        path = task_path(tasks_dir, args.task)
        task = load_task(path)
        if task is None:
            print(f"[fatal] task not found: {path}", file=sys.stderr)
            return 2
        # T-24（v2.10.0, F-34）：升级包七字段（agentic-cicd §16）—— 高信号、非原始日志
        # 倾倒（G1）。事件台账是唯一事实源：attempted_fixes 从 REPAIR 族转移聚合。
        events = read_events(tasks_dir, args.task)
        repair_ev = [e for e in events if e.get("to") in ("REPAIR", "REPAIRING", "REVERIFY")]
        attempted = [f"{str(e.get('ts', '?'))[:19]}  {e.get('from')}->{e.get('to')}"
                     + (f"  verdict={e.get('verdict')}" if e.get("verdict") else "")
                     for e in repair_ev]
        recent = [f"{str(e.get('ts', '?'))[:19]}  {e.get('event'):<20} "
                  f"{str(e.get('from'))}->{str(e.get('to'))}"
                  + (f"  reason={e.get('reason')}" if e.get("reason") else "")
                  for e in events]
        failed_tests = [s.strip() for s in args.failed_tests.split(",") if s.strip()]

        diff_block = "(no diff attached)"
        if args.diff_file:
            dp = Path(args.diff_file)
            if not dp.exists():
                print(f"[fatal] diff file not found: {dp}", file=sys.stderr)
                return 2
            dlines = dp.read_text(encoding="utf-8", errors="replace").splitlines()
            tag = "" if len(dlines) <= args.max_diff_lines else (
                f"\n... (truncated: {len(dlines) - args.max_diff_lines} of "
                f"{len(dlines)} lines omitted — full diff at {dp.name})")
            diff_block = "\n".join(dlines[:args.max_diff_lines]) + tag

        last_verdict = next((e.get("verdict") for e in reversed(events) if e.get("verdict")), None)
        recommended = args.recommended or (
            "manual review with the attempt lineage below; "
            + ("consider reverting the last repair (last verdict=%s)" % last_verdict
               if last_verdict in ("FAILED", "REGRESSION")
               else "inspect the failing evidence before any further automated repair"))

        pack = {
            "schema": "escalation-pack.v1",
            "task": args.task,
            "problem": f"task {args.task!r} escalated at state {task['state']}"
                       + (f" — {task['title']}" if task.get("title") else ""),
            "evidence": recent[-6:],
            "attempted_fixes": attempted[-5:],
            "failed_tests": failed_tests,
            "relevant_diff": diff_block,
            "risk": args.risk or f"priority={task.get('priority')}, state={task['state']}",
            "recommended_action": recommended,
        }
        if args.json:
            print(json.dumps(pack, ensure_ascii=False, indent=2))
        else:
            for k in ("problem", "risk", "recommended_action"):
                print(f"## {k}: {pack[k]}")
            print("## evidence:")
            for ln in pack["evidence"]:
                print(f"  - {ln}")
            print("## attempted_fixes:")
            for ln in pack["attempted_fixes"] or ["(none recorded)"]:
                print(f"  - {ln}")
            print("## failed_tests: " + (", ".join(pack["failed_tests"]) or "(none declared)"))
            print("## relevant_diff:")
            print(pack["relevant_diff"])
        return 0

    if args.cmd == "validate":
        path = task_path(tasks_dir, args.task)
        task = load_task(path)
        if task is None:
            print(f"[fatal] task not found: {path}", file=sys.stderr)
            return 2
        problems = []
        for key in ("schema", "task_id", "state", "history", "blackboard"):
            if key not in task:
                problems.append(f"missing key: {key}")
        problems += validate_transitions(task)
        if task.get("verdict") not in (None, *VERDICTS):
            problems.append(f"invalid verdict: {task['verdict']!r}")
        # C1-2 production fields: optional (old tasks stay valid), typed when present
        if task.get("priority") is not None and task["priority"] not in ("P0", "P1", "P2", "P3"):
            problems.append(f"invalid priority: {task['priority']!r}")
        for fld in ("acceptance_criteria", "branch", "workspace"):
            if fld in task and task[fld] is not None and not isinstance(task[fld], str):
                problems.append(f"invalid {fld} type: {type(task[fld]).__name__}")
        # T-08：done-when（字符串）与 done_evidence（{ts,text,condition} 或 null）类型闸
        if "done_when" in task and task["done_when"] is not None \
                and not isinstance(task["done_when"], str):
            problems.append(f"invalid done_when type: {type(task['done_when']).__name__}")
        de = task.get("done_evidence")
        if de is not None and not (isinstance(de, dict) and isinstance(de.get("text"), str)):
            problems.append("done_evidence must be a {ts,text,condition} object or null")
        runs = task.get("runs", [])
        if not isinstance(runs, list):
            problems.append("runs must be a list")
        for r in runs:
            if not isinstance(r, dict) or "state" not in r:
                problems.append(f"bad run record: {r!r}")
        deps = task.get("depends_on", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            problems.append("depends_on must be a list of task ids")
        if problems:
            print(json.dumps({"task": args.task, "valid": False, "problems": problems},
                             ensure_ascii=False, indent=2))
            return 2
        out = {"task": args.task, "valid": True, "state": task["state"]}
        if deps:
            out["dependencies"] = check_dependencies(task, tasks_dir)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
