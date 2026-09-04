#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ci-smoke.py — 定时冒烟（评估报告 P2-1，ref-23）

One command that runs the FULL deterministic regression stack for the SDK and
writes a dated summary. Intended to run on a schedule (weekly automation) and
before/after any release. Zero-LLM, offline.

Steps (cheapest-first — verification-kernel §B.3 ordering):
  0. version-check (T-16)             — version strings + CHANGELOG order (F-26 gate)
  1. robustness-suite (full, 51+ cases)
  2. golden-run --validate-set (v2, v3)   — accept-rule pre-check (zero LLM)
  3. golden-run --offline v3              — 32/32 structural judging (zero LLM)
  4. privacy-scan SDK dir                 — leak gate for new content
Exit: 0 = all green / 2 = any failure. Summary JSON via --json or --report <path>.

Usage:
  python ci-smoke.py
  python ci-smoke.py --json
  python ci-smoke.py --report <REPORT_PATH>/smoke-2026-08-26.json
  python ci-smoke.py --skip-privacy       # slow environments
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SDK_DIR = SCRIPT_DIR.parent


def sanitize_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # sandbox shim (E1)
    return env


def run(cmd: list, timeout: int = 600) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=sanitize_env(), stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 127, f"{type(e).__name__}: {e}"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# --- R-5: 步骤清单 manifest 化（ResourceOS §17 依赖图 / §22 组合） --------------
# 七步 cheapest-first 原先硬编码在 main() 里：加一步要改代码，且"version-check
# 是第 0 步"这条约定没有数据落点。抽出后 ci-smoke 退化为薄 runner。
STEPS_FILE = SCRIPT_DIR / "data" / "ci-steps.json"


def expand_arg(token: str) -> str:
    """@data/<file> → scripts/data/<file>；@sdk → SDK 根目录；其余原样。"""
    if token == "@sdk":
        return str(SDK_DIR)
    if token.startswith("@data/"):
        return str(SCRIPT_DIR / token[1:])
    return token


def load_steps(path: Path, args: argparse.Namespace) -> list[tuple[str, list[str], int]] | None:
    """读 manifest → [(name, cmd, timeout)]。不可用返回 None（调用方 fail-closed）。"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    out: list[tuple[str, list[str], int]] = []
    for st in data.get("steps", []):
        flag = st.get("skip_flag")
        # 只认布尔开关，且必须是 argparse 已声明的项（防止 manifest 凭空造开关）
        if flag and flag in vars(args) and isinstance(vars(args)[flag], bool) and vars(args)[flag]:
            continue
        script = SCRIPT_DIR / st["script"]
        if not script.exists():
            return None
        out.append((st["name"],
                    [sys.executable, str(script), *[expand_arg(a) for a in st.get("args", [])]],
                    int(st.get("timeout", 120))))
    return out or None


def tool_health() -> dict[str, int]:
    """R-4: 汇总 toolstack.json 的 health 三态。读不到就返回空 dict（不阻塞冒烟）。"""
    p = SCRIPT_DIR / "toolstack.json"
    summary: dict[str, int] = {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return summary
    for tbl in ("sdk_tools", "local_tools"):
        for meta in (data.get(tbl) or {}).values():
            h = meta.get("health") or "unknown"
            summary[h] = summary.get(h, 0) + 1
    return summary


# --- F-63: --report 保留策略（data/ 目录不逐日堆积）---------------------------
# 只匹配 `<前缀>-YYYY-MM-DD` 结尾的文件名（日期必须收尾，`foo-2026-09-01-extra`
# 这类不碰）；同前缀视为一族，保留文件名序（即日期序）最后 KEEP 份。
REPORT_KEEP = 7
_DATE_STEM = re.compile(r"^(.+)-(\d{4}-\d{2}-\d{2})$")


def prune_old_reports(p: Path, keep: int = REPORT_KEEP) -> list[str]:
    """写完新报告后清理同前缀带日期旧报告，返回被删文件名列表。永不抛错。"""
    m = _DATE_STEM.match(p.stem)
    if not m:
        return []
    prefix = m.group(1)
    sibs: list[Path] = []
    for q in p.parent.glob(f"{prefix}-*.json"):
        qm = _DATE_STEM.match(q.stem)
        if qm and qm.group(1) == prefix:
            sibs.append(q)
    sibs.sort()
    removed: list[str] = []
    for q in sibs[:-keep] if len(sibs) > keep else []:
        try:
            q.unlink()
            removed.append(q.name)
        except OSError:
            pass
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK scheduled smoke test (robustness+golden+privacy)")
    ap.add_argument("--json", action="store_true", help="summary JSON to stdout")
    ap.add_argument("--report", default=None, help="write summary JSON to a dated file")
    ap.add_argument("--skip-privacy", action="store_true", help="skip privacy-scan step")
    ap.add_argument("--steps", default=None,
                    help="步骤清单 manifest（默认 scripts/data/ci-steps.json，R-5）")
    args = ap.parse_args()

    def echo(msg: str) -> None:
        """Progress line: stderr when --json (stdout stays pure JSON), else stdout."""
        print(msg, file=sys.stderr if args.json else sys.stdout, flush=True)

    steps = load_steps(Path(args.steps) if args.steps else STEPS_FILE, args)
    if steps is None:
        echo(f"ci-smoke: FATAL — 步骤清单不可用：{args.steps or STEPS_FILE}")
        return 2

    results = []
    for name, cmd, timeout in steps:
        code, out = run(cmd, timeout=timeout)
        ok = code == 0
        # extract a compact verdict line from JSON payloads
        detail = ""
        try:
            data = json.loads(out[out.index("{"):])
            if "pass_rate" in data:
                detail = f"pass_rate={data['pass_rate']}"
                if not ok:  # F-55：失败时必须点名失败用例，否则红灯不可归因（v2.10.5 第 6 轮自检实录）
                    bad = [c.get("name", "?") for c in (data.get("results") or [])
                           if not c.get("ok", True)][:5]
                    if bad:
                        detail += " failed=" + "; ".join(bad)[:160]
            elif "valid" in data:
                detail = f"valid={data['valid']}"
            elif "changelog_top" in data:
                detail = (f"consistent={data.get('ok')} top={data.get('changelog_top')}"
                          + (f" problems={len(data['problems'])}" if data.get("problems") else ""))
            elif "clean" in data:
                detail = f"clean={data['clean']} findings={data.get('total')}"
        except (ValueError, IndexError, json.JSONDecodeError):
            detail = out.strip().splitlines()[-1][:80] if out.strip() else "no output"
        results.append({"step": name, "ok": ok, "exit": code, "detail": detail})
        # v2.10.1 (F-45): --json must emit parseable JSON on stdout only —
        # progress lines go to stderr, otherwise `ci-smoke --json | jq` breaks.
        echo(f"  [{'OK ' if ok else '!! '}] {name:<22} exit={code} {detail}")

    all_ok = all(r["ok"] for r in results)
    summary = {"schema": "ci-smoke.v1", "time": now_iso(), "all_ok": all_ok, "steps": results,
               # R-4：工具健康概览（schema-4 health 三态汇总）。只读、永不阻塞 ——
               # 探测回写是显式动作，这里只把现状摆到报告里，供下轮决策看。
               "tool_health": tool_health()}
    if summary["tool_health"]:
        echo("  [health] " + " ".join(f"{k}={v}" for k, v in sorted(summary["tool_health"].items())))

    if args.report:
        p = Path(args.report)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        pruned = prune_old_reports(p)
        msg = f"  [report] {p}"
        if pruned:
            msg += f"  [retention] pruned {len(pruned)} (keep={REPORT_KEEP}): {', '.join(pruned)}"
        if args.json:
            print(msg, file=sys.stderr, flush=True)
        else:
            print(msg, flush=True)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    echo(f"ci-smoke: {'ALL GREEN' if all_ok else 'FAILURES — see steps above'}")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
