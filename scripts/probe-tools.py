#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe-tools.py — 会话级工具探测单次调用化 (v1.0, 2026-08-22)

Purpose: replace per-session 6+ individual `--version` probe tool-calls with ONE
deterministic call. Agent runs `python scripts/probe-tools.py --json` once per
session; output feeds §6 static tool routing (G3) — probe once, degrade silently.

Design rules (SDK §3/G1-G3, §6):
  * Single source of truth: toolstack.json local_tools manifest (same dir).
  * Python 3.9+ stdlib only. JSON out via --json. Exit 0 always (probe is never fatal).
  * Windows npm shim fallback (.cmd/.exe) — mirrors toolstack-pipeline.py.

Usage:
  python probe-tools.py                # human-readable probe table
  python probe-tools.py --json         # machine-readable JSON (for agent routing)
  python probe-tools.py --group llm    # filter by manifest group (optional)
  python probe-tools.py --write-back   # 探测结果回写 toolstack.json（health/last_checked）
Exit codes: 0 = done (probe results are informational; missing tools are not fatal).

Health write-back (R-4, ResourceOS §19 三态子集):
  schema-4 起每个工具条目带 `health`（active/degraded/unavailable）与 `last_checked`。
  连续 `--degraded-after`（默认 2）次探测失败 → degraded；连续
  `--unavailable-after`（默认 4）次 → unavailable；任一次成功即回 active 并清零连败。
  连败计数存在条目的 `_fail_streak`（运行时台账，非协议字段，selfcheck 不校验）。
  回写是**显式动作**（--write-back）：探测本身保持只读，避免每次会话污染工作区。
  写入走 tmp+replace 原子替换，且内容无变化时不落盘。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST = SCRIPT_DIR / "toolstack.json"

# 降级阈值常量可配（风险矩阵：探测环境抖动不应一次就判死工具）
DEGRADED_AFTER = 2
UNAVAILABLE_AFTER = 4
HEALTH_STATES = ("active", "degraded", "unavailable")


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "command not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def probe_one(name: str, cfg: dict) -> dict:
    cmd = list(cfg["cmd"])
    # Windows: npm shims are extensionless (`ocr`) — CreateProcess needs *.cmd/*.exe.
    candidates = [cmd]
    if os.name == "nt" and "." not in os.path.basename(cmd[0]):
        candidates.append([cmd[0] + ".cmd", *cmd[1:]])
        candidates.append([cmd[0] + ".exe", *cmd[1:]])
    res = None
    for cand in candidates:
        res = run(cand, timeout=int(cfg.get("timeout", 30)))
        if res.returncode != 127:
            break
    ok = res is not None and res.returncode == 0
    ver = None
    if ok and res.stdout.strip():
        if cfg.get("grep"):
            ver = next((ln.strip() for ln in res.stdout.splitlines() if cfg["grep"] in ln), None)
        if ver is None:
            ver = res.stdout.strip().splitlines()[0]
    return {
        "tool": name,
        "group": cfg.get("group", "misc"),
        "ok": ok,
        "version": ver,
        "exit_code": res.returncode if res else None,
        "note": cfg.get("note", ""),
    }


def next_health(entry: dict, ok: bool, degraded_after: int,
                unavailable_after: int) -> tuple[str, int]:
    """三态健康机（§19 DEGRADED→ACTIVE 回边）：成功即清零，连败达阈值逐级降级。"""
    streak = 0 if ok else int(entry.get("_fail_streak", 0) or 0) + 1
    if streak >= unavailable_after:
        return "unavailable", streak
    if streak >= degraded_after:
        return "degraded", streak
    return "active", streak


def write_back(path: Path, manifest: dict, updates: dict[str, dict],
               now: str) -> tuple[bool, str]:
    """原子回写；无变化不落盘。失败不致命（探测脚本绝不应因写盘失败而红）。"""
    if not updates:
        return False, "no change"
    table = manifest.setdefault("local_tools", {})
    for name, patch in updates.items():
        table.setdefault(name, {}).update(patch)
    try:
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".toolstack-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
    except OSError as e:
        return False, f"write-back failed: {type(e).__name__}: {e}"
    return True, f"{len(updates)} updated @ {now}"


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK session tool probe (one call, all tools)")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    ap.add_argument("--group", default=None, help="filter by manifest group (e.g. review/debug/llm)")
    ap.add_argument("--write-back", action="store_true",
                    help="回写 health/last_checked/_fail_streak 到 toolstack.json（默认只读）")
    ap.add_argument("--degraded-after", type=int, default=DEGRADED_AFTER,
                    help=f"连败多少次降级为 degraded（默认 {DEGRADED_AFTER}）")
    ap.add_argument("--unavailable-after", type=int, default=UNAVAILABLE_AFTER,
                    help=f"连败多少次置 unavailable（默认 {UNAVAILABLE_AFTER}）")
    ap.add_argument("--manifest", default=None,
                    help="探测/回写指定 manifest（测试与夹具；默认 scripts/toolstack.json）")
    args = ap.parse_args()

    manifest_path = Path(args.manifest).resolve() if args.manifest else MANIFEST
    if not manifest_path.exists():
        log(json.dumps({"error": f"manifest not found: {manifest_path}"}))
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    local_tools: dict = manifest.get("local_tools", {})
    rows = [probe_one(n, c) for n, c in local_tools.items()
            if not args.group or c.get("group") == args.group]

    # --- R-4 健康态回写 ---
    now = now_iso()
    updates: dict[str, dict] = {}
    health_summary: dict[str, int] = {s: 0 for s in HEALTH_STATES}
    transitions: list[dict] = []
    for r in rows:
        entry = local_tools.get(r["tool"], {})
        health, streak = next_health(entry, bool(r["ok"]),
                                     args.degraded_after, args.unavailable_after)
        r["health"] = health
        r["fail_streak"] = streak
        r["previous_health"] = entry.get("health")
        health_summary[health] = health_summary.get(health, 0) + 1
        if args.write_back and (
                entry.get("health") != health
                or entry.get("last_checked") != now
                or entry.get("_fail_streak") != streak):
            updates[r["tool"]] = {"health": health, "last_checked": now, "_fail_streak": streak}
            if entry.get("health") and entry.get("health") != health:
                transitions.append({"tool": r["tool"], "from": entry.get("health"), "to": health})
    written, write_note = (False, "disabled (no --write-back)")
    if args.write_back:
        written, write_note = write_back(manifest_path, manifest, updates, now)

    if args.json:
        print(json.dumps({
            "time": now,
            "tools": rows,
            "health": health_summary,
            "transitions": transitions,
            "write_back": {"applied": written, "note": write_note,
                           "degraded_after": args.degraded_after,
                           "unavailable_after": args.unavailable_after},
        }, ensure_ascii=False, indent=2))
    else:
        log("== Local tool probes ==")
        for r in rows:
            v = r["version"] or ("—" if r["ok"] else "MISSING")
            log(f"  {'OK ' if r['ok'] else '!! '} {r['tool']:<28} [{r['group']:<8}] {v}"
                f"  health={r['health']}")
        missing = [r["tool"] for r in rows if not r["ok"]]
        if missing:
            log(f"  -> missing (expected or degraded): {', '.join(missing)}")
        log(f"  -> health: {health_summary} | write-back: {write_note}")
        for t in transitions:
            log(f"  -> transition: {t['tool']} {t['from']} -> {t['to']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
