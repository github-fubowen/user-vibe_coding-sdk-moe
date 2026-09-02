#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
version-check.py — 版本串一致性 + CHANGELOG 顺序确定性闸（T-16 / F-26）

Why this exists (F-26, v2.8.1 自查):
  v2.8.1 的 CHANGELOG 条目被手工写在 v2.8.0 条目**之后** —— 文件首个 `## vX.Y.Z`
  因此仍是 v2.8.0，与 SKILL/README 的 v2.8.1 失配（audit 145/146 唯一红灯）。
  根因：`bump-version.py` 的 layout-repair 插入（插到首个 `## vX` 之前）在
  header 已存在时直接 `[skip]`，手工写入的顺序错误于是无人纠正。
  更糟的是 **ci-smoke 当时根本不检查版本串** —— 红灯只能靠 workspace 侧的
  audit_sdk.py 发现。本脚本把该检查上移为 SDK 自带门禁的第 6 项（且置为最前，
  契合 verification-kernel「cheapest-first」：最便宜的闸先跑）。

Checks (all fail-closed):
  1. SKILL.md frontmatter 版本串
  2. SKILL.md 正文首个版本串（H1 标题）
  3. README.md blurb 版本串
  4. README.md 「版本：」行版本串
  5. CHANGELOG.md 首个 `## vX.Y.Z` 版本串
  6. CHANGELOG.md 条目顺序严格递减（首个即最新）且无重复条目
Above 1-5 must all be equal; 6 must hold.

Exit: 0 = consistent / 2 = any mismatch or ordering violation.

Usage:
  python version-check.py                 # 默认校验本 SDK 根目录
  python version-check.py --json
  python version-check.py --root <SDK_DIR>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SDK_DIR = SCRIPT_DIR.parent

SCHEMA = "version-check.v1"
VER_RE = re.compile(r"v\d+\.\d+\.\d+")
CL_HEAD_RE = re.compile(r"^## (v\d+\.\d+\.\d+)", re.M)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"[fatal] cannot read {path.name}: {e}")


def _first_ver(text: str, where: str) -> str:
    m = VER_RE.search(text)
    if not m:
        raise SystemExit(f"[fatal] no version string (vX.Y.Z) found in {where}")
    return m.group(0)


def _split_frontmatter(skill: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). No frontmatter -> ('', whole)."""
    if skill.startswith("---"):
        parts = skill.split("---", 2)
        if len(parts) >= 3:
            return parts[1], parts[2]
    return "", skill


def _vtuple(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def check(root: Path) -> dict:
    skill_p, readme_p, cl_p = root / "SKILL.md", root / "README.md", root / "CHANGELOG.md"
    for p in (skill_p, readme_p, cl_p):
        if not p.exists():
            return {"schema": SCHEMA, "ok": False, "root": str(root),
                    "versions": {}, "changelog_order_ok": False, "changelog_top": None,
                    "problems": [f"missing required file: {p.name}"]}

    skill = _read(skill_p)
    readme = _read(readme_p)
    cl = _read(cl_p)

    fm, body = _split_frontmatter(skill)
    versions = {
        "skill_frontmatter": _first_ver(fm or skill, "SKILL.md frontmatter"),
        "skill_title": _first_ver(body, "SKILL.md body/H1"),
        "readme_blurb": _first_ver(readme, "README.md blurb"),
    }
    # README 的「版本：」行（可能在 blurb 之后，单独定位）
    if "版本：" in readme:
        versions["readme_version_line"] = _first_ver(readme.split("版本：", 1)[1],
                                                     "README.md version line")
    else:
        versions["readme_version_line"] = None

    cl_heads = CL_HEAD_RE.findall(cl)
    if not cl_heads:
        return {"schema": SCHEMA, "ok": False, "root": str(root), "versions": versions,
                "changelog_order_ok": False, "changelog_top": None,
                "problems": ["CHANGELOG.md has no `## vX.Y.Z` entry heading"]}
    versions["changelog_top"] = cl_heads[0]

    problems = []

    # --- 1) 版本串一致性 ---
    comparable = {k: v for k, v in versions.items() if v is not None}
    distinct = sorted(set(comparable.values()), key=_vtuple, reverse=True)
    if len(distinct) > 1:
        worst = distinct[0]  # 最高版本视为"应为"的当前版本
        for k, v in comparable.items():
            if v != worst:
                problems.append(f"version mismatch: {k}={v} != {worst}")
    # CHANGELOG 首个条目必须等于当前版本（顺序倒置的主症状）
    if versions["changelog_top"] != distinct[0]:
        problems.append(
            f"CHANGELOG first entry ({versions['changelog_top']}) is not the current "
            f"version ({distinct[0]}) — entries are newest-first; a manual edit likely "
            f"inserted the newest block below an older one (F-26). Fix: move the newest "
            f"block above, or re-run `bump-version.py <ver> --apply`."
        )

    # --- 2) 条目顺序严格递减 + 无重复 ---
    order_ok = True
    seq = [_vtuple(v) for v in cl_heads]
    for i in range(1, len(seq)):
        if seq[i] >= seq[i - 1]:
            order_ok = False
            problems.append(
                f"CHANGELOG order violation: {cl_heads[i - 1]} must come after "
                f"{cl_heads[i]} (newest-first)"
            )
    dups = sorted({v for v in cl_heads if cl_heads.count(v) > 1})
    if dups:
        order_ok = False
        problems.append(f"duplicate CHANGELOG entries: {', '.join(dups)}")

    return {
        "schema": SCHEMA,
        "ok": not problems,
        "root": str(root),
        "versions": versions,
        "changelog_order_ok": order_ok,
        "changelog_top": versions["changelog_top"],
        "problems": problems,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Version-string + CHANGELOG order gate (T-16, F-26)")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    ap.add_argument("--root", default=str(SDK_DIR), help="SDK root (default: parent of scripts/)")
    args = ap.parse_args()

    rep = check(Path(args.root).resolve())

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for k, v in rep["versions"].items():
            print(f"  {k:<22} {v}")
        print(f"  {'changelog_order_ok':<22} {rep['changelog_order_ok']}")
        for p in rep["problems"]:
            print(f"  [!!] {p}", file=sys.stderr)
        print(f"version-check: {'CONSISTENT' if rep['ok'] else 'MISMATCH'}")

    return 0 if rep["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
