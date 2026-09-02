#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-runner.py — 修复/变更后的确定性验证闸 (v2.1, 2026-08-30)

Purpose: replace the LLM-narrated verify loop (§5.6 / ref-18 §4) with ONE
deterministic call that runs test/lint/build steps and reports pass/fail JSON.
Code execution is the ground truth; the agent only reads the verdict + bounded
diagnostic tails instead of narrating "now running tests... now checking...".

v2.0 changes (Coding Agent OS 吸收 T6/T7):
  * Layered verification (coding-agent-os §12): config `layers` runs
    cheapest-first with SHORT-CIRCUIT — first failing layer stops the chain,
    report records `stopped_at` + `error_class` (syntax/type/lint/... or
    timeout/command_not_found/test_failed).
  * Unified diagnostic schema (diagnostic.v1, coding-agent-os §28.3): every
    report carries top-level `schema` + per-step `error_class` + `diagnostics`.
  * Backward compatible: `steps` (v1) still supported; `--layers` filters a
    subset by name substring.
  * v2.1: step 支持 `allow_missing: true` —— 可选工具未安装（exit 126/127）时记
    `skipped` 而非失败。随包预设（scripts/presets/）依赖此项，否则缺 ruff/mypy
    的机器上闸门必然红灯，预设就没人用。
  * v2.2 (2026-09-01, T-07 自查报告): `--confidence <0-1>` 驱动自适应验证深度
    （AgentOS #1 —— 有信心的小改动不必跑满 9 层；低置信任务验证拉满）：
    <0.4 全层 / 0.4-0.7 语法+类型+目标测试 / >0.7 语法+目标测试。
    显式 `--layers` 优先于 --confidence（显式声明 > 启发式）。

Design rules (SDK §3/G-gates, §5.6 verification five-state, ref-20):
  * Config: verify.json in --config (default: ./verify.json) — {steps:[...]} or {layers:[...]}
  * Python 3.9+ stdlib only. JSON out. Exit: 0 = all pass / 2 = any fail.
  * Output tails are BOUNDED (--tail 12 lines/step) — never dump full logs (G1).
  * Verification states are NOT judged here: script reports pass/fail facts;
    the five-state judgment (REGRESSION/UNKNOWN etc.) stays with the agent (ref-18/ref-20).

Usage:
  python verify-runner.py --config verify.json            # human table
  python verify-runner.py --config verify.json --json     # machine-readable
  python verify-runner.py --config verify.json --layers syntax,lint   # subset
  python verify-runner.py --cmd "pytest -q"               # single ad-hoc step
Exit codes: 0 = all steps passed / 2 = at least one step failed (or config missing).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "diagnostic.v1"
LAYER_ORDER = ["syntax", "type", "lint", "test-targeted", "test-full",
               "integration", "security", "regression", "invariants"]

# T-18（v2.9.0, F-28）：显式别名匹配 —— 消除子串巧合（此前 "type" in "typecheck"
# 纯属拼写巧合，层名一改即静默失效）。唯一匹配入口 _layer_matches：
#   1. 层名 == token（精确）
#   2. 层名 ∈ 别名表[token]
#   3. 层名以 token + "-" 开头（test → test-targeted / test-full 前缀族）
# 子串包含不再作为匹配手段（"typography" 不再命中 "type"）。
LAYER_ALIASES = {
    "type": ("type", "typecheck"),
}


def _layer_matches(name: str, token: str) -> bool:
    n = (name or "").lower()
    if n == token:
        return True
    if n in LAYER_ALIASES.get(token, ()):
        return True
    return n.startswith(token + "-")


# T-22（v2.9.0, F-33）：测试选择（Test Impact Analysis 的约定映射版）。
# verification-kernel §B.5：inner repair loop 通常只到 Stage 0-6 —— 每轮修复都跑
# 全量测试是低配机上最大的时间浪费。约定策略（stdlib 零依赖，覆盖优先）：
#   变更文件 stem -> <roots>/test_<stem>.py / <roots>/<stem>_test.py
#   变更文件本身是测试（test_*.py / *_test.py）-> 直接收录
# 无映射 = fail-open（保持该层原 cmd，附 note），绝不因映射不到而静默跳过验证。
DEFAULT_TEST_ROOTS_FALLBACK = "tests"


def select_targeted_tests(changed: list[str], project: Path,
                          cfg: dict | None) -> tuple[list[str], str]:
    """Map changed files to existing test files (convention strategy).

    Returns (matched_test_paths, note). Fail-open: empty list when nothing maps.
    """
    sel = (cfg or {}).get("test_selection") or {}
    if sel.get("strategy") not in (None, "convention"):
        return [], f"unsupported test_selection.strategy={sel.get('strategy')!r} — skipped"
    max_tests = int(sel.get("max_tests", 50))
    if sel.get("test_roots"):
        roots = [str(r) for r in sel["test_roots"]]
    else:
        roots = [DEFAULT_TEST_ROOTS_FALLBACK] if (project / DEFAULT_TEST_ROOTS_FALLBACK).is_dir() else ["."]

    matched: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        if path and path not in seen:
            seen.add(path)
            matched.append(path)

    for f in changed:
        norm = f.replace("\\", "/").strip()
        if not norm:
            continue
        name = norm.rsplit("/", 1)[-1]
        # 变更文件本身就是测试 → 直接作为目标测试
        if name.startswith("test_") or name.endswith("_test.py"):
            _add(norm)
            continue
        stem = name.rsplit(".", 1)[0]
        if not stem:
            continue
        for root in roots:
            base = project / root
            if not base.is_dir():
                continue
            pats = ([f"test_{stem}.py", f"{stem}_test.py"] if root == "."
                    else [f"**/test_{stem}.py", f"**/{stem}_test.py"])
            for pat in pats:
                for p in sorted(base.glob(pat)):
                    if p.is_file():
                        _add(p.relative_to(project).as_posix())

    note = ""
    if len(matched) > max_tests:
        note = f"matched {len(matched)} tests, capped at {max_tests} (test_selection.max_tests)"
        matched = matched[:max_tests]
    return matched, note


def log(msg: str) -> None:
    print(msg, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def infer_error_class(name: str, exit_code: int) -> str:
    """Map a failed step to an error_class (diagnostic.v1, ref-22 failure-class aware)."""
    if exit_code == 127:
        return "command_not_found"
    if exit_code == 124:
        return "timeout"
    if name in LAYER_ORDER:
        return name
    if name in ("syntax", "type", "lint") or any(k in name.lower() for k in
                                                 ("syntax", "type", "lint", "compile")):
        return "syntax"
    return "test_failed"


def run_step(name: str, cmd: list[str], timeout: int, tail: int, cwd: str | None) -> dict:
    t0 = datetime.now()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        res = subprocess.CompletedProcess(cmd, 127, "", "command not found")
    except subprocess.TimeoutExpired:
        res = subprocess.CompletedProcess(cmd, 124, "", "timeout")
    dur_ms = int((datetime.now() - t0).total_seconds() * 1000)
    out = (res.stdout or "").strip().splitlines()
    err = (res.stderr or "").strip().splitlines()
    combined = out + (["[stderr]"] + err if err else [])
    ok = res.returncode == 0
    return {
        "name": name,
        "cmd": cmd,
        "ok": ok,
        "exit_code": res.returncode,
        "duration_ms": dur_ms,
        "error_class": None if ok else infer_error_class(name, res.returncode),
        "tail": combined[-tail:],
    }


def load_config(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log(f"[fatal] invalid JSON in {path}")
        sys.exit(2)


# T-07（AgentOS #1）：置信度 → 验证深度映射。低置信=验证拉满；高置信=轻量。
# token 是低配机的实痛 —— 全任务一刀切 9 层验证是纯浪费（SDK 自查报告 F-21）。
#   conf < 0.4  → full   （不筛层）
#   0.4 ~ 0.7   → medium （语法 + 类型 + 目标测试 [+ security]）
#   conf > 0.7  → light  （语法 + 目标测试 [+ security]）
#
# T-17（v2.8.2, F-27）：**security 层是硬闸，任何档位都不得剔除**。
# 背景：v2.8.1 自查实测 `--confidence 0.9` → selected_layers=["syntax","test"]，
# 随包预设定义的 security（pip-audit / npm audit）被静默跳过 —— 与 verification-kernel
# §B.3「Stage 9 security = hard block，无论下游阶段状态」冲突，也与自家 T-12
# （安全扫描验证阶段）自相矛盾。ALWAYS_ON 即在任何档位无条件保留的层名子串。

ALWAYS_ON_TOKENS = ("security",)


def select_by_confidence(steps: list[dict], confidence: float) -> tuple[list[dict], str, str | None]:
    """Map --confidence to a layer subset. Returns (steps, depth, note)."""
    if confidence < 0.4:
        return steps, "full", None          # 低置信：不筛层，验证拉满
    if confidence <= 0.7:
        depth, tokens = "medium", ("syntax", "type", "test")
    else:
        depth, tokens = "light", ("syntax", "test")
    # 保持配置的原始顺序：命中档位 token 或恒保 token 即入选（显式别名匹配，T-18）
    selected = [s for s in steps
                if (any(_layer_matches(s.get("name", ""), t) for t in tokens)
                    or any(_layer_matches(s.get("name", ""), t) for t in ALWAYS_ON_TOKENS))]
    # 目标测试优先：配置同时含 test-targeted 与 test-full 时，轻/中档只跑 targeted
    #   —— 注意：test-full 不是恒保层，可以被剔除；security 才是（T-17）。
    if any(_layer_matches(s.get("name", ""), "test-targeted") for s in selected):
        selected = [s for s in selected
                    if not _layer_matches(s.get("name", ""), "test-full")]
    if not selected:
        return steps, depth, "no layer matched confidence filter — ran all (fallback)"
    return selected, depth, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic verify gate (layered, diagnostic.v1)")
    ap.add_argument("--config", default="verify.json", help="JSON config with steps or layers")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    ap.add_argument("--tail", type=int, default=12, help="bounded tail lines per step")
    ap.add_argument("--cmd", nargs=argparse.REMAINDER, default=None, help="ad-hoc single step: --cmd pytest -q")
    ap.add_argument("--layers", default=None, help="comma-separated layer-name substrings to run (subset)")
    ap.add_argument("--confidence", type=float, default=None,
                    help="0-1: adaptive verify depth (T-07) — <0.4 all layers / 0.4-0.7 "
                         "syntax+type+targeted / >0.7 syntax+targeted; security 层恒保（T-17，"
                         "任何档位都不剔除安全扫描）。--layers overrides.")
    ap.add_argument("--changed", default=None,
                    help="comma-separated changed source files (T-22): maps to test files "
                         "by convention and appends them to the test-targeted layer cmd; "
                         "no mapping = fail-open (layer runs as configured)")
    ap.add_argument("--cwd", default=None, help="working dir for steps (default: config dir)")
    args = ap.parse_args()

    if args.confidence is not None and not (0.0 <= args.confidence <= 1.0):
        log(f"[fatal] --confidence must be within [0, 1], got {args.confidence}")
        return 2

    cfg_path = Path(args.config).resolve()
    cfg = load_config(cfg_path)
    steps = (cfg or {}).get("steps", [])
    layers = (cfg or {}).get("layers", [])
    short_circuit = bool(cfg.get("short_circuit", True)) if cfg else True

    if args.cmd:
        steps = [{"name": "adhoc", "cmd": args.cmd}]
    elif layers:
        steps = layers

    if not steps:
        reason = "config not found" if cfg is None else "no steps/layers in config"
        log(f"[fatal] {reason}: {cfg_path} (use --cmd or add steps/layers to config)")
        return 2

    if args.layers:
        wanted = [s.strip().lower() for s in args.layers.split(",") if s.strip()]
        steps = [s for s in steps if any(_layer_matches(s.get("name", ""), w) for w in wanted)]
        if not steps:
            log(f"[fatal] no configured steps match --layers {args.layers}")
            return 2

    depth, depth_note = "explicit", None
    if args.confidence is not None:
        if args.layers:
            depth_note = "--layers given — --confidence ignored (explicit declaration wins)"
        else:
            steps, depth, depth_note = select_by_confidence(steps, args.confidence)

    # T-22: --changed -> 约定映射到测试文件，仅注入 test-targeted 层（fail-open）
    test_selection = None
    if args.changed:
        changed = [c.strip() for c in args.changed.split(",") if c.strip()]
        project = Path(args.cwd) if args.cwd else cfg_path.parent
        matched, sel_note = select_targeted_tests(changed, project, cfg)
        test_selection = {"changed_files": changed, "matched_tests": matched,
                          "strategy": "convention", "note": sel_note or None}
        if matched:
            injected = False
            for i, s in enumerate(steps):
                if s.get("name", "") == "test-targeted":
                    ns = dict(s)
                    ns["cmd"] = list(s.get("cmd", [])) + list(matched)
                    steps[i] = ns
                    injected = True
            if not injected:
                test_selection["note"] = (
                    (test_selection["note"] + "; " if test_selection["note"] else "")
                    + "no test-targeted layer in config — selection not applied")

    cwd = args.cwd or (str(cfg_path.parent) if cfg_path.exists() else None)
    rows = []
    stopped_at = None
    for s in steps:
        if not isinstance(s, dict) or "cmd" not in s:
            log(f"[fatal] step {s.get('name') if isinstance(s, dict) else s!r} missing 'cmd'")
            return 2
        row = run_step(s.get("name", "step"), list(s["cmd"]), int(s.get("timeout", 120)), args.tail, cwd)
        # allow_missing: 未安装的可选工具（ruff/mypy/eslint…）不应让闸门失败 —— 否则
        # 随包预设在任何缺工具的机器上都是必然红灯，反而没人用。
        if (not row["ok"] and s.get("allow_missing")
                and row["exit_code"] in (127, 126)):
            row["ok"] = True
            row["skipped"] = "tool not installed (allow_missing)"
            row["error_class"] = None
        # allow_exit_codes: 工具已装但退出码另有语义（pytest 5 = 没有收集到测试，
        # 不是测试失败）。白名单式放行，仍需显式声明。
        allowed = s.get("allow_exit_codes") or []
        if not row["ok"] and row["exit_code"] in allowed:
            row["ok"] = True
            row["skipped"] = f"exit {row['exit_code']} allowed by config"
            row["error_class"] = None
        rows.append(row)
        if not row["ok"]:
            stopped_at = row["name"]
            if short_circuit:
                break
    all_ok = all(r["ok"] for r in rows)
    failures = [r for r in rows if not r["ok"]]
    diagnostics = [{"step": r["name"], "exit_code": r["exit_code"], "error_class": r["error_class"]}
                   for r in failures]

    report = {
        "schema": SCHEMA,
        "time": now_iso(), "config": str(cfg_path), "all_ok": all_ok,
        "short_circuit": short_circuit, "stopped_at": stopped_at,
        "error_class": diagnostics[0]["error_class"] if diagnostics else None,
        "verify_depth": depth,
        "verify_depth_note": depth_note,
        "selected_layers": [r["name"] for r in rows],
        "diagnostics": diagnostics,
        "steps": rows,
    }
    if test_selection is not None:
        report["test_selection"] = test_selection

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            mark = "OK " if r["ok"] else f"!! {r['exit_code']}"
            log(f"  {mark}  {r['name']:<24} {r['duration_ms']:>7}ms  {(' '.join(r['cmd']))[:60]}")
            for ln in r["tail"]:
                log(f"        | {ln[:120]}")
        if stopped_at:
            log(f"  [stop] short-circuit at layer: {stopped_at} (cheapest-first, §12)")
        log(f"  [depth] {depth}"
            + (f" — {depth_note}" if depth_note else "")
            + (f" (confidence={args.confidence})" if args.confidence is not None else ""))
        log(f"Verdict: {'ALL PASS' if all_ok else 'FAILED — see exit codes above'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
