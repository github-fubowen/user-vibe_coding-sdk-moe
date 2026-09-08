#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case-evolve.py — 失败 → 回归用例自演化（A-13，AOS §27）

Why: 真实失败（F-xx 缺陷 / 生产事故）目前靠人工写进 CHANGELOG，之后能不能变成
回归用例全看记不记得。AOS §27 的做法是流水线化：失败 → 分类 → 泛化 → 合成任务
→ 暂存池 → 晋升常设套件。SDK 规模下**不做 LLM 合成新题**（那是 §40.1-9 自述的
质量陷阱），只做结构化登记 + 三道闸：

  1. 近重复检测：标题+标签的词集 Jaccard ≥ 0.92 视为重复 → 拒绝（§27.2）
  2. 溯源强制：必须带 provenance（来源缺陷号 / 事故 / 报告路径），可审计"这题为什么存在"
  3. 暂存 + dwell：新用例进 staging，默认 7 天后才可晋升；且需 ≥3 次稳定运行
     （mark-stable 累加），防止"刚写就晋升"把噪声固化成门禁（§40.1-9）

Usage:
  python scripts/case-evolve.py add --id F-70 --title "..." --tags gate,ci --provenance "评审报告-....md"
  python scripts/case-evolve.py list [--json]
  python scripts/case-evolve.py mark-stable --id F-70
  python scripts/case-evolve.py promote --id F-70          # dwell 未满 / 稳定次数不足 → exit 2
Store: scripts/data/evolved-cases.json（可用 --store 覆盖）
Exit: 0 = ok / 2 = 重复、校验失败、dwell 未满、稳定次数不足
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STORE = SCRIPT_DIR / "data" / "evolved-cases.json"
DWELL_DAYS = 7
STABLE_RUNS_REQUIRED = 3
NEAR_DUP_THRESHOLD = 0.92
_TOKEN_RE = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]{2}")


def load(path: Path) -> dict:
    if not path.exists():
        return {"schema": "evolved-cases.v1", "cases": []}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        d.setdefault("cases", [])
        return d
    except (ValueError, OSError):
        return {"schema": "evolved-cases.v1", "cases": []}


def save(path: Path, d: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser(description="failure → regression case evolution (AOS §27)")
    ap.add_argument("cmd", choices=("add", "list", "mark-stable", "promote"))
    ap.add_argument("--store", default=str(DEFAULT_STORE))
    ap.add_argument("--id", default=None, help="用例 id（通常用缺陷号，如 F-70）")
    ap.add_argument("--title", default=None)
    ap.add_argument("--tags", default="", help="逗号分隔")
    ap.add_argument("--provenance", default=None, help="来源（缺陷号/事故/报告路径）")
    ap.add_argument("--dwell-days", type=int, default=DWELL_DAYS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    store = Path(args.store)
    data = load(store)

    if args.cmd == "list":
        rows = []
        for c in data["cases"]:
            created = datetime.fromisoformat(c["created_at"])
            mature = created + timedelta(days=c.get("dwell_days", DWELL_DAYS))
            rows.append({"id": c["id"], "status": c["status"], "title": c["title"],
                         "stable_runs": c.get("stable_runs", 0),
                         "created_at": c["created_at"],
                         "promote_after": mature.isoformat(timespec="seconds"),
                         "dwell_remaining_s": max(0, int((mature - datetime.now(timezone.utc).astimezone()).total_seconds())),
                         "provenance": c.get("provenance")})
        if args.json:
            print(json.dumps({"schema": "evolved-cases.v1", "cases": rows}, ensure_ascii=False, indent=2))
        else:
            print(f"== evolved cases · {len(rows)} ==")
            for r in rows:
                print(f"  [{r['status']:<8}] {r['id']:<10} stable={r['stable_runs']} "
                      f"dwell_left={r['dwell_remaining_s'] // 86400}d  {r['title'][:40]}")
        return 0

    if not args.id:
        print("[fatal] --id required", file=sys.stderr)
        return 2
    entry = next((c for c in data["cases"] if c["id"] == args.id), None)

    if args.cmd == "add":
        if entry:
            print(f"[fatal] case already exists: {args.id}", file=sys.stderr)
            return 2
        if not args.title or not args.provenance:
            print("[fatal] --title 与 --provenance 必填（溯源不可省，§27.2）", file=sys.stderr)
            return 2
        toks = tokens(f"{args.title} {args.tags}")
        for c in data["cases"]:
            if jaccard(toks, tokens(f"{c['title']} {' '.join(c.get('tags') or [])}")) >= NEAR_DUP_THRESHOLD:
                print(f"[fatal] near-duplicate of {c['id']} "
                      f"(Jaccard ≥ {NEAR_DUP_THRESHOLD}) — 合并而非重复登记", file=sys.stderr)
                return 2
        created = datetime.now(timezone.utc).astimezone()
        entry = {"id": args.id, "title": args.title,
                 "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
                 "provenance": args.provenance, "status": "staging",
                 "created_at": created.isoformat(timespec="seconds"),
                 "dwell_days": args.dwell_days, "stable_runs": 0}
        data["cases"].append(entry)
        save(store, data)
        print(f"added {args.id} → staging（dwell {args.dwell_days}d，需 {STABLE_RUNS_REQUIRED} 次稳定运行后可晋升）")
        return 0

    if entry is None:
        print(f"[fatal] case not found: {args.id}", file=sys.stderr)
        return 2

    if args.cmd == "mark-stable":
        entry["stable_runs"] = int(entry.get("stable_runs", 0)) + 1
        save(store, data)
        print(f"{args.id}: stable_runs={entry['stable_runs']}/{STABLE_RUNS_REQUIRED}")
        return 0

    # promote
    created = datetime.fromisoformat(entry["created_at"])
    mature = created + timedelta(days=entry.get("dwell_days", DWELL_DAYS))
    now = datetime.now(timezone.utc).astimezone()
    if now < mature:
        left = mature - now
        print(f"[fail] {args.id}: dwell 未满（还需 {left.days}d{left.seconds // 3600}h）—— "
              f"新题立刻进门禁 = 把噪声固化（§40.1-9）", file=sys.stderr)
        return 2
    if int(entry.get("stable_runs", 0)) < STABLE_RUNS_REQUIRED:
        print(f"[fail] {args.id}: 稳定运行 {entry.get('stable_runs', 0)}/{STABLE_RUNS_REQUIRED} 次",
              file=sys.stderr)
        return 2
    entry["status"] = "promoted"
    entry["promoted_at"] = now_iso()
    save(store, data)
    print(f"promoted {args.id} → permanent suite（provenance: {entry.get('provenance')}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
