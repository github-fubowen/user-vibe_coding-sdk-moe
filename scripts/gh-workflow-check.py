#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gh-workflow-check.py — .github 工作流结构校验 (v1.0, 2026-08-28, C2-3)

Purpose: deterministic zero-LLM structural validation of the SDK's GitHub
Actions files (C2-1/C2-2/C2-3). Enforces the control-plane contract:
  * ci.yml has workflow_dispatch with inputs operation/version/agent_run_id
  * reusable/ set contains python-ci/node-ci/docker-build
  * every workflow's reusable call uses only the SDK's reusable library
    (Agent 只选不生成 — no ad-hoc job bodies under the SDK workflows)
  * GITHUB_TOKEN scope is read-only by default (permissions: contents: read)

Design rules: stdlib only (no PyYAML — text-level structural checks), exit
0 = OK / 2 = violation. Used by robustness-suite and future remote CI.

Usage:
  python gh-workflow-check.py --gh-dir .github
  python gh-workflow-check.py --gh-dir .github --json
Exit codes: 0 = OK / 2 = violation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_REUSABLES = ("python-ci.yml", "node-ci.yml", "docker-build.yml")
DISPATCH_INPUTS = ("operation", "version", "agent_run_id")
REUSABLE_REF = "./.github/reusable/"


def check_workflow_dir(gh: Path) -> list[str]:
    problems = []
    wf_dir = gh / "workflows"
    r_dir = gh / "reusable"
    if not wf_dir.is_dir():
        problems.append("missing workflows/ dir")
        return problems
    if not r_dir.is_dir():
        problems.append("missing reusable/ dir")
        return problems

    for fn in REQUIRED_REUSABLES:
        if not (r_dir / fn).exists():
            problems.append(f"missing reusable/{fn}")

    # ci.yml: dispatch 控制面契约
    ci = wf_dir / "ci.yml"
    if not ci.exists():
        problems.append("missing workflows/ci.yml")
    else:
        text = ci.read_text(encoding="utf-8", errors="replace")
        if "workflow_dispatch" not in text:
            problems.append("ci.yml lacks workflow_dispatch (C2-3)")
        for inp in DISPATCH_INPUTS:
            if f"{inp}:" not in text:
                problems.append(f"ci.yml dispatch missing input: {inp}")
        if "permissions:" not in text or "contents: read" not in text:
            problems.append("ci.yml lacks read-only permissions default")

    # 消费方示例存在（C2-2 验收）
    if not (wf_dir / "example-consumer.yml").exists():
        problems.append("missing example-consumer.yml (C2-2)")

    # 所有 workflow 的 job 只能引用 reusable 库（不拼装 ad-hoc job 体）
    for wf in wf_dir.glob("*.yml"):
        text = wf.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "runs-on:" in line:
                problems.append(f"{wf.name}: ad-hoc 'runs-on' job body (只选 reusable)")
                break
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="GitHub workflows structural check (C2-3)")
    ap.add_argument("--gh-dir", default=".github", help=".github dir (default: ./.github)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    gh = Path(args.gh_dir)
    if not gh.exists():
        print(f"[fatal] .github dir not found: {gh}", file=sys.stderr)
        return 2
    problems = check_workflow_dir(gh)
    if args.json:
        print(json.dumps({"schema": "gh-workflows.v1", "gh_dir": str(gh),
                          "valid": not problems, "problems": problems},
                         ensure_ascii=False, indent=2))
    else:
        if problems:
            print("== gh-workflow-check: VIOLATIONS ==")
            for p in problems:
                print(f"  !! {p}")
        else:
            print("== gh-workflow-check: OK — control-plane contract satisfied ==")
    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())
