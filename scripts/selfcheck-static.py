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

# --- T-541 (F-61): SKILL.md 热路径尺寸闸 --------------------------------------
# SKILL.md 是 **prompt cache 的稳定前缀**（G5）也是每次会话必读的热路径：它每长
# 1KB，所有任务都要多付这 1KB。所以尺寸不是观感问题，是成本与缓存命中率问题。
# warn/fail 阈值常量化，`--max-skill-bytes` 可覆盖 warn（fail = warn + 5,000 的
# 带宽保持不变）—— 阈值是协议行，改它要过 CHANGELOG。
SKILL_WARN_BYTES = 40_000
SKILL_FAIL_BYTES = 45_000
SKILL_FAIL_DELTA = SKILL_FAIL_BYTES - SKILL_WARN_BYTES
# 清偿包 sdd-sdk-improve-v2.11 的 S-4 判据（比 warn 更严）：下沉后应 ≤37,000B。
# 只作 advisory note，不阻塞 —— 它是"本轮验收目标"，warn/fail 才是长期闸。
S4_TARGET_BYTES = 37_000

# schema-4 (R-3, ResourceOS §19): tool-level health is a 3-state subset of the
# reference 7-state lifecycle — full lifecycle (draft/deprecated/...) is out of
# scope for a ~50-resource skill, and §34 scale-driven says so.
HEALTH_STATES = {"active", "degraded", "unavailable"}

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

    # --- schema-4 fields (R-3, ResourceOS §5/§6/§19) -----------------------
    # All four fields are OPTIONAL and backward-compatible: absent -> note,
    # present-but-invalid -> problem. Only the capability vocabulary is a hard
    # filter (§6.3 anti-proliferation gate: unknown words must not spread).
    vocab = data.get("capability_vocab")
    vocab_set = set(vocab) if isinstance(vocab, list) else None
    if vocab is None and (data.get("schema") or 0) >= 4:
        notes.append("toolstack schema>=4 but capability_vocab missing")

    bad_caps: list[str] = []
    empty_caps: list[str] = []
    missing_caps: list[str] = []
    bad_health: list[str] = []
    bad_fallback: list[str] = []
    health_summary: dict[str, int] = {}
    covered = 0
    total = 0
    for tname, table in (("sdk_tools", sdk_tools), ("local_tools", local_tools)):
        for name, meta in table.items():
            total += 1
            caps = meta.get("capabilities")
            if caps is None:
                missing_caps.append(f"{tname}:{name}")
            elif not isinstance(caps, list) or not all(isinstance(c, str) for c in caps):
                bad_caps.append(f"{tname}:{name} (capabilities must be list[str])")
            elif not caps:
                empty_caps.append(f"{tname}:{name}")
            else:
                covered += 1
                if vocab_set is not None:
                    unknown = [c for c in caps if c not in vocab_set]
                    if unknown:
                        bad_caps.append(f"{tname}:{name} unknown capability {unknown}")
            health = meta.get("health")
            if health is not None:
                if health not in HEALTH_STATES:
                    bad_health.append(f"{tname}:{name}={health}")
                else:
                    health_summary[health] = health_summary.get(health, 0) + 1
            fb = meta.get("fallback")
            if fb is not None and not isinstance(fb, str):
                bad_fallback.append(f"{tname}:{name} (fallback must be str|null)")
            elif isinstance(fb, str) and fb not in table:
                bad_fallback.append(f"{tname}:{name} -> {fb} (not in {tname})")

    if bad_caps:
        problems.append(f"toolstack capabilities invalid: {bad_caps}")
    if bad_health:
        problems.append(f"toolstack health not in {sorted(HEALTH_STATES)}: {bad_health}")
    if bad_fallback:
        problems.append(f"toolstack fallback dangling: {bad_fallback}")
    if empty_caps:
        notes.append(f"toolstack entries with empty capabilities: {empty_caps}")
    if missing_caps:
        notes.append(f"toolstack entries without capabilities field: {missing_caps}")

    return {
        "schema": data.get("schema"),
        "last_check": data.get("last_check"),
        "sdk_tools": len(sdk_tools),
        "local_tools": len(local_tools),
        "refs": len(refs),
        "broken_scripts": broken_scripts,
        "broken_refs": broken_refs,
        "capability_vocab": len(vocab_set) if vocab_set is not None else None,
        "capability_coverage": f"{covered}/{total}",
        "health": health_summary,
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
    # 边界（R-5 事故加固）：`.*?` + re.S 会跨用例贪婪匹配 —— 任何含 `"script":`
    # 的夹具 JSON 文本都会把后面真正的拦截用例吞掉，导致该脚本被误报「无拦截用例」。
    # 限制 script→expect 的距离（同一条 dict 内必然很近），跨用例即不匹配。
    for m in re.finditer(r'"script":\s*"([^"]+)"(.{0,400}?)"expect":\s*([0-9]+)',
                         suite_src, re.S):
        add(m.group(1), m.group(3))

    # style 3（v2.10.12 F-59 Phase 1）：声明式用例 manifest — scripts/cases/*.json。
    # 常量参数用例迁出源码后，部分脚本的拦截用例只存在于 manifest —— 源码扫描
    # 必须合并这里，否则 blocking-coverage 误报「无拦截用例」。坏 JSON 不在此处
    # 报错（套件运行时 fail-closed 才是权威），这里只收集合法条目。
    cases_dir = ROOT / "scripts" / "cases"
    if cases_dir.exists():
        for mf in sorted(cases_dir.glob("*.json")):
            try:
                mdata = json.loads(mf.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            items = mdata.get("cases") if isinstance(mdata, dict) else None
            for c in items or []:
                if isinstance(c, dict) and isinstance(c.get("script"), str) \
                        and isinstance(c.get("expect"), int):
                    add(c["script"], str(c["expect"]))
    return found


def check_skill_size(warn_bytes: int = SKILL_WARN_BYTES,
                     fail_bytes: int | None = None) -> dict:
    """T-541：SKILL.md 热路径尺寸闸。fail → problem（exit 2）；warn 与 S-4 只提示。"""
    p = ROOT / "SKILL.md"
    if not p.exists():
        problems.append("SKILL.md missing")
        return {}
    size = p.stat().st_size
    fail = fail_bytes if fail_bytes is not None else warn_bytes + SKILL_FAIL_DELTA
    if size > fail:
        problems.append(
            f"SKILL.md {size:,}B > fail 阈值 {fail:,}B —— 热路径超预算（F-61）。"
            f"处置：把明细下沉 refs，热路径只留判据与指针")
        verdict = "fail"
    elif size > warn_bytes:
        notes.append(f"SKILL.md {size:,}B > warn 阈值 {warn_bytes:,}B（fail 在 {fail:,}B）"
                     f"—— 下一次改动前先把明细下沉 refs")
        verdict = "warn"
    else:
        verdict = "ok"
    if size > S4_TARGET_BYTES:
        notes.append(f"SKILL.md {size:,}B > 清偿包 S-4 判据 {S4_TARGET_BYTES:,}B"
                     f"（advisory，不阻塞）")
    return {"bytes": size, "warn_bytes": warn_bytes, "fail_bytes": fail,
            "s4_target_bytes": S4_TARGET_BYTES, "verdict": verdict}


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


def check_docs() -> dict:
    """v2.10.13 docs 段：D-01 索引存在性 / D-02 schema 合规（+ id 唯一）。

    为什么只做这两条：selfcheck 是 **tier-0 秒级闸**，且不得依赖 D 盘语料池
    （跨盘 / CI / fixture 都可能没有）。D-03 漂移 / D-04 卡片 / D-08 来源
    需要读语料盘，交给 `doc-pipeline.py check`（ci-smoke 第 3 步）。

    部分树（robustness 的 _sdk_tree* 夹具只有 5 个脚本）没有 doc-pipeline.py
    → 跳过而不是红灯：自检的"完整性"只对**装了该能力的树**成立。
    """
    pipe = ROOT / "scripts" / "doc-pipeline.py"
    if not pipe.exists():
        notes.append("docs check skipped: doc-pipeline.py absent (partial tree)")
        return {"skipped": True, "reason": "doc-pipeline.py absent"}
    p = ROOT / "scripts" / "data" / "doc-index.json"
    if not p.exists():
        problems.append(
            "D-01: scripts/data/doc-index.json missing "
            "(run: doc-pipeline.py register --scan --init)")
        return {"skipped": False, "index": str(p), "exists": False, "total_docs": 0}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        problems.append(f"D-01: doc-index.json unreadable: {e}")
        return {"skipped": False, "index": str(p), "exists": True, "readable": False}
    if not isinstance(data, dict) or data.get("schema") != "doc-index.v1":
        problems.append(f"D-02: doc-index.json schema != doc-index.v1 "
                        f"(got {data.get('schema') if isinstance(data, dict) else type(data).__name__})")
        return {"skipped": False, "exists": True, "readable": True, "schema_ok": False}
    docs = data.get("docs")
    if not isinstance(docs, list):
        problems.append("D-02: doc-index.json 'docs' is not a list")
        return {"skipped": False, "exists": True, "readable": True, "schema_ok": False}
    req = ["id", "name", "path", "type", "status"]
    bad = [d.get("id", "?") for d in docs
           if not isinstance(d, dict) or any(f not in d for f in req)
           or not isinstance(d.get("tags"), list)]
    if bad:
        problems.append(f"D-02: docs missing required fields {req}+tags(list): {bad}")
    ids = [d.get("id") for d in docs if isinstance(d, dict)]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        problems.append(f"D-05: duplicate doc ids in index: {dup}")
    return {"skipped": False, "exists": True, "readable": True, "schema_ok": True,
            "total_docs": len(docs), "corpus_root": data.get("corpus_root"),
            "invalid": bad, "duplicate_ids": dup}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="SDK static structure self-check (frontmatter / refs / scripts / toolstack)")
    ap.add_argument("--json", action="store_true", default=True,
                    help="machine-readable JSON to stdout (default)")
    ap.add_argument("--quiet", action="store_true", help="suppress JSON, exit code only")
    ap.add_argument("--root", default=None,
                    help="check a different SDK root (fixtures/tests; same contract "
                         "as version-check.py --root)")
    ap.add_argument("--max-skill-bytes", type=int, default=SKILL_WARN_BYTES,
                    help=f"覆盖 SKILL.md warn 阈值（默认 {SKILL_WARN_BYTES:,}B；"
                         f"fail = warn + {SKILL_FAIL_DELTA:,}B，T-541）")
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
        "docs": check_docs(),
        "skill_size": check_skill_size(args.max_skill_bytes),
        "problems": problems,
        "notes": notes,
        "ok": not problems,
    }
    if not args.quiet:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())
