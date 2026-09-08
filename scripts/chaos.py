#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chaos.py — chaos-lite 故障注入与恢复度量（A-9，AOS §11 / §40.6）

Why: `robustness-suite` 测的是**脚本自身容错**（给坏输入，看要不要崩），不是
"Agent 遇故障后能不能恢复"。AOS §11 要的是后者：注入故障 → 观察恢复动作 →
量 RecoveryRate / MTTR，并识别 `blind_retry_pattern`（同一动作重复 3 次无状态变化）。

落地裁剪（单机、无容器）：不注入内核级故障，只注入**环境/输入层**的 5 类：
  tool_unavailable  PATH 置空 —— 依赖的外部命令全部消失
  timeout           强制超时（--timeout-ms）
  corrupt_state     截断/污染目标文件（--target）
  git_conflict      向目标文件写入冲突内容（--target）
  read_only_fs      目标目录置只读（--target，运行后必定恢复）
恢复判定由调用方给 `--recover-cmd`（exit 0 = 恢复成功）；不给则只报故障表现。

Design rules: stdlib only · 只读被测命令之外的东西 · 一切临时改动 finally 还原 ·
exit 0 = 达到 --min-recovery（默认不设，纯报告）/ 2 = 未达标或用法错误。

Usage:
  python scripts/chaos.py list
  python scripts/chaos.py --fault tool_unavailable --cmd "python scripts/version-check.py --json" \\
                          --recover-cmd "python scripts/version-check.py --json"
  python scripts/chaos.py --scenarios scripts/data/chaos-scenarios.json --json
Exit: 0 = report ok / 2 = 低于 --min-recovery 或参数错误
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FAULTS = ("tool_unavailable", "timeout", "corrupt_state", "git_conflict", "read_only_fs")


def run(cmd: list[str], timeout: int | None = None, env: dict | None = None) -> tuple[int, str, int]:
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           env=env or os.environ.copy(), stdin=subprocess.DEVNULL,
                           encoding="utf-8", errors="replace")  # F-73: 子进程 GBK 输出不得炸 reader 线程
        return r.returncode, (r.stdout or "") + (r.stderr or ""), int((time.monotonic() - t0) * 1000)
    except subprocess.TimeoutExpired:
        return 124, "timeout", int((time.monotonic() - t0) * 1000)
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}", int((time.monotonic() - t0) * 1000)


def inject(fault: str, target: Path | None, workdir: Path) -> tuple[dict, callable]:
    """返回 (注入描述, 还原函数)。还原必须无副作用。"""
    if fault == "tool_unavailable":
        empty = workdir / "empty-bin"
        empty.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["PATH"] = str(empty)
        return ({"fault": fault, "detail": "PATH 置空（外部命令不可用）", "env": env},
                lambda: None)
    if fault == "timeout":
        return ({"fault": fault, "detail": "强制超时窗口", "timeout_ms": 1}, lambda: None)
    if fault in ("corrupt_state", "git_conflict", "read_only_fs"):
        if not target:
            raise SystemExit(f"[fatal] fault={fault} 需要 --target")
        if fault == "read_only_fs":
            d = target if target.is_dir() else target.parent
            old = d.stat().st_mode
            os.chmod(d, 0o555)
            return ({"fault": fault, "detail": f"目录置只读 {d}"},
                    (lambda d=d, old=old: os.chmod(d, old)))
        backup = workdir / "target.bak"
        if target.exists():
            shutil.copy2(target, backup)
            had = True
        else:
            had = False
        if fault == "corrupt_state":
            target.write_text("{corrupted", encoding="utf-8")
        else:
            target.write_text((target.read_text(encoding="utf-8") if had else "")
                              + "\n<<<<<<< HEAD\nconflicting edit\n=======\nother\n>>>>>>> other\n",
                              encoding="utf-8")
        def restore(t=target, b=backup, had=had):
            if had and b.exists():
                shutil.copy2(b, t)
            elif not had and t.exists():
                t.unlink()
        return ({"fault": fault, "detail": f"污染 {target.name}"}, restore)
    raise SystemExit(f"[fatal] unknown fault: {fault}")


ARGS_BLIND = False  # 由 main 设置（--check-blind-retry）


def scenario_run(sc: dict, workdir: Path) -> dict:
    fault = sc["fault"]
    cmd = sc["cmd"] if isinstance(sc["cmd"], list) else sc["cmd"].split()
    target = Path(sc["target"]).resolve() if sc.get("target") else None
    info, restore = inject(fault, target, workdir)
    out = {"name": sc.get("name") or fault, "fault": fault, "detail": info["detail"]}
    # F-71: Windows CreateProcess 用父进程 PATH 解析可执行文件，子 env 置空不生效 ——
    # 注入后探测可达性，仍可达则如实标注 fault_effective=false（防 vacuous RecoveryRate），
    # 该场景不计入恢复度量。解析归属：`cmd /c <tool>` 包裹 → cmd 以自身（被注入的）env
    # 解析 → 探测被包裹工具 × 注入后 PATH；直接形式 → Windows 用父 PATH / POSIX exec 用子 env。
    effective = True
    if fault == "tool_unavailable" and cmd:
        probe = cmd[0]
        if probe.lower() == "cmd" and len(cmd) >= 3 and cmd[1].lower() in ("/c", "/k"):
            effective = shutil.which(cmd[2], path=info["env"]["PATH"]) is None
        elif os.name == "nt":
            effective = shutil.which(probe) is None
        else:
            effective = shutil.which(probe, path=info["env"]["PATH"]) is None
        if not effective:
            out["detail"] += "（注入无效：解析层仍可达目标；Windows 下用 cmd /c 包裹可真实触发）"
    out["fault_effective"] = effective
    try:
        env = info.get("env")
        timeout = sc.get("timeout_ms", info.get("timeout_ms"))
        if timeout is not None:
            timeout = timeout / 1000.0  # F-72: 字段名毫秒，subprocess.run 收秒（此前直传，300ms 实为 300s）
        code, text, ms = run(cmd, timeout=timeout, env=env)
        out.update({"fault_exit": code, "duration_ms": ms,
                    "tail": text.strip().splitlines()[-1][:120] if text.strip() else ""})
        # blind_retry_pattern：同一命令连跑 3 次，退出码一致 且 目标文件无变化
        if sc.get("check_blind_retry") or ARGS_BLIND:
            sig = _signature(target)
            repeats = [run(cmd, timeout=timeout, env=env)[0] for _ in range(2)]
            out["blind_retry"] = (repeats[0] == repeats[1] == code
                                  and _signature(target) == sig)
        else:
            out["blind_retry"] = None
        # 恢复
        if sc.get("recover_cmd"):
            rcmd = sc["recover_cmd"] if isinstance(sc["recover_cmd"], list) else sc["recover_cmd"].split()
            rt = sc.get("recover_timeout_ms")
            rcode, _, rms = run(rcmd, timeout=(rt / 1000.0 if rt is not None else None))
            out.update({"recovered": rcode == 0, "mttr_ms": rms})
        else:
            out.update({"recovered": None, "mttr_ms": None})
    finally:
        restore()
    return out


def _signature(target: Path | None) -> str:
    try:
        if target and target.exists() and target.is_file():
            return f"{target.stat().st_size}:{hash(target.read_bytes()) & 0xffff}"
    except OSError:
        pass
    return "na"


def main() -> int:
    ap = argparse.ArgumentParser(description="chaos-lite fault injection & recovery metrics (AOS §11)")
    ap.add_argument("mode", nargs="?", default="run", choices=("run", "list"),
                    help="list = 列出内置故障类；run = 执行（默认）")
    ap.add_argument("--fault", default=None, help=",".join(FAULTS))
    ap.add_argument("--cmd", default=None, help="被测命令（字符串或列表经 --scenarios 给）")
    ap.add_argument("--recover-cmd", default=None, help="恢复命令（exit 0 = 恢复成功）")
    ap.add_argument("--target", default=None, help="fault=corrupt_state/git_conflict/read_only_fs 的目标")
    ap.add_argument("--timeout-ms", type=int, default=None, help="fault=timeout 的超时窗口")
    ap.add_argument("--scenarios", default=None, help="场景清单 JSON（[{name,fault,cmd,recover_cmd,target}]）")
    ap.add_argument("--check-blind-retry", action="store_true",
                    help="检测 blind_retry_pattern（同一命令连跑 3 次、退出码一致且目标无变化）；"
                         "只读命令会假阳性，故默认关闭")
    ap.add_argument("--min-recovery", type=float, default=None,
                    help="RecoveryRate 下限；低于则 exit 2（不设=纯报告）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.mode == "list":
        print(json.dumps({"faults": list(FAULTS)}, ensure_ascii=False, indent=2)
              if args.json else "内置故障类: " + ", ".join(FAULTS))
        return 0

    if args.scenarios:
        try:
            scenarios = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))
            scenarios = scenarios.get("scenarios", scenarios) if isinstance(scenarios, dict) else scenarios
        except (ValueError, OSError) as e:
            print(f"[fatal] unreadable scenarios: {e}", file=sys.stderr)
            return 2
    elif args.fault and args.cmd:
        scenarios = [{"name": args.fault, "fault": args.fault, "cmd": args.cmd,
                      "recover_cmd": args.recover_cmd, "target": args.target,
                      "timeout_ms": args.timeout_ms}]
    else:
        print("[fatal] 需要 --scenarios，或 --fault + --cmd", file=sys.stderr)
        return 2

    global ARGS_BLIND
    ARGS_BLIND = args.check_blind_retry
    bad = [sc.get("fault") for sc in scenarios if sc.get("fault") not in FAULTS]
    if bad:
        print(f"[fatal] unknown fault: {', '.join(str(b) for b in bad)} "
              f"（内置：{', '.join(FAULTS)}）", file=sys.stderr)
        return 2

    results = []
    with tempfile.TemporaryDirectory() as wd:
        for sc in scenarios:
            try:
                results.append(scenario_run(sc, Path(wd)))
            except SystemExit as e:
                results.append({"name": sc.get("name") or sc.get("fault"),
                                "fault": sc.get("fault"), "error": str(e)})

    evaluated = [r for r in results
                 if r.get("recovered") is not None and r.get("fault_effective", True)]
    recovered = sum(1 for r in evaluated if r["recovered"])
    ineffective = [r["name"] for r in results if r.get("fault_effective") is False]
    mttrs = [r["mttr_ms"] for r in evaluated if r["recovered"] and r.get("mttr_ms")]
    blind = [r["name"] for r in results if r.get("blind_retry")]
    rate = (recovered / len(evaluated)) if evaluated else None
    report = {"schema": "chaos.v1", "scenarios": len(results), "evaluated": len(evaluated),
              "recovered": recovered,
              "ineffective_injections": ineffective,
              "recovery_rate": None if rate is None else round(rate, 4),
              "mttr_ms_mean": round(sum(mttrs) / len(mttrs), 1) if mttrs else None,
              "blind_retry_patterns": blind, "results": results}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"== chaos-lite · scenarios={len(results)} ==")
        for r in results:
            if r.get("error"):
                print(f"  !! {r['name']:<22} {r['error'][:60]}")
                continue
            rec = "-" if r["recovered"] is None else ("OK" if r["recovered"] else "FAILED")
            print(f"  {'OK ' if r['recovered'] else '-- '} {r['name']:<22} "
                  f"fault_exit={r.get('fault_exit')} recovery={rec} "
                  f"{'INEFF ' if r.get('fault_effective') is False else ''}"
                  f"{'blind_retry!' if r.get('blind_retry') else ''}")
        print(f"  RecoveryRate: {'-' if rate is None else f'{rate:.0%}'}"
              f"  MTTR: {report['mttr_ms_mean']}ms  blind_retry: {len(blind)}")

    if args.min_recovery is not None and (rate is None or rate < args.min_recovery):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
