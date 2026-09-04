#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
action-gate.py — Action Validator 预执行门（T-25 / F-38 / F-35，v2.10.0）

Why: 两份架构文档与上轮自查的收敛缺口 ——
  * AgentOS Top4「Action Validator 预执行门」（v2.7.0 自查列 Top5 只落 4 项，悬空两轮）；
  * agentic-cicd §3.2 Agent Tool Gateway：agent 的每个动作先过统一校验点
    （工具存在 / 参数合法 / 风险分级核对），才允许触达真实基础设施；
  * toolstack.json 的 `idempotent` 元数据自 v2.4.0 起零消费方（F-35）——本脚本
    是它的第一个消费方：幂等的工具允许安全重试，非幂等的重试前必须显式声明。

Policy (deterministic, §10.9 risk tiers):
  decision  条件
  --------  ------------------------------------------------------------
  ALLOW     工具存在 且 risk_tier <= 2（安全可逆）
  ALLOW*    risk_tier == 3 —— 放行但附条件（独立交叉核对 + 回滚验证，
            agent 必须先满足并在产出中记录；exit 0，conditions 字段非空）
  DENY      工具不在 toolstack（先 probe-tools.py 探测）或 risk_tier >= 4
            （不可逆/凭据 —— 结构性人工闸门，exit 2；--user-approved 仅在
            用户显式确认后可传，记入 human_approval 审计字段）
  DENY      --args-json 不是合法 JSON（参数先于执行失败，fail-closed）

Usage:
  python action-gate.py --tool ocr --json
  python action-gate.py --tool diff-risk --args-json '{"files":"a.py"}' --json
  python action-gate.py --tool git-push --user-approved --json     # tier-4：仅用户确认后
Exit: 0 = ALLOW / 2 = DENY（fail-closed）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from _common import (EXIT_OK, EXIT_ERROR, EXIT_GATE, emit_json,
                   now_iso, schema, build_parser, add_json_flag)

SCRIPT_DIR = Path(__file__).resolve().parent
TOOLSTACK = SCRIPT_DIR / "toolstack.json"
SCHEMA = schema("action-gate")

# cicd §15（P3 清偿 v2.10.6）：策略版本钉 —— 风险分级决策表是策略面。变更分级/
# 决策规则 = 变策略 = 显式 bump 本常量 + CHANGELOG 记录。调用方可传
# --policy-version 校验钉住的版本（不匹配 → fail-closed exit 2）。
POLICY_VERSION = "gate-policy.v1"



def load_tools() -> tuple[dict, dict]:
    """Return (raw toolstack, merged tool map).

    v2.10.1 (F-42): the gate originally read `local_tools` only, so all 22
    `sdk_tools` — the SDK's own scripts, i.e. the actions an agent actually
    takes — were DENIED, including this file's own `--tool diff-risk` example.
    Both maps are now merged; `local_tools` wins on a key collision.
    """
    data = json.loads(TOOLSTACK.read_text(encoding="utf-8"))
    merged: dict = {}
    merged.update(data.get("sdk_tools", {}))
    merged.update(data.get("local_tools", {}))
    return data, merged


def find_tool(name: str, tools: dict) -> tuple[str | None, dict | None]:
    """Match by exact key, base name ('open-code-review (ocr)' -> open-code-review),
    stem ('bump-version.py' <-> 'bump-version'), or parenthesized alias ('ocr').
    Deterministic: exact > base > stem > alias."""
    if name in tools:
        return name, tools[name]
    for key, meta in tools.items():
        base = key.split(" (")[0].strip()
        if base == name:
            return key, meta
    # stem match: 'diff-risk' -> 'diff-risk.py' and vice versa
    for key, meta in tools.items():
        base = key.split(" (")[0].strip()
        if base.removesuffix(".py") == name.removesuffix(".py"):
            return key, meta
    for key, meta in tools.items():
        if "(" in key and key.rstrip(")").rsplit("(", 1)[-1].strip() == name:
            return key, meta
    return None, None


CI_STEPS = SCRIPT_DIR / "data" / "ci-steps.json"


def ci_prereqs(script_key: str) -> dict | None:
    """若该脚本是 ci-smoke 的某一步，回报其位置与 cheapest-first 前置步骤。"""
    if not CI_STEPS.exists():
        return None
    try:
        data = json.loads(CI_STEPS.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    steps = data.get("steps") or []
    for i, st in enumerate(steps):
        if st.get("script") == script_key:
            return {"is_step": True, "position": i, "tier": st.get("tier"),
                    "optional": bool(st.get("optional")),
                    "prerequisite_steps": [s.get("name") for s in steps[:i]]}
    return {"is_step": False}


def resolve(name: str, tools: dict) -> dict:
    """R-5 / ResourceOS §10 `resolve` 动词：纯规划、零副作用的依赖可用性预检。

    三态：READY（自身可用）/ DEGRADED（自身 degraded|unavailable 但 fallback 可用）
    / BLOCKED（自身不可用且无可用 fallback，或未登记）。
    """
    key, meta = find_tool(name, tools)
    rep: dict = {"schema": SCHEMA, "mode": "resolve", "tool": name, "time": now_iso(),
                 "policy_version": POLICY_VERSION, "toolstack_key": key}
    if key is None:
        rep.update({"decision": "BLOCKED", "health": None, "fallback": None,
                    "reasons": ["工具未登记在 toolstack.json —— 不可执行（先跑 "
                                "selfcheck-static 或 toolstack-pipeline 登记）"]})
        return rep

    health = meta.get("health") or "active"
    fb = meta.get("fallback")
    fb_key, fb_meta = (find_tool(fb, tools) if fb else (None, None))
    fb_health = (fb_meta or {}).get("health") or "active" if fb_key else None
    prereq = ci_prereqs(key)

    if health == "active":
        decision = "READY"
    elif fb_key and fb_health == "active":
        decision = "DEGRADED"
    else:
        decision = "BLOCKED"

    reasons: list[str] = []
    if decision == "READY":
        reasons.append(f"health={health}（last_checked={meta.get('last_checked') or 'never'}）")
    elif decision == "DEGRADED":
        reasons.append(f"health={health} —— 自身不可用，改走 fallback {fb_key}（health={fb_health}）")
    else:
        reasons.append(f"health={health} 且无可用 fallback"
                       + (f"（登记 fallback={fb}，但其 health={fb_health}）" if fb_key else "（未登记 fallback）"))
    if prereq and prereq.get("is_step"):
        reasons.append("ci-smoke 第 "
                       f"{prereq['position']} 步（tier={prereq.get('tier')}），前置："
                       + (", ".join(prereq["prerequisite_steps"]) or "无"))

    rep.update({"decision": decision, "health": health,
                "last_checked": meta.get("last_checked"),
                "capabilities": meta.get("capabilities") or [],
                "fallback": ({"tool": fb_key, "health": fb_health} if fb else None),
                "risk_tier": meta.get("risk_tier"),
                "ci_step": prereq, "reasons": reasons})
    return rep


def gate(name: str, args_json: str | None, user_approved: bool) -> dict:
    reasons: list[str] = []
    conditions: list[str] = []
    try:
        _, tools = load_tools()
    except Exception as e:  # fail-closed: 元数据读不了 = 门禁失效 = 拒绝
        return {"schema": SCHEMA, "time": now_iso(), "policy_version": POLICY_VERSION, "tool": name,
                "decision": "DENY", "reasons": [f"toolstack unreadable: {type(e).__name__}: {e}"],
                "risk_tier": None, "conditions": [], "human_approval": None, "args": None}

    key, meta = find_tool(name, tools)
    if meta is None:
        return {"schema": SCHEMA, "time": now_iso(), "policy_version": POLICY_VERSION, "tool": name,
                "decision": "DENY",
                "reasons": [f"tool {name!r} not in toolstack.json — probe first "
                            f"(probe-tools.py) or add it with risk_tier metadata"],
                "risk_tier": None, "conditions": [], "human_approval": None, "args": None}

    parsed_args = None
    if args_json is not None:
        try:
            parsed_args = json.loads(args_json)
        except json.JSONDecodeError as e:
            return {"schema": SCHEMA, "time": now_iso(), "policy_version": POLICY_VERSION, "tool": name, "toolstack_key": key,
                    "decision": "DENY", "reasons": [f"--args-json invalid: {e}"],
                    "risk_tier": meta.get("risk_tier"), "conditions": [],
                    "human_approval": None, "args": None}

    tier = int(meta.get("risk_tier", 3))
    human_approval = "recorded (--user-approved)" if user_approved else None

    if tier >= 4:
        if user_approved:
            reasons.append(f"risk_tier={tier} (irreversible/credentials) — human approval recorded")
            decision = "ALLOW"
        else:
            reasons.append(f"risk_tier={tier} (irreversible/credentials) — §10.9 tier-4 requires "
                           "explicit human approval (ask the user; pass --user-approved only after)")
            decision = "DENY"
    elif tier == 3:
        decision = "ALLOW"
        conditions.extend(["independent cross-check of the target and blast radius",
                           "rollback validated (§10.7) before execution"])
        reasons.append(f"risk_tier=3 (destructive) — allowed with mandatory conditions")
    else:
        decision = "ALLOW"
        reasons.append(f"risk_tier={tier} (safe/reversible)")

    if not meta.get("idempotent", False):
        conditions.append("tool is NOT idempotent — retries need an idempotency key "
                          "(task-state --idempotency-key, T-26) or explicit re-authorization")

    return {"schema": SCHEMA, "time": now_iso(), "policy_version": POLICY_VERSION, "tool": name, "toolstack_key": key,
            "decision": decision, "reasons": reasons, "risk_tier": tier,
            "conditions": conditions, "human_approval": human_approval,
            "metadata": {"idempotent": meta.get("idempotent", False),
                         "timeout_ms": meta.get("timeout_ms"),
                         "retryable": meta.get("retryable"),
                         "group": meta.get("group"),
                         "note": meta.get("note")},
            "args": parsed_args}


def main() -> int:
    ap = build_parser("Action Validator pre-execution gate (T-25)")
    ap.add_argument("--tool", required=True, help="tool name (toolstack.json key, base name, or alias)")
    ap.add_argument("--args-json", default=None, help="tool arguments as a JSON object (validated)")
    ap.add_argument("--user-approved", action="store_true",
                    help="tier-4 only: record explicit human approval (ask the user FIRST)")
    ap.add_argument("--policy-version", default=None,
                    help="caller-pinned gate policy version (cicd §15); mismatch → exit 2")
    ap.add_argument("--resolve", action="store_true",
                    help="resolve 模式（R-5）：依赖可用性预检，纯规划零副作用，输出 READY/DEGRADED/BLOCKED")
    ap.add_argument("--toolstack", default=None,
                    help="指定 toolstack.json（测试与夹具；默认 scripts/toolstack.json）")
    add_json_flag(ap, help="machine-readable JSON to stdout")
    args = ap.parse_args()

    if args.toolstack:
        global TOOLSTACK
        TOOLSTACK = Path(args.toolstack).resolve()

    if args.policy_version and args.policy_version != POLICY_VERSION:  # §15 策略版本钉
        print(f"[fatal] policy version mismatch: caller pinned {args.policy_version!r}, "
              f"gate enforces {POLICY_VERSION!r} — risk-tier decision table is policy, "
              f"bump the POLICY_VERSION constant (with CHANGELOG) if intended",
              file=sys.stderr)
        return EXIT_GATE

    if args.resolve:
        rep = resolve(args.tool, load_tools()[1])
        if args.json:
            emit_json(rep)
        else:
            print(f"== action-gate resolve: {rep['decision']}  {args.tool} "
                  f"(toolstack_key={rep.get('toolstack_key')}) ==")
            for r in rep.get("reasons", []):
                print(f"  - {r}")
        return EXIT_OK if rep["decision"] != "BLOCKED" else EXIT_GATE

    rep = gate(args.tool, args.args_json, args.user_approved)
    if args.json:
        emit_json(rep)
    else:
        print(f"== action-gate: {rep['decision']}  {args.tool} "
              f"(tier={rep.get('risk_tier')}, policy={rep.get('policy_version')}) ==")
        for r in rep.get("reasons", []):
            print(f"  - {r}")
        for c in rep.get("conditions", []):
            print(f"  [condition] {c}")
    return EXIT_OK if rep["decision"] == "ALLOW" else EXIT_GATE


if __name__ == "__main__":
    sys.exit(main())
