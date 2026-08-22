#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case-search.py — Debug 案例库检索（ref-18 §5 轨迹复用） (v1.0, 2026-08-22)

Purpose: before starting a full Debug diagnosis (ref-18 hypothesis loop), grep the
incident case library for a similar past case (symptom -> trajectory -> fix ->
verification). If a case matches, jump straight to verifying the recorded fix —
saves a full diagnosis cycle at ZERO LLM cost.

Design rules (SDK §3/G-gates, ref-18 §5):
  * Case dir: --dir (default .workbuddy/debug-cases/ under --cwd or cwd).
  * Case format: Markdown with `## [date] symptom` heading (ref-18 §5 template).
  * Search: case-insensitive substring over the whole file; rank by hit count.
  * Python 3.9+ stdlib only. JSON out. Read-only.

Usage:
  python case-search.py --q "tower attack gold"
  python case-search.py --q "ReferenceError MAPH" --dir /path/to/cases --json
  python case-search.py --q "shim __spec__" --top 3
Exit codes: 0 always (informational; results in output/JSON).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def collect_cases(root: Path) -> list[tuple[Path, str]]:
    """Return [(path, text)] for all *.md case files under root (non-recursive + one level)."""
    if not root.exists():
        return []
    files = sorted(root.glob("*.md")) + sorted(root.glob("*/**/*.md"))
    seen, out = set(), []
    for p in files:
        if p in seen:
            continue
        seen.add(p)
        try:
            out.append((p, p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return out


def rank(text: str, q: str) -> tuple[int, str]:
    """Hit count + matched line excerpt."""
    lines = text.splitlines()
    hits = [ln.strip() for ln in lines if q.lower() in ln.lower()]
    excerpt = ""
    if hits:
        # prefer heading line if present, else first hit
        heading = next((h for h in hits if h.startswith("#") or h.startswith("##")), hits[0])
        excerpt = heading[:120]
    return len(hits), excerpt


def main() -> int:
    ap = argparse.ArgumentParser(description="Debug case-library search (zero-LLM, ref-18 §5)")
    ap.add_argument("--q", required=True, help="search keyword(s) (space-separated = AND within file)")
    ap.add_argument("--dir", default=None, help="case dir (default .workbuddy/debug-cases/)")
    ap.add_argument("--cwd", default=".", help="base dir to resolve default case dir")
    ap.add_argument("--top", type=int, default=5, help="max results")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.dir) if args.dir else Path(args.cwd) / ".workbuddy" / "debug-cases"
    queries = [q for q in args.q.split() if q]
    cases = collect_cases(root)

    results = []
    for path, text in cases:
        hit_counts = [rank(text, q)[0] for q in queries]
        total = sum(hit_counts)
        if total == 0:
            continue
        _, excerpt = rank(text, queries[0])
        results.append({
            "path": str(path), "hits": total, "matched_queries": sum(1 for h in hit_counts if h > 0),
            "excerpt": excerpt,
        })

    results.sort(key=lambda r: (-r["hits"], -r["matched_queries"]))
    results = results[: args.top]

    if args.json:
        print(json.dumps({
            "query": queries, "case_dir": str(root), "total_cases": len(cases),
            "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"== Case search: {args.q}  (dir: {root}, {len(cases)} cases) ==")
        if not results:
            print("  no match — start a fresh diagnosis (ref-18), then log the case")
        for r in results:
            print(f"  [{r['hits']} hits] {r['path']}")
            if r["excerpt"]:
                print(f"             {r['excerpt'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
