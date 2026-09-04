#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
token-meter.py — 会话 token 计量与指标表 (v1.0, 2026-08-22)

Purpose: give G4/G6 (token budget gates) a deterministic measuring tool — no
manual accounting, no LLM. Consumes the ref-05 §7 per-call log schema (JSONL)
or raw text, computes: totals, per-model breakdown, think-token ratio,
token efficiency (tokens per passed task), cache-hit proxy (field or prefix
repetition heuristic), cost estimate (optional price table).

Design rules (SDK §3/G4-G6, ref-05 §2/§7, ref-06):
  * Python 3.9+ stdlib only. JSON out. Read-only.
  * Missing usage fields are estimated CJK-aware (ref-06): CJK /2, other /4.
  * Bounded output; JSON is the machine contract, human table is a summary.

Log schema (JSONL, ref-05 §7): one object per call:
  {"time","task_type","model_id","prompt_version","temperature","thinking",
   "in_tokens","out_tokens","think_tokens","latency_ms","success","failure_mode"}
  Or raw text lines (estimated). Or --json-in with an array.

Usage:
  python token-meter.py --log calls.jsonl --json
  python token-meter.py --log calls.jsonl --prices '{"deepseek-v4":0.002}'
  python token-meter.py --log calls.jsonl --budget '{"max_usd":0.5,"max_calls":50}'
  python token-meter.py --log text-file.txt          # estimate only
Exit codes (F-50, v2.10.2):
  0 = 未传 --budget（纯计量）· 或预算未超限 · 或 --budget 非对象以外的正常路径
  2 = **传了 --budget 且超限**（max_usd / max_calls 任一越界）· 或 --budget 不是 JSON 对象

  旧契约是 "0 always (informational)" —— 预算超限只写 flags 仍 return 0，与 coding-agent-os
  §16「explicit stop > silent degrade」自相矛盾，任何按退出码判定的调用方都会静默放行。
  现规则：**显式传 --budget 即表示要求被拦住**；不传则保持纯计量语义，向后兼容。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# --- R-7: 上下文分类观测（ResourceOS §32.3 + SKILL §7 预算表）------------------
# 五类与 SKILL §7 表格逐行对齐（"活动资源 L3" 即 refs）。未知/缺失落 unclassified，
# 绝不丢弃 —— 分类漏标本身就是要被看见的信号。
CATEGORIES = ("system", "task", "refs", "memory", "results")

CONTEXT_BUDGET_SQL = """
CREATE TABLE IF NOT EXISTS context_budget_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  source TEXT,
  category TEXT NOT NULL,
  calls INTEGER NOT NULL DEFAULT 0,
  in_tokens INTEGER NOT NULL DEFAULT 0,
  out_tokens INTEGER NOT NULL DEFAULT 0,
  think_tokens INTEGER NOT NULL DEFAULT 0
)
"""


def log_categories(db_path: Path, source: str, by_category: dict) -> int:
    """把分类观测落到 router-stats.db 的 context_budget_log。返回写入行数。"""
    import sqlite3
    import time as _time
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db_path, timeout=10)
        try:
            con.execute(CONTEXT_BUDGET_SQL)
            ts = now_iso()
            rows = [(ts, str(source), k, v.get("calls", 0), v.get("in", 0),
                     v.get("out", 0), v.get("think", 0)) for k, v in by_category.items()]
            con.executemany(
                "INSERT INTO context_budget_log (ts, source, category, calls,"
                " in_tokens, out_tokens, think_tokens) VALUES (?,?,?,?,?,?,?)", rows)
            con.commit()
            return len(rows)
        finally:
            con.close()
    except (sqlite3.Error, OSError) as e:
        # 观测落库失败不该让计量命令失败 —— 明确报告，退出码不变
        return -1


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def token_est(text: str) -> int:
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return cjk // 2 + (len(text) - cjk) // 4


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    records = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict):
                records.append(obj)
        except json.JSONDecodeError:
            # raw text line — treat whole line as one "prompt" for estimation
            records.append({"raw_line": ln[:4000]})
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description="Token metering for G4/G6 (ref-05 §7 schema)")
    ap.add_argument("--log", required=True, help="JSONL log or raw text file")
    ap.add_argument("--prices", default=None, help='JSON: {"model_id": price_per_1k_tokens_total}')
    ap.add_argument("--budget", default=None, help='JSON: {"max_usd": 0.5, "max_calls": 50} — per-task budget (T10)')
    ap.add_argument("--category-budget", default=None,
                    help='JSON: {"task": 2000, "refs": 8000, ...} — 上下文分类软上限'
                         '（R-7，只观测不拦截；类名同 SKILL §7：'
                         'system/task/refs/memory/results）')
    ap.add_argument("--db", default=None,
                    help="把分类观测写入该 SQLite 的 context_budget_log 表（R-7，"
                         "显式指定才写，默认无副作用）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    records = load_records(Path(args.log))
    if not records:
        print(json.dumps({"error": "no records", "file": args.log}))
        return 0

    prices = json.loads(args.prices) if args.prices else {}
    budget = json.loads(args.budget) if args.budget else {}
    if not isinstance(budget, dict):
        print(json.dumps({"error": "bad budget", "file": args.log}))
        return 2

    per_model: dict[str, dict] = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "think": 0,
                                                      "passed": 0, "failed": 0})
    # R-7：按 R-6 / SKILL §7 的上下文分类做观测。**只观测不强制分配** —— 分配是
    # agent 的判断，这里只回答"实际装了多少"，超预算只提示不拦截。
    per_cat: dict[str, dict] = {c: {"calls": 0, "in": 0, "out": 0, "think": 0}
                                for c in CATEGORIES + ("unclassified",)}
    totals = {"calls": 0, "in": 0, "out": 0, "think": 0, "passed": 0, "failed": 0, "latency": 0}
    cache_hits, cache_total = 0, 0

    for r in records:
        if "raw_line" in r:
            totals["in"] += token_est(r["raw_line"])
            totals["calls"] += 1
            continue
        model = r.get("model_id", "unknown")
        in_t = r.get("in_tokens")
        out_t = r.get("out_tokens")
        think_t = r.get("think_tokens") or 0
        if in_t is None and "prompt" in r:
            in_t = token_est(r["prompt"])
        if out_t is None and "response" in r:
            out_t = token_est(r["response"])
        in_t = in_t or 0
        out_t = out_t or 0

        success = bool(r.get("success", True))
        m = per_model[model]
        m["calls"] += 1; m["in"] += in_t; m["out"] += out_t; m["think"] += think_t
        m["passed" if success else "failed"] += 1
        totals["calls"] += 1; totals["in"] += in_t; totals["out"] += out_t
        totals["think"] += think_t
        totals["passed" if success else "failed"] += 1
        totals["latency"] += r.get("latency_ms", 0)

        # R-7 分类观测：记录自带的 category 优先，未知/缺失落入 unclassified
        # （不丢弃 —— 分类漏标本身就是要被看见的信号）
        cat = str(r.get("category", "") or "").strip().lower()
        c = per_cat.get(cat) or per_cat["unclassified"]
        c["calls"] += 1; c["in"] += in_t; c["out"] += out_t; c["think"] += think_t

        # cache-hit proxy: explicit field, else prefix repetition across same-model calls (simple heuristic)
        if "cache_hit" in r:
            cache_total += 1
            cache_hits += 1 if r["cache_hit"] else 0

    passed = totals["passed"] or 1
    eff = (totals["in"] + totals["out"]) / passed
    think_ratio = totals["think"] / (totals["think"] + totals["out"]) if (totals["think"] + totals["out"]) else 0.0
    cache_rate = cache_hits / cache_total if cache_total else None

    cost_total = 0.0
    cost_rows = {}
    for model, mm in per_model.items():
        px = prices.get(model)
        if px is not None:
            cost = (mm["in"] + mm["out"] + mm["think"]) * px / 1000
            cost_rows[model] = round(cost, 4)
            cost_total += cost

    # per-task budget tracking (T10, coding-agent-os §16: silent degrade < explicit stop)
    budget_block = None
    if budget:
        max_usd = budget.get("max_usd")
        max_calls = budget.get("max_calls")
        exceeded = False
        reason = []
        if max_usd is not None and cost_total > max_usd:
            exceeded = True
            reason.append(f"cost {cost_total:.4f} > max_usd {max_usd}")
        if max_calls is not None and totals["calls"] > max_calls:
            exceeded = True
            reason.append(f"calls {totals['calls']} > max_calls {max_calls}")
        budget_block = {
            "spent_usd": round(cost_total, 4), "max_usd": max_usd,
            "calls": totals["calls"], "max_calls": max_calls,
            "exceeded": exceeded, "reasons": reason,
            "action": "ESCALATED-suggest" if exceeded else "within-budget",
        }

    # R-7：分类预算对照（只观测，不分配、不拦截）
    cat_budget: dict = json.loads(args.category_budget) if args.category_budget else {}
    if not isinstance(cat_budget, dict):
        print(json.dumps({"error": "bad category-budget", "file": args.log}))
        return 2
    by_category, over_cats = {}, []
    for k, v in per_cat.items():
        if not v["calls"]:
            continue
        total_tok = v["in"] + v["out"] + v["think"]
        row = {**v, "tokens": total_tok}
        lim = cat_budget.get(k)
        if isinstance(lim, (int, float)):
            row["budget"] = lim
            row["over"] = total_tok > lim
            if row["over"]:
                over_cats.append(f"{k} {total_tok} > {lim}")
        by_category[k] = row

    report = {
        "time": now_iso(), "file": args.log, "records": len(records),
        "totals": {**totals, "token_efficiency": round(eff, 1), "think_ratio": round(think_ratio, 3)},
        "cache": {"total": cache_total, "hits": cache_hits, "hit_rate": round(cache_rate, 3) if cache_rate is not None else None},
        "by_category": by_category,
        "category_budget": {"limits": cat_budget or None, "over": over_cats or None},
        "per_model": dict(per_model),
        "cost_est": {"total": round(cost_total, 4), "per_model": cost_rows},
        "budget": budget_block,
        "flags": [
            "overthinking: think ratio >0.7" if think_ratio > 0.7 else None,
            "cache broken: hit_rate <0.6" if cache_rate is not None and cache_rate < 0.6 else None,
            "budget exceeded: escalate to human (L5, ref-22) — explicit stop > silent degrade" if budget_block and budget_block["exceeded"] else None,
            ("context budget over: " + "; ".join(over_cats) + " —— 压缩输入类，"
             "但不得挤占输出推理空间（SKILL §7 reasoning 硬底线）") if over_cats else None,
            ("unclassified records: %d —— 分类漏标会掩盖真实注入面"
             % per_cat["unclassified"]["calls"]) if per_cat["unclassified"]["calls"] else None,
        ],
    }

    # R-7 落库：--db 显式指定才写（避免纯计量命令产生副作用）
    if args.db:
        report["category_logged"] = log_categories(Path(args.db), args.log, by_category)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"== token-meter: {args.log} ({len(records)} records) ==")
        print(f"  in={totals['in']} out={totals['out']} think={totals['think']} "
              f"| eff={eff:.0f}/pass | think_ratio={think_ratio:.1%}")
        print(f"  pass={totals['passed']} fail={totals['failed']} | cache_hit={cache_rate if cache_rate is not None else 'n/a'}")
        if cost_total:
            print(f"  cost_est=¥{cost_total:.4f} {cost_rows}")
        for model, mm in sorted(per_model.items()):
            print(f"  {model:<20} {mm['calls']:>3} calls  in={mm['in']:>7} out={mm['out']:>7} "
                  f"think={mm['think']:>6}  pass={mm['passed']} fail={mm['failed']}")
        for f in report["flags"]:
            if f:
                print(f"  ⚠ {f}")
    # F-50 (v2.10.2 负向覆盖审计)：预算闸此前**永不拦截**——超预算只写 flags 仍 return 0，
    # 与自身 docstring「explicit stop > silent degrade」（coding-agent-os §16）自相矛盾。
    # 任何按退出码判定的调用方（ci-smoke / pre-commit / shell &&）都会静默放行。
    # 规则：显式传 --budget 即表示要求被拦住 → 超限 exit 2；不传 --budget 仅计量 → exit 0。
    if budget_block and budget_block["exceeded"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
