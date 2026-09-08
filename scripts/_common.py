#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_common.py — SDK 脚本层共享库 v1（Epic C / F-58）

Why this exists (F-58): 每个闸脚本各自重复实现同一批东西 —— exit 码语义、
JSON 输出序列化、schema id 常量、argparse 构造。**同一件事有 N 份实现，改一处要改
N 处**，而且"2 到底是拒还是错"这种语义只能靠注释约定。本文件把真正共用且稳定的
部分收敛到一处；**各闸的判定逻辑仍留在各闸**（不搞大一统 —— 那正是过度工程）。

Invariants:
  * stdlib only（与 SDK 全部脚本同律）；目标 <150 行。
  * **不含 `sys.exit`**：库不做进程级决策，退出码由调用方返回。
    （也避免 selfcheck-static 的 blocking-coverage 把它当"闸"来要求拦截用例。）
  * 只收"稳定契约"：exit 码 / schema id / JSON 序列化 / 时间戳 / parser 构造。
    任何带业务语义的东西不进这里。

不是工具：本文件是库，没有 CLI、没有 exit path，已在 toolstack.json
`sdk_tools_exempt` 登记 —— 不参与 action-gate 门禁，也不算 sdk_tools 覆盖度。

Usage:
    from _common import EXIT_OK, EXIT_GATE, schema, now_iso, emit_json, build_parser
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

__all__ = [
    "EXIT_OK", "EXIT_ERROR", "EXIT_GATE",
    "SCHEMA_IDS", "schema",
    "now_iso", "dumps", "emit_json",
    "build_parser", "add_json_flag",
]

# --- exit-code 语义（不是数字，是契约）---------------------------------------
# 0 = 通过；1 = 用法/环境错误（不是闸门判定）；2 = 闸门拒绝。
# 三者混用会让"红灯到底是我的错还是闸在拦"变成玄学 —— 语义必须在代码里，不能只在注释里。
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_GATE = 2

# --- schema id 常量表（单点真相）---------------------------------------------
# 之前每个脚本各写一行 `SCHEMA = "xxx.v1"`，重命名的成本 = 改 N 处。
SCHEMA_IDS = {
    "diagnostic": "diagnostic.v1",        # diff-risk / router-stats 共用
    "task-state": "task-state.v1",
    "gate-policy": "gate-policy.v1",
    "action-gate": "action-gate.v1",
    "patch-gate": "patch-gate.v1",
    "version-check": "version-check.v1",
    "selfcheck-static": "selfcheck-static.v1",
    "ci-smoke": "ci-smoke.v1",
    "trace": "trace.v1",                  # R-10 trace-export --trace
    "ci-steps": "ci-steps.v1",            # R-5 步骤清单
    "doc-index": "doc-index.v1",          # 参考语料池索引（v2.10.13）
    "doc-index-check": "doc-index-check.v1",  # doc-pipeline check 输出
}


def schema(key: str) -> str:
    """按 key 取 schema id。未登记的 key 直接 KeyError —— 拼错即炸，不静默降级。"""
    return SCHEMA_IDS[key]


def now_iso() -> str:
    """本地时区 ISO 8601（秒精度）。所有脚本的时间戳必须是同一个函数。"""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def dumps(obj) -> str:
    """规范序列化：`ensure_ascii=False` + `indent=2`。

    中文必须原样输出（`ensure_ascii=True` 会把中文变成 \\uXXXX，人读不了），
    且所有脚本必须同构，否则下游解析与人工 diff 都要各写一套。
    """
    return json.dumps(obj, ensure_ascii=False, indent=2)


def emit_json(obj) -> None:
    """把对象按规范序列化打到 stdout。F-45：`--json` 模式下 stdout 必须纯 JSON。"""
    print(dumps(obj))


def build_parser(description: str, epilog: str | None = None,
                 prog: str | None = None) -> argparse.ArgumentParser:
    """argparse 母版。只接 description/epilog/prog —— 各脚本的 flag 自己加，
    这样 `--help` 的输出顺序与未迁移前**逐字节一致**（R-C2 等价性前提）。"""
    kwargs: dict = {"description": description}
    if epilog:
        kwargs["epilog"] = epilog
    if prog:
        kwargs["prog"] = prog
    return argparse.ArgumentParser(**kwargs)


def add_json_flag(parser: argparse.ArgumentParser,
                  help: str | None = None) -> argparse.ArgumentParser:
    """加 `--json`。help=None 时不带 help 文本（与原脚本写法一致，保 --help 字节等价）。"""
    kwargs: dict = {"action": "store_true"}
    if help:
        kwargs["help"] = help
    parser.add_argument("--json", **kwargs)
    return parser
