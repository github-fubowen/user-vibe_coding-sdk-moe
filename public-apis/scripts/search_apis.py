#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search_apis.py — offline search over the vendored public-apis README data.

Source data: https://github.com/public-apis/public-apis (MIT) — data/README.md
This script is READ-ONLY: parses the local markdown, never touches the network,
never writes files, stdlib only (Python 3.8+).

Usage examples:
  python search_apis.py --category Finance
  python search_apis.py --keyword weather --https yes --cors unknown
  python search_apis.py --auth No --limit 20
  python search_apis.py --stats
  python search_apis.py --category Books --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "README.md"

HEADER_MARKERS = ("API |", "API|")
SEPARATOR_CHARS = set(":-| ")


def parse_apis(readme_path: Path):
    """Parse the README into a list of API dicts.

    Structure: '### Category' headers followed by tables of the form
    '| [Name](url) | description | auth | HTTPS | CORS |'.
    Only 5-column tables (Auth/HTTPS/CORS) are collected.
    """
    apis = []
    category = None
    in_table = False

    for raw in readme_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue

        m = re.match(r"^### (.+)$", line)
        if m:
            category = m.group(1).strip()
            in_table = False
            continue

        if line.startswith("|"):
            if in_table and set(line) <= SEPARATOR_CHARS:
                continue  # separator row |:---|:---|...|
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not in_table:
                # header row (may lack leading/trailing pipes)
                if cells and cells[0] in HEADER_MARKERS and len(cells) >= 5:
                    if {"Auth", "HTTPS", "CORS"}.issubset(cells[:5]):
                        in_table = True
                continue
            if len(cells) < 5:
                continue
            name_cell, desc, auth, https, cors = cells[:5]
            mname = re.match(r"\[([^\]]+)\]\(([^)]+)\)", name_cell)
            if mname:
                name, url = mname.group(1), mname.group(2)
            else:
                name, url = name_cell, ""
            apis.append({
                "category": category,
                "name": name,
                "url": url,
                "description": desc,
                "auth": auth,
                "https": https,
                "cors": cors,
            })
            continue

        # non-pipe header row such as 'API | Description | Auth | HTTPS | CORS'
        if line.startswith(HEADER_MARKERS):
            cells = [c.strip() for c in line.split("|")]
            in_table = {"Auth", "HTTPS", "CORS"}.issubset(cells)

    return apis


def matches(api, args) -> bool:
    if args.category and args.category.lower() not in api["category"].lower():
        return False
    if args.keyword:
        hay = f"{api['name']} {api['description']}".lower()
        if args.keyword.lower() not in hay:
            return False
    if args.auth is not None:
        if args.auth.lower() != api["auth"].lower():
            return False
    if args.https is not None:
        if args.https.lower() != api["https"].lower():
            return False
    if args.cors is not None:
        if args.cors.lower() != api["cors"].lower():
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Offline search of the public-apis list (vendored README.md).")
    ap.add_argument("-c", "--category", help="category substring filter (case-insensitive)")
    ap.add_argument("-k", "--keyword", help="keyword filter on name+description")
    ap.add_argument("--auth", help="auth filter: No / apiKey / OAuth / ... (exact, case-insensitive)")
    ap.add_argument("--https", help="HTTPS filter: yes / no")
    ap.add_argument("--cors", help="CORS filter: yes / no / unknown")
    ap.add_argument("-l", "--limit", type=int, default=0, help="max rows printed (0 = all)")
    ap.add_argument("--json", action="store_true", help="output raw JSON")
    ap.add_argument("--csv", action="store_true", help="output CSV")
    ap.add_argument("--stats", action="store_true", help="print per-category counts and exit")
    ap.add_argument("--data", default=str(DATA_FILE), help="path to README.md (override)")
    args = ap.parse_args()

    if not Path(args.data).is_file():
        print(f"error: data file not found: {args.data}", file=sys.stderr)
        return 1

    apis = parse_apis(Path(args.data))

    if args.stats:
        counts = {}
        for a in apis:
            counts[a["category"]] = counts.get(a["category"], 0) + 1
        print(f"total APIs: {len(apis)}  |  categories: {len(counts)}")
        for cat, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"{n:5d}  {cat}")
        return 0

    results = [a for a in apis if matches(a, args)]
    total = len(results)
    if args.limit:
        results = results[: args.limit]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.csv:
        import csv as _csv
        import io

        buf = io.StringIO()
        w = _csv.DictWriter(buf, fieldnames=["category", "name", "url",
                                             "description", "auth", "https", "cors"])
        w.writeheader()
        w.writerows(results)
        print(buf.getvalue().strip())
    else:
        if results:
            w_name = max(len(r["name"]) for r in results)
            w_cat = max(len(r["category"]) for r in results)
            for r in results:
                desc = r["description"]
                if len(desc) > 64:
                    desc = desc[:61] + "..."
                print(f"[{r['category']:<{w_cat}}] {r['name']:<{w_name}}  "
                      f"{r['auth']:<8} https={r['https']:<3} cors={r['cors']:<7} "
                      f"{r['url']}  {desc}")
        print(f"\n{total} match(es)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
