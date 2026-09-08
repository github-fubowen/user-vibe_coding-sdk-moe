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
import hashlib
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


# --- A-5: 验收契约（AOS §24 / §4.2，v2.11.0）---------------------------------
# 闸集 / 版本 / 金标集 hash 必须与契约一致，否则"绿"不可信：改了闸门而不改契约、
# 或改了金标集而不重签，都视为判定失据 → fail-closed（exit 2）。
# 与 privacy-scan 不同：契约没有 skip 开关 —— 可跳过扫描，不可跳过"依据什么判定"。
CONTRACT_FILE = SCRIPT_DIR / "data" / "acceptance-contract.v1.json"
CHANGELOG = SDK_DIR / "CHANGELOG.md"
_VER_RE = re.compile(r"^##\s+(v\d+\.\d+\.\d+)", re.M)


def _sha256_file(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


def contract_check(executed: list[str], custom_manifest: bool = False,
                   contract_path: Path | None = None) -> dict:
    """比对验收契约。返回 {applied, contract_hash, match, problems[]}。永不抛错。

    custom_manifest=True（显式 --steps 指向别处）时**不套用契约**：那是一次临时/局部运行，
    不是验收声明 —— 否则"跑 1 步看看"也会被判缺失 7 个闸（v2.11.0 实测：F-63 保留策略
    用例用单步清单跑 ci-smoke，被契约闸误判为 REGRESSION）。原则：契约管**验收运行**，
    不管临时运行；但临时运行的报告必须写明 `applied=false`，不得冒充满绿验收。
    """
    # 显式 --contract：即使清单是自定义的，也是一次验收运行，必须套用契约
    applied = (not custom_manifest) or (contract_path is not None)
    out = {"applied": applied, "contract_hash": None, "match": None, "problems": []}
    cf = contract_path or CONTRACT_FILE
    if not cf.exists():
        out["problems"].append(f"missing contract: {cf.name}")
        out["match"] = False
        return out
    try:
        c = json.loads(cf.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        out["problems"].append(f"unreadable contract: {e}")
        out["match"] = False
        return out

    out["contract_hash"] = hashlib.sha256(
        json.dumps(c, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    if not applied:
        return out
    out["match"] = False

    # 0) 步骤清单：默认清单必须与契约登记的一致（改闸不重签 = 判定失据）
    sm = c.get("steps_manifest") or {}
    if sm.get("path"):
        p = SCRIPT_DIR / sm["path"]
        if not p.exists():
            out["problems"].append(f"steps manifest missing: {sm['path']}")
        elif sm.get("sha256") and _sha256_file(p) != sm["sha256"]:
            out["problems"].append("steps manifest sha256 drift (改闸需重签契约)")

    # 1) 版本：契约声明的 sdk_version 必须等于 CHANGELOG 顶部版本（T-16 同源自洽）
    top = ""
    try:
        m = _VER_RE.search(CHANGELOG.read_text(encoding="utf-8"))
        top = m.group(1) if m else ""
    except OSError:
        pass
    if c.get("sdk_version") != top:
        out["problems"].append(f"version drift: contract={c.get('sdk_version')} changelog_top={top or '?'}")

    # 2) 闸集：强制闸必须全部执行；不得出现契约外的闸
    gates = list(c.get("gate_set") or [])
    optional = list(c.get("optional_gates") or [])
    missing = [g for g in gates if g not in executed]
    extra = [e for e in executed if e not in gates and e not in optional]
    if missing:
        out["problems"].append("gate_set missing: " + ", ".join(missing))
    if extra:
        out["problems"].append("gate_set unexpected: " + ", ".join(extra))

    # 3) 套件：金标集 sha256 / 样本数漂移（防"放宽 accept 规则后仍自称同一套件"）
    for name, meta in (c.get("suite_manifest", {}).get("golden_sets") or {}).items():
        p = SCRIPT_DIR / (meta.get("path") or "")
        if not p.exists():
            out["problems"].append(f"suite {name}: file missing ({meta.get('path')})")
            continue
        h = _sha256_file(p)
        if meta.get("sha256") and h != meta["sha256"]:
            out["problems"].append(f"suite {name}: sha256 drift (contract={str(meta['sha256'])[:12]}… actual={h[:12]}…)")
        try:
            n = len(json.loads(p.read_text(encoding="utf-8")).get("samples") or [])
        except (ValueError, OSError):
            n = -1
        if meta.get("count") is not None and n != meta["count"]:
            out["problems"].append(f"suite {name}: count drift (contract={meta['count']} actual={n})")

    out["match"] = not out["problems"]
    return out


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
    ap.add_argument("--contract", default=None,
                    help="A-5：显式指定验收契约（显式给出时**即使自定义清单也套用契约**——"
                         "显式契约 = 这是一次验收运行，不是临时跑跑）")
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

    # A-5：验收契约比对（闸集/版本/套件 hash）—— 失配即 fail-closed
    acc = contract_check([r["step"] for r in results],
                         custom_manifest=args.steps is not None,
                         contract_path=Path(args.contract) if args.contract else None)
    contract_ok = acc["match"] is not False
    all_ok = all(r["ok"] for r in results) and contract_ok
    summary = {"schema": "ci-smoke.v1", "time": now_iso(), "all_ok": all_ok, "steps": results,
               "acceptance": acc,
               # R-4：工具健康概览（schema-4 health 三态汇总）。只读、永不阻塞 ——
               # 探测回写是显式动作，这里只把现状摆到报告里，供下轮决策看。
               "tool_health": tool_health()}
    if summary["tool_health"]:
        echo("  [health] " + " ".join(f"{k}={v}" for k, v in sorted(summary["tool_health"].items())))
    # 契约行永远打印（绿也要看得见 hash，便于跨机比对"是不是同一套判定依据"）
    if not acc["applied"]:
        echo(f"  [-- ] {'acceptance-contract':<22} hash={acc['contract_hash'] or '-'} "
             f"skipped — 自定义步骤清单，非验收运行（不得据此声明通过）")
    else:
        echo(f"  [{'OK ' if contract_ok else '!! '}] {'acceptance-contract':<22} "
             f"hash={acc['contract_hash'] or '-'} "
             + ("match" if contract_ok else "DRIFT — " + "; ".join(acc["problems"])[:200]))

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
