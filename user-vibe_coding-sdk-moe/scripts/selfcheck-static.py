#!/usr/bin/env python3
"""SDK static structure self-check (SELF-CHECK-S1).

Checks:
  1. frontmatter keys + name
  2. version string consistency (delegates to version-check.py contract)
  3. references/ 01-24 existence + SKILL section 9 table coverage
  4. scripts referenced in docs exist / scripts orphan detection
  5. toolstack.json entry -> file existence
  6. ALIGNMENT.md / ENGINEERING.md cross links
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ["SKILL.md", "README.md", "ENGINEERING.md", "ALIGNMENT.md", "CHANGELOG.md"]

# `.py` names that appear as `scripts/<name>.py` in docs but are NOT SDK-owned:
# illustrative placeholders in command examples, or scripts belonging to an
# external skill referenced by pointer (ref-10 ARS-Codex, ref-14 cybersecurity).
EXTERNAL_PY = {
    "a.py",            # ref-22 diff-risk example placeholder
    "b.py",            # ref-22 diff-risk example placeholder
    "search.py",       # ref-14 cybersecurity-skills-router (external skill)
    "install-skill-from-github.py",  # ref-10 ARS-Codex install snippet
    "ars_codex_quality_gates.py",    # ref-10 ARS-Codex quality gate
}

# F-43 guard: v2.8.2~v2.10.0 added 5 scripts that nobody registered in
# toolstack.json, and nothing flagged it — `sdk_tools` has no automation
# (toolstack-pipeline covered only refs/provider_health until v2.10.2).
# Every scripts/*.py must therefore be registered, unless it is listed in
# toolstack.json `sdk_tools_exempt` (single source of truth, shared with
# toolstack-pipeline.py so the two can never disagree). Empty today.
DEFAULT_EXEMPT: set[str] = set()
PYRE = re.compile(r"(?<![A-Za-z0-9_\-])([A-Za-z0-9_\-]+\.py)(?![A-Za-z0-9_\-])")
# A script "can block" if it has any non-zero exit path (F-50 audit input).
HAS_EXIT_PATH_RE = re.compile(r"return [12]\b|sys\.exit\([12]\)|exit[= ]2\b")
REFRE = re.compile(r"^\|\s*(\d{2})\s*\|\s*`([^`]+)`\s*\|", re.M)
SCRIPTRE = re.compile(r"scripts/([A-Za-z0-9_\-]+\.py)")

problems: list[str] = []
notes: list[str] = []


def skill_text() -> str:
    return (ROOT / "SKILL.md").read_text(encoding="utf-8")


def check_frontmatter() -> dict:
    txt = skill_text()
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", txt, re.S)
    if not m:
        problems.append("SKILL.md frontmatter missing/broken")
        return {}
    fm = m.group(1)
    keys = [ln.split(":", 1)[0] for ln in fm.splitlines() if re.match(r"^[a-z_]+:", ln)]
    name = ""
    for ln in fm.splitlines():
        if ln.startswith("name:"):
            name = ln.split(":", 1)[1].strip()
    if "name" not in keys or "description" not in keys:
        problems.append(f"frontmatter missing key: {keys}")
    if name != "user-vibe_coding-sdk-moe":
        problems.append(f"frontmatter name mismatch: {name!r}")
    return {"keys": keys, "name": name}


def check_references() -> dict:
    refs_dir = ROOT / "references"
    have = {p.name.split("-", 1)[0]: p for p in refs_dir.glob("*.md")}
    txt = skill_text()
    table = {num: path for num, path in REFRE.findall(txt)}
    missing, external = [], []
    for num, path in sorted(table.items()):
        if path.startswith("$") or path.startswith("../"):
            external.append((num, path))
            target = ROOT / path if not path.startswith("$") else None
            if target is not None and not target.exists():
                problems.append(f"ref-{num} external target missing: {path}")
            continue
        p = ROOT / path.strip("`")
        if not p.exists():
            missing.append((num, path))
    files_without_entry = sorted(set(have) - set(table))
    if missing:
        problems.append(f"references listed in SKILL but missing on disk: {missing}")
    if files_without_entry:
        notes.append(f"reference files not listed in SKILL section 9: {files_without_entry}")
    return {
        "table_entries": len(table),
        "external": external,
        "on_disk": sorted(have),
        "unlisted": files_without_entry,
    }


def check_scripts(registered: set[str] | None = None,
                  exempt: set[str] | None = None) -> dict:
    """Only flag *SDK-owned* script references.

    Docs contain plenty of illustrative names (a.py, test_x.py, verify.py...) that
    are NOT SDK scripts, so we only consider names written as `scripts/<name>.py`
    or registered in toolstack.json `sdk_tools`.
    """
    existing = {p.name for p in (ROOT / "scripts").glob("*.py")}
    explicit: set[str] = set()
    for doc in DOCS + [f"references/{p.name}" for p in (ROOT / "references").glob("*.md")]:
        p = ROOT / doc
        if p.exists():
            explicit |= set(SCRIPTRE.findall(p.read_text(encoding="utf-8")))
    registered = set(registered or ())
    tracked = (explicit | registered) - EXTERNAL_PY
    dangling = sorted(tracked - existing)

    allref: set[str] = set()
    for doc in DOCS:
        p = ROOT / doc
        if p.exists():
            allref |= set(PYRE.findall(p.read_text(encoding="utf-8")))
    for r in (ROOT / "references").glob("*.md"):
        allref |= set(PYRE.findall(r.read_text(encoding="utf-8")))
    orphan = sorted(existing - allref)
    # F-43 guard (v2.10.2): the drift that actually happened — scripts that exist
    # on disk but were never registered, so action-gate cannot gate them.
    unregistered = sorted(existing - registered - set(exempt or DEFAULT_EXEMPT))
    if dangling:
        problems.append(f"SDK script referenced/registered but missing: {dangling}")
    if unregistered:
        problems.append(
            f"scripts exist but are NOT in toolstack.json sdk_tools "
            f"(action-gate cannot gate them): {unregistered}")
    if orphan:
        notes.append(f"scripts never mentioned in docs: {orphan}")
    return {
        "count": len(existing),
        "tracked": len(tracked),
        "registered": len(registered),
        "dangling": dangling,
        "unregistered": unregistered,
        "orphan": orphan,
    }


def check_toolstack() -> dict:
    p = ROOT / "scripts" / "toolstack.json"
    if not p.exists():
        problems.append("scripts/toolstack.json missing")
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    sdk_tools: dict = data.get("sdk_tools", {})
    local_tools: dict = data.get("local_tools", {})
    refs: dict = data.get("refs", {})

    broken_scripts, no_risk = [], []
    for name, meta in sdk_tools.items():
        if not (ROOT / "scripts" / name).exists():
            broken_scripts.append(name)
        if "risk_tier" not in meta:
            no_risk.append(name)
    if broken_scripts:
        problems.append(f"toolstack sdk_tools missing on disk: {broken_scripts}")
    if no_risk:
        problems.append(f"toolstack sdk_tools without risk_tier: {no_risk}")

    # toolstack `refs` keys are "<NN>-<repo-slug>", which do NOT match the
    # reference filename "<NN>-<topic>.md" 1:1 (e.g. 10-ars-codex ->
    # 10-academic-research-skills.md; 12-public-apis is external). Resolve
    # through the SKILL section-9 table instead of filename equality.
    table = {num: path for num, path in REFRE.findall(skill_text())}
    broken_refs, external_refs = [], []
    for key in refs:
        num = key.split("-", 1)[0]
        path = table.get(num)
        if path is None:
            broken_refs.append(key)
            continue
        if path.startswith("../") or path.startswith("$"):
            external_refs.append(key)
            if path.startswith("../") and not (ROOT / path).exists():
                broken_refs.append(f"{key} (external target missing)")
            continue
        if not (ROOT / path).exists():
            broken_refs.append(f"{key} -> {path}")
    if broken_refs:
        problems.append(f"toolstack refs unresolvable: {broken_refs}")

    no_risk_local = [k for k, v in local_tools.items() if "risk_tier" not in v]
    if no_risk_local:
        notes.append(f"toolstack local_tools without risk_tier: {no_risk_local}")
    if external_refs:
        notes.append(f"toolstack refs resolved to external skills: {external_refs}")

    return {
        "schema": data.get("schema"),
        "last_check": data.get("last_check"),
        "sdk_tools": len(sdk_tools),
        "local_tools": len(local_tools),
        "refs": len(refs),
        "broken_scripts": broken_scripts,
        "broken_refs": broken_refs,
    }


def _split_top_level(s: str) -> list[str]:
    """Split on commas that are not nested in brackets/quotes (arg lists may span lines)."""
    out: list[str] = []
    depth, cur, quote, i = 0, [], None, 0
    while i < len(s):
        c = s[i]
        if quote:
            cur.append(c)
            if c == "\\":
                cur.append(s[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            cur.append(c)
        elif c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return [x.strip() for x in out]


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    return s


def collect_blocking_cases(suite_src: str) -> dict[str, list[str]]:
    """Extract {script: [expected-exit, ...]} from robustness-suite.py.

    Two registration styles exist: the C(...) helper and raw dict literals
    (used for cases that need a custom command, e.g. the isolated-copy probe).
    Both must be parsed or real coverage is miscounted as a gap.
    """
    found: dict[str, list[str]] = {}

    def add(script: str, expect: str) -> None:
        found.setdefault(script, []).append(expect.strip())

    # style 1: C("name", "script.py", [args], <expect>, ...)
    for m in re.finditer(r"\bC\(", suite_src):
        i = m.end() - 1
        depth, j = 0, i
        while j < len(suite_src):
            if suite_src[j] == "(":
                depth += 1
            elif suite_src[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        args = _split_top_level(suite_src[i + 1:j])
        if len(args) >= 4:
            add(_unquote(args[1]), args[3])

    # style 2: raw dict — "script": "x.py" ... "expect": N
    for m in re.finditer(r'"script":\s*"([^"]+)"(.*?)"expect":\s*([0-9]+)', suite_src, re.S):
        add(m.group(1), m.group(3))
    return found


def check_blocking_coverage() -> dict:
    """v2.10.3 (F-50): a gate that is never proven to block is not a gate.

    F-42 was action-gate denying everything while 173/173 cases were green;
    F-50 was token-meter never returning non-zero despite a documented budget
    gate. Both share one root cause: **the suite only asserted the success
    path**. So: any script that can exit non-zero must have at least one case
    asserting a non-zero exit.
    """
    suite = ROOT / "scripts" / "robustness-suite.py"
    if not suite.exists():
        notes.append("blocking-coverage check skipped: robustness-suite.py not found")
        return {"checked": 0, "gaps": []}
    cases = collect_blocking_cases(suite.read_text(encoding="utf-8"))
    gaps, gated = [], []
    for p in sorted((ROOT / "scripts").glob("*.py")):
        if p.name == "robustness-suite.py":
            continue
        if not HAS_EXIT_PATH_RE.search(p.read_text(encoding="utf-8")):
            continue  # informational tool — nothing to prove
        gated.append(p.name)
        blocking = [e for e in cases.get(p.name, []) if e not in ("0",)]
        if not blocking:
            gaps.append(p.name)
    if gaps:
        problems.append(
            "scripts with a non-zero exit path but NO blocking test case "
            f"(gate never proven to block): {gaps}")
    return {"gated_scripts": len(gated), "gaps": gaps}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="SDK static structure self-check (frontmatter / refs / scripts / toolstack)")
    ap.add_argument("--json", action="store_true", default=True,
                    help="machine-readable JSON to stdout (default)")
    ap.add_argument("--quiet", action="store_true", help="suppress JSON, exit code only")
    ap.add_argument("--root", default=None,
                    help="check a different SDK root (fixtures/tests; same contract "
                         "as version-check.py --root)")
    args = ap.parse_args(argv)

    global ROOT
    if args.root:
        ROOT = pathlib.Path(args.root).resolve()

    # Prerequisite guard: a partial tree (fixture / partial checkout) must produce a
    # clean fail-closed verdict, never a traceback. Found by the renamed-dir fixture
    # in robustness-suite (C0-2), which copies only 5 scripts and no SKILL.md.
    required = ("SKILL.md", "scripts/toolstack.json")
    absent = [r for r in required if not (ROOT / r).exists()]
    if absent:
        out = {
            "schema": "selfcheck-static.v1",
            "root": str(ROOT),
            "ok": False,
            "problems": [f"incomplete SDK tree — missing: {', '.join(absent)}"],
            "notes": [],
        }
        if not args.quiet:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2

    ts_raw = json.loads((ROOT / "scripts" / "toolstack.json").read_text(encoding="utf-8"))
    ts = check_toolstack()
    out = {
        "schema": "selfcheck-static.v1",
        "root": str(ROOT),
        "frontmatter": check_frontmatter(),
        "references": check_references(),
        "scripts": check_scripts(set(ts_raw.get("sdk_tools", {})),
                                 set(ts_raw.get("sdk_tools_exempt", []))),
        "blocking_coverage": check_blocking_coverage(),
        "toolstack": ts,
        "problems": problems,
        "notes": notes,
        "ok": not problems,
    }
    if not args.quiet:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())
