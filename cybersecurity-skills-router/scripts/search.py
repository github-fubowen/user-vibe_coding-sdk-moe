#!/usr/bin/env python3
"""Read-only search over the local Anthropic-Cybersecurity-Skills library.

stdlib only, no network, no writes. Keyword matches against the index.json
(name+description); subdomain filter scans SKILL.md frontmatter (all 817
files, ~1s). Prints ranked matches.

Usage:
    python search.py --keyword "ransomware" --top 10
    python search.py --subdomain digital-forensics --top 20
    python search.py --keyword "DPAPI" --json
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "cybersecurity-skills"
INDEX = SKILLS_DIR / "index.json"

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_SUBDOMAIN_RE = re.compile(r"^subdomain:\s*([\w-]+)\s*$", re.MULTILINE)


def load_index():
    if not INDEX.exists():
        sys.exit(f"[error] index not found: {INDEX}\n"
                 f"Run: git clone --depth 1 https://github.com/mukul975/"
                 f"Anthropic-Cybersecurity-Skills.git {SKILLS_DIR}")
    with open(INDEX, encoding="utf-8") as f:
        return json.load(f)


def subdomain_of(entry):
    """Read subdomain from the SKILL.md frontmatter of a skill dir."""
    d = SKILLS_DIR / entry.get("path", "")
    f = d / "SKILL.md"
    if not f.exists():
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            head = fh.read(4000)
        m = _FM_RE.search(head)
        if m:
            sm = _SUBDOMAIN_RE.search(m.group(1))
            if sm:
                return sm.group(1)
    except OSError:
        pass
    return None


def score(entry, keyword):
    """Simple relevance: keyword hits in name > description."""
    kw = keyword.lower()
    name = entry.get("name", "").lower()
    desc = entry.get("description", "").lower()
    s = 0
    if kw in name:
        s += 10
    if kw in desc:
        s += 5
    for tok in kw.split():
        if tok in name:
            s += 3
        if tok in desc:
            s += 2
    return s


def main():
    ap = argparse.ArgumentParser(description="Search local cybersecurity skill library")
    ap.add_argument("--keyword", help="keyword in name or description")
    ap.add_argument("--subdomain", "--domain", dest="subdomain",
                    help="filter by subdomain (e.g. digital-forensics, cloud-security)")
    ap.add_argument("--top", type=int, default=10, help="max results")
    ap.add_argument("--json", action="store_true", help="output as JSON")
    args = ap.parse_args()

    if not args.keyword and not args.subdomain:
        ap.print_help()
        sys.exit(1)

    data = load_index()
    hits = []
    for entry in data.get("skills", []):
        if args.subdomain and subdomain_of(entry) != args.subdomain:
            continue
        if args.keyword:
            s = score(entry, args.keyword)
            if s == 0:
                continue
            hits.append((s, entry))
        else:
            hits.append((0, entry))

    hits.sort(key=lambda x: -x[0])
    hits = hits[: args.top]

    if args.json:
        print(json.dumps([e for _, e in hits], ensure_ascii=False, indent=2))
        return

    for s, e in hits:
        desc = (e.get("description") or "").replace("\n", " ")[:140]
        print(f"[{s:>3}] {e['name']}  ({subdomain_of(e) or e.get('domain', '')})")
        print(f"      {desc}")
        print(f"      path: {e.get('path', '')}")
    print(f"\n{len(hits)} / {data.get('total_skills', '?')} skills matched")


if __name__ == "__main__":
    main()
