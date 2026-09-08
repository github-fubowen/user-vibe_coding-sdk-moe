#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
accept-score.py — Gated 多维验收评分（A-1，AOS §20.3 / §21.3）

Why: `ci-smoke` 的"8/8 全绿"是**布尔合取**——它回答"有没有哪道闸红"，回答不了
"整体处在什么水平、哪个维度在拖后腿、这个分数有多可信"。AOS §20.2 明确指出：把
安全/数据丢失这类**闸门属性**与效率/可维护性这类**质量属性**混进一个连续分数是
反模式。所以本脚本严格两段式：

    Step 1  硬闸（布尔，先判）：任何一道红 → REJECT，composite = report-only
            （绝不用高分把安全或正确性"买回来"）
    Step 2  质量维几何均值（仅闸全绿时）：Correctness^wc × Reliability^wr ×
            Autonomy^wa × Efficiency^we × Maintainability^wm，权重按任务类取行
            （D5：先 4 组，见 data/acceptance-weights.v1.json）
    Step 3  缺失维度**照实缺席**：reliability/autonomy 待 A-9/A-10 才有信号，
            宁可少算一维（权重在现有维上重新归一化 + 报 coverage），不用 1.0 假装。

Inputs（全部是既有产物，零新采集）:
    --smoke    ci-smoke 报告 JSON（硬闸 + robustness/golden 的 pass_rate 明细）
    --golden   golden-run 报告 JSON（correctness / efficiency，可选）
    --dim k=v  手工补维（如 --dim reliability=0.8），用于 A-9/A-10 落地前的过渡

Design rules: stdlib only · 零网络 · 只读 · report-only（默认 exit 0，--gate 时
REJECT 才 exit 2 —— 评分本身不阻断，阻断仍由 ci-smoke 的布尔闸负责）。

Usage:
  python scripts/accept-score.py --smoke scripts/data/ci-smoke-2026-09-07.json
  python scripts/accept-score.py --smoke <smoke.json> --golden <golden.json> --cell bug_fix --json
  python scripts/accept-score.py --smoke <smoke.json> --gate        # REJECT → exit 2
Exit: 0 = 已出分（含 REJECT 报告）· 2 = --gate 且硬闸未过 · 2 = 输入不可用
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WEIGHTS_FILE = SCRIPT_DIR / "data" / "acceptance-weights.v1.json"
CONTRACT_FILE = SCRIPT_DIR / "data" / "acceptance-contract.v1.json"
DIMS = ("correctness", "reliability", "autonomy", "efficiency", "maintainability")
_RATE_RE = re.compile(r"pass_rate=([0-9.]+)")


def load_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def pick_rate(smoke: dict, step_name: str) -> float | None:
    """从 ci-smoke 步骤明细里抠 pass_rate（detail 形如 "pass_rate=1.0"）。"""
    for st in smoke.get("steps") or []:
        if st.get("step") == step_name:
            m = _RATE_RE.search(str(st.get("detail") or ""))
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    return None
    return None


def hard_gates(smoke: dict) -> tuple[bool, list[dict]]:
    """布尔硬闸：任一失败即 REJECT（AOS §21.1 的 SDK 落地形态）。"""
    checks: list[dict] = []
    for st in smoke.get("steps") or []:
        checks.append({"gate": st.get("step"), "pass": bool(st.get("ok"))})
    acc = smoke.get("acceptance") or {}
    if acc:
        checks.append({"gate": "acceptance-contract",
                       "pass": acc.get("match") is not False,
                       "detail": acc.get("problems") or []})
    return all(c["pass"] for c in checks), checks


def main() -> int:
    ap = argparse.ArgumentParser(description="Gated multi-dimensional acceptance score (AOS §20.3)")
    ap.add_argument("--smoke", required=True, help="ci-smoke report JSON")
    ap.add_argument("--golden", default=None, help="golden-run report JSON（correctness/efficiency）")
    ap.add_argument("--cell", default="default",
                    help="任务类（code/bug_fix/review/documentation；未知回落 default）")
    ap.add_argument("--dim", action="append", default=[],
                    help="手工补维 --dim reliability=0.8（可重复）")
    ap.add_argument("--eff-baseline", type=float, default=None,
                    help="效率基线（tokens/成功样本）；给了才算 efficiency 维")
    ap.add_argument("--weights", default=None, help="权重表路径（默认 data/acceptance-weights.v1.json）")
    ap.add_argument("--gate", action="store_true", help="硬闸未过时 exit 2（默认仅报告）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    smoke = load_json(Path(args.smoke))
    if not smoke:
        print(f"[fatal] unreadable smoke report: {args.smoke}", file=sys.stderr)
        return 2

    wpath = Path(args.weights) if args.weights else WEIGHTS_FILE
    w = load_json(wpath) or {}
    groups = w.get("groups") or {}
    weights = dict(groups.get(args.cell) or w.get("default") or {})
    if not weights:
        weights = {d: 1.0 / len(DIMS) for d in DIMS}

    gates_ok, gate_checks = hard_gates(smoke)

    # --- 维度取值：有信号才算，没有就缺席（不用 1.0 假装）---
    dims: dict[str, float] = {}
    golden = load_json(Path(args.golden)) if args.golden else None
    if golden is not None:
        pr = golden.get("pass_rate")
        if pr is not None:
            dims["correctness"] = float(pr)
    if "correctness" not in dims:
        r = pick_rate(smoke, "golden v3 offline")
        if r is not None:
            dims["correctness"] = r
    r = pick_rate(smoke, "robustness-suite")
    if r is not None:
        dims["maintainability"] = r
    if golden is not None and args.eff_baseline:
        eff = golden.get("token_efficiency")
        if isinstance(eff, (int, float)) and eff > 0:
            dims["efficiency"] = max(0.0, min(1.0, args.eff_baseline / float(eff)))
    for kv in args.dim:
        if "=" in kv:
            k, v = kv.split("=", 1)
            try:
                dims[k.strip()] = max(0.0, min(1.0, float(v)))
            except ValueError:
                pass

    missing = [d for d in DIMS if d not in dims]
    used = {d: dims[d] for d in DIMS if d in dims}

    quality = None
    if used and gates_ok:
        wsum = sum(weights.get(d, 0.0) for d in used)
        if wsum > 0:
            # 几何均值，权重在被覆盖维上重新归一化
            log_s = sum((weights.get(d, 0.0) / wsum) * math.log(max(v, 1e-9))
                        for d, v in used.items())
            quality = round(math.exp(log_s), 6)

    out = {
        "schema": "accept-score.v1",
        "smoke": str(args.smoke),
        "cell": args.cell,
        "decision": "ACCEPT_CANDIDATE" if gates_ok else "REJECT",
        "hard_gates_ok": gates_ok,
        "hard_gates": gate_checks,
        "dims": {d: (round(used[d], 6) if d in used else None) for d in DIMS},
        "weights_used": {d: round(weights.get(d, 0.0), 4) for d in DIMS},
        "quality_score": quality,
        "coverage": {"dims_used": len(used), "dims_total": len(DIMS),
                     "missing": missing},
        "note": ("REJECT：硬闸未过，quality_score 不计算（report-only，不得用于排名或放行）"
                 if not gates_ok else
                 (f"仅 {len(used)}/{len(DIMS)} 维有信号"
                  +                   (f"，缺 {'/'.join(missing)}" if missing else "")
                  + ("；" + "、".join(
                      f"{d} 待 {t}" for d, t in (("reliability", "A-9"), ("autonomy", "A-10"))
                      if d in missing) if any(d in missing for d in ("reliability", "autonomy"))
                     else ""))),
    }

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"== accept-score · cell={args.cell} ==")
        print(f"  hard gates : {'PASS' if gates_ok else 'FAIL'}  "
              f"({sum(1 for c in gate_checks if c['pass'])}/{len(gate_checks)})")
        for c in gate_checks:
            if not c["pass"]:
                print(f"    !! {c['gate']} {c.get('detail') or ''}")
        for d in DIMS:
            v = out["dims"][d]
            print(f"  {d:<16}: {'-' if v is None else f'{v:.4f}'}   w={out['weights_used'][d]}")
        print(f"  quality_score: {'-' if quality is None else f'{quality:.4f}'}"
              f"   coverage {len(used)}/{len(DIMS)}")
        print(f"  decision: {out['decision']}  — {out['note']}")

    if args.gate and not gates_ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
