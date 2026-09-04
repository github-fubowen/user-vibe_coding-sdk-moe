#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diff-risk.py — 补丁风险确定性评分 (v1.0, 2026-08-30)

Purpose: implement ref-22 §8 「Diff Risk Scoring」 as a REAL deterministic gate.
Before this script existed, the protocol declared a hard rule — "score > 0.7
must go to a human" — with no implementation, so it silently degraded into the
agent grading its own patch, which is exactly what the gate exists to prevent.

Scoring (all deterministic, zero LLM, stdlib only):
  score = 0.30*size + 0.30*module + 0.25*history + 0.15*error_class
    size        — diff 规模（行数 + 文件数），越大越难审
    module      — 触及路径的最高风险权重（scripts/ > .github/workflows/ > SKILL.md > docs/）
    history     — 是否命中 known_failures（黑板里的失败签名/路径）
    error_class — 上一次失败的分类（quality 最危险，infra/timeout 最轻）

Bands (ref-22 §8 thresholds — protocol, not suggestion):
    < 0.3   auto      — 确定性闸已过，可自动合并
  0.3–0.7   review    — agent review（ref-19 review-prefilter 关注包）
    > 0.7   human     — 硬闸：人工审核，任何 agent 都不得自行放行

Design rules (SDK §3/G-gates, ref-22 §8):
  * Python 3.9+ stdlib only. Deterministic: same input → same score, always.
  * Fail-closed: unreadable diff → exit 2 (never a silent 0.0 "safe" score).
  * Exit: 0 = score <= 0.7 (may proceed) / 2 = score > 0.7 HUMAN GATE or input error.

Usage:
  python diff-risk.py --diff-file changes.patch
  python diff-risk.py --files scripts/a.py,docs/b.md --lines 180
  python diff-risk.py --diff-file p.patch --known-failures '["scripts/router-stats.py"]' --error-class quality
  git diff | python diff-risk.py --stdin
Exit codes: 0 = proceed / 2 = human gate or input error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from _common import (EXIT_OK, EXIT_ERROR, EXIT_GATE, emit_json,
                   now_iso, schema, build_parser, add_json_flag)

SCHEMA = schema("diagnostic")

# ref-22 §8 thresholds — 协议行，不是建议
AUTO_MAX = 0.3
HUMAN_MIN = 0.7

WEIGHTS = {"size": 0.30, "module": 0.30, "history": 0.25, "error_class": 0.15}

# 最具体优先（first match wins）
MODULE_RULES: list[tuple[str, float]] = [
    ("scripts/data/", 0.50),
    ("scripts/", 1.00),
    (".github/workflows/", 0.90),
    (".github/", 0.70),
    ("SKILL.md", 0.85),
    ("ENGINEERING.md", 0.60),
    ("references/", 0.30),
    ("CHANGELOG.md", 0.15),
    ("README.md", 0.25),
    ("docs/", 0.20),
]
DEFAULT_MODULE_RISK = 0.40

ERROR_CLASS_RISK = {
    "quality": 0.60,   # 逻辑错误：最危险
    "empty": 0.30,
    "infra": 0.20,
    "timeout": 0.20,
}
DEFAULT_ERROR_RISK = 0.40  # 未知/未提供：不假设安全

# 规模归一化基准（达到即满分）
LINES_FOR_FULL_RISK = 300
FILES_FOR_FULL_RISK = 10


def module_risk(path: str) -> tuple[float, str]:
    """Highest matching module weight for a path (most specific rule wins)."""
    p = path.replace("\\", "/")
    for prefix, weight in MODULE_RULES:
        if p.endswith(prefix.rstrip("/")) or prefix.rstrip("/") in p:
            return weight, prefix
    return DEFAULT_MODULE_RISK, "default"


def parse_unified_diff(text: str) -> tuple[list[str], int]:
    """Extract (touched files, changed line count) from a unified diff."""
    files: list[str] = []
    changed = 0
    for line in text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            cand = line[4:].strip()
            cand = re.sub(r"^[ab]/", "", cand)
            if cand and cand != "/dev/null" and cand not in files:
                files.append(cand)
        elif line.startswith("+") or line.startswith("-"):
            if not line.startswith(("+++", "---")):
                changed += 1
    return files, changed


def parse_stat(text: str) -> tuple[list[str], int]:
    """Parse `git diff --stat` summary: '3 files changed, 120 insertions(+), 40 deletions(-)'."""
    m = re.search(r"(\d+)\s+insertions?\(\+\)", text)
    ins = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)\s+deletions?\(-\)", text)
    dele = int(m.group(1)) if m else 0
    files = re.findall(r"^\s*(\S+\.(?:py|md|json|ya?ml|ts|js|sh|ps1))\s*\|", text, re.M)
    return sorted(set(files)), ins + dele


def load_known_failures(raw: str | None) -> list[str]:
    """Accept an inline JSON array, a path to a JSON file, or a task-state JSON."""
    if not raw:
        return []
    txt = raw.strip()
    if txt.startswith("["):
        try:
            return [str(x) for x in json.loads(txt)]
        except json.JSONDecodeError:
            return [txt]
    p = Path(txt)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return [txt]
        if isinstance(data, list):
            return [str(x) for x in data]
        # task-state.v1: 黑板 known_failures
        if isinstance(data, dict):
            kf = (data.get("blackboard") or {}).get("known_failures") or []
            return [str(x) for x in kf]
    return [txt]


def score(files: list[str], changed_lines: int, known_failures: list[str],
          error_class: str | None) -> dict:
    """Deterministic risk score in [0,1] with a per-component breakdown."""
    # size: 行数为主，文件数为辅
    line_f = min(1.0, changed_lines / LINES_FOR_FULL_RISK)
    file_f = min(1.0, len(files) / FILES_FOR_FULL_RISK)
    size = round(0.7 * line_f + 0.3 * file_f, 4)

    # peak = 触及路径中的最高权重。起点必须是 0.0 —— 用 DEFAULT 作下限会让
    # docs/ 这类已知低风险路径被"未知路径"默认值抬高（0.2 被压成 0.4）。
    module = 0.0
    module_hit = "default"
    for f in files:
        w, hit = module_risk(f)
        if w > module:
            module, module_hit = w, hit
    if not files:
        module, module_hit = DEFAULT_MODULE_RISK, "no-files"
    module = round(module, 4)

    hits: list[str] = []
    for kf in known_failures:
        for f in files:
            if kf and (kf in f or f in kf):
                hits.append(f"{kf} ~ {f}")
                break
    history = 1.0 if hits else 0.0

    ec = (error_class or "").strip().lower() or None
    ec_risk = ERROR_CLASS_RISK.get(ec, DEFAULT_ERROR_RISK if ec is None else DEFAULT_ERROR_RISK)

    total = round(WEIGHTS["size"] * size + WEIGHTS["module"] * module
                  + WEIGHTS["history"] * history + WEIGHTS["error_class"] * ec_risk, 4)
    total = max(0.0, min(1.0, total))

    if total > HUMAN_MIN:
        band, decision = "human", "人工审核（硬闸，不自动推进）"
    elif total >= AUTO_MAX:
        band, decision = "review", "agent review（ref-19 关注包）"
    else:
        band, decision = "auto", "自动合并（确定性闸已过）"

    reasons = [
        f"size={size} ({changed_lines} lines / {len(files)} files)",
        f"module={module} (peak '{module_hit}')",
        f"history={history} ({len(hits)} known_failure hits)",
        f"error_class={ec or 'none'} → {ec_risk}",
    ]
    return {
        "schema": SCHEMA, "score": total, "band": band, "decision": decision,
        "thresholds": {"auto_max": AUTO_MAX, "human_min": HUMAN_MIN},
        "components": {"size": size, "module": module, "history": history,
                       "error_class": ec_risk},
        "weights": WEIGHTS,
        "inputs": {"files": files, "changed_lines": changed_lines,
                   "known_failure_hits": hits, "error_class": ec},
        "reasons": reasons,
    }


def main() -> int:
    ap = build_parser("Deterministic diff risk gate (ref-22 §8)")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--diff-file", default=None, help="unified diff file")
    src.add_argument("--stdin", action="store_true", help="read unified diff from stdin")
    src.add_argument("--stat", default=None, help="`git diff --stat` text")
    src.add_argument("--files", default=None, help="comma-separated touched paths")
    ap.add_argument("--lines", type=int, default=0, help="changed line count (with --files)")
    ap.add_argument("--known-failures", default=None,
                    help='JSON array, path to JSON list, or task-state.v1 JSON')
    ap.add_argument("--error-class", default=None,
                    help="last failure class: quality|empty|infra|timeout")
    ap.add_argument("--verify-confidence", type=float, default=None,
                    help="0-1: verify-runner confidence -> synthesize repair_confidence "
                         "(T-23/B.21: 0.5*(1-risk_score)+0.5*vc; <0.7 -> human_review_required)")
    add_json_flag(ap)
    args = ap.parse_args()

    files: list[str] = []
    changed = 0
    if args.diff_file:
        p = Path(args.diff_file)
        if not p.exists():
            print(f"[fatal] diff file not found: {p}", file=sys.stderr)
            return EXIT_GATE
        files, changed = parse_unified_diff(p.read_text(encoding="utf-8", errors="replace"))
    elif args.stdin:
        files, changed = parse_unified_diff(sys.stdin.read())
    elif args.stat:
        files, changed = parse_stat(args.stat)
    elif args.files:
        files = [f.strip() for f in args.files.split(",") if f.strip()]
        changed = args.lines
    else:
        print("[fatal] no diff source: use --diff-file / --stdin / --stat / --files",
              file=sys.stderr)
        return EXIT_GATE

    out = score(files, changed, load_known_failures(args.known_failures), args.error_class)

    # T-23（v2.10.0, F-29 附带 / verification-kernel B.21）：修复置信度合成 ——
    # diff-risk（补丁清洁度）与 verify --confidence（验证实证）此前是两处孤立信号。
    # 合成式（确定性启发，非模型打分）：repair_confidence = 0.5*(1-risk) + 0.5*vc；
    # <0.7 -> human_review_required（对齐 kernel "require_human_review_below_confidence"）。
    if args.verify_confidence is not None:
        if not (0.0 <= args.verify_confidence <= 1.0):
            print("[fatal] --verify-confidence must be within [0, 1]", file=sys.stderr)
            return EXIT_GATE
        rc = round(0.5 * (1 - out["score"]) + 0.5 * args.verify_confidence, 3)
        out["repair_confidence"] = rc
        out["human_review_required"] = rc < 0.7

    if args.json:
        emit_json(out)
    else:
        print(f"== diff-risk: score={out['score']} band={out['band']} ==")
        print(f"  decision: {out['decision']}")
        for r in out["reasons"]:
            print(f"    - {r}")
        if out["band"] == "human":
            print("  [GATE] score > 0.7 — 人工审核，不得自动推进（ref-22 §8 硬闸）")
    return EXIT_GATE if out["band"] == "human" else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
