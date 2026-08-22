#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
error-sig.py — 本地错误签名库 add/match (v1.0, 2026-08-22)

Purpose: implement ref-18 "确定性先行" 步骤 2 (日志/错误签名匹配) as a persistent,
zero-LLM lookup. Debug sessions add signatures once; future sessions match error
text against the store and jump straight to the known fix — no LLM inference.

Design rules (SDK §3/G-gates, ref-18 §2):
  * Store: scripts/data/error-signatures.json (default) or --store.
  * Python 3.9+ stdlib only. JSON out. Matching is substring — deterministic.
  * 'add' writes the store (tier-2 controlled modification, reversible — safe);
    never pushes. 'match' is read-only.

Schema:
  {"signatures": [
     {"id":"py-spec-error","patterns":["AttributeError: __spec__","_apipkg"],
      "label":"沙箱 PYTHONPATH shim 干扰", "fix":"用 stdlib 脚本或隔离 env；非脚本缺陷",
      "tags":["env","python"]}
  ]}

Usage:
  python error-sig.py match --text "<error output>" --json
  python error-sig.py match --text "$(cat error.log)" --store my-sigs.json
  python error-sig.py add --pattern "IndexError: list index" --label "..." --fix "..." --tags env,python
  python error-sig.py list --json
Exit codes: match: 0 = ok (matches found or none; result in JSON) / 2 = store missing.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STORE = SCRIPT_DIR / "data" / "error-signatures.json"


def load_store(path: Path) -> dict:
    if not path.exists():
        return {"signatures": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_store(path: Path, store: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Local error-signature store (zero-LLM lookup)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("match", help="match error text against signatures")
    m.add_argument("--text", required=True, help="error output text (or --file)")
    m.add_argument("--file", default=None, help="read error text from file")
    m.add_argument("--store", default=str(DEFAULT_STORE))
    m.add_argument("--json", action="store_true")

    a = sub.add_parser("add", help="add a signature")
    a.add_argument("--pattern", required=True, help="substring pattern to match (repeatable: comma-separated)")
    a.add_argument("--label", required=True)
    a.add_argument("--fix", default="", help="known fix suggestion")
    a.add_argument("--tags", default="", help="comma-separated tags")
    a.add_argument("--store", default=str(DEFAULT_STORE))

    l = sub.add_parser("list", help="list all signatures")
    l.add_argument("--store", default=str(DEFAULT_STORE))
    l.add_argument("--json", action="store_true")

    args = ap.parse_args()

    if args.cmd == "match":
        store_path = Path(args.store)
        if not store_path.exists():
            print(json.dumps({"error": f"store not found: {store_path} (run add first)"}))
            return 2
        text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
        store = load_store(store_path)
        hits = []
        for sig in store.get("signatures", []):
            matched = [p for p in sig["patterns"] if p in text]
            if matched:
                hits.append({"id": sig["id"], "label": sig["label"], "fix": sig.get("fix", ""),
                             "matched_patterns": matched, "tags": sig.get("tags", [])})
        if args.json:
            print(json.dumps({"hits": hits, "count": len(hits)}, ensure_ascii=False, indent=2))
        else:
            if not hits:
                print("No signature matched — proceed to hypothesis loop (ref-18 §3).")
            for h in hits:
                print(f"  HIT {h['id']}: {h['label']}")
                if h["fix"]:
                    print(f"       fix: {h['fix']}")
        return 0

    if args.cmd == "add":
        store_path = Path(args.store)
        store = load_store(store_path)
        sig = {
            "id": f"sig-{uuid.uuid4().hex[:8]}",
            "patterns": [p.strip() for p in args.pattern.split(",") if p.strip()],
            "label": args.label,
            "fix": args.fix,
            "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        }
        store.setdefault("signatures", []).append(sig)
        save_store(store_path, store)
        print(json.dumps({"added": sig, "store": str(store_path)}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "list":
        store_path = Path(args.store)
        if not store_path.exists():
            print(json.dumps({"error": f"store not found: {store_path}"}))
            return 2
        store = load_store(store_path)
        sigs = store.get("signatures", [])
        if args.json:
            print(json.dumps({"count": len(sigs), "signatures": sigs}, ensure_ascii=False, indent=2))
        else:
            for s in sigs:
                print(f"  {s['id']:<14} {s['label']}  (tags: {', '.join(s.get('tags', []))})")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
