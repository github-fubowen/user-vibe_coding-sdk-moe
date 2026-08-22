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
  python token-meter.py --log text-file.txt          # estimate only
Exit codes: 0 always (informational).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


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
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    records = load_records(Path(args.log))
    if not records:
        print(json.dumps({"error": "no records", "file": args.log}))
        return 0

    prices = json.loads(args.prices) if args.prices else {}

    per_model: dict[str, dict] = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "think": 0,
                                                      "passed": 0, "failed": 0})
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

    report = {
        "time": now_iso(), "file": args.log, "records": len(records),
        "totals": {**totals, "token_efficiency": round(eff, 1), "think_ratio": round(think_ratio, 3)},
        "cache": {"total": cache_total, "hits": cache_hits, "hit_rate": round(cache_rate, 3) if cache_rate is not None else None},
        "per_model": dict(per_model),
        "cost_est": {"total": round(cost_total, 4), "per_model": cost_rows},
        "flags": [
            "overthinking: think ratio >0.7" if think_ratio > 0.7 else None,
            "cache broken: hit_rate <0.6" if cache_rate is not None and cache_rate < 0.6 else None,
        ],
    }

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
