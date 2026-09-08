#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git-pre-commit.py — SDK 提交前门禁（评估报告 P0-1，ref-23）

Installed by install-hooks.py as `.git/hooks/pre-commit`. Purpose: make the
regression + privacy gates STRUCTURAL instead of discipline-based (评估报告
缺口：门禁未结构化 → L2）。Fail-closed: any gate failure blocks the commit.

Gates (deterministic, zero-LLM, seconds):
  1. Staged changes under `<sdk>/scripts/*.py`
     -> robustness-suite --only <changed-script> (subset, fast)
  2. Staged data files (`<sdk>/scripts/data/*.json` or golden-set-*/baseline-*)
     -> JSON validity + golden `--validate-set` for golden sets (F3, C0-4)
  3. Staged NEW files under the SDK dir -> privacy-scan (leak gate)
  4. ANY staged change under the SDK dir -> selfcheck-static (v2.10.2, ~1s):
     frontmatter / references / script existence / toolstack consistency.
     Closes the F-43 blind spot: a new script that was never registered in
     toolstack.json `sdk_tools` now blocks the commit instead of silently
     drifting until the next ci-smoke.
  5. Docs-only / non-SDK commits -> instant pass (skip)

Environment hardening:
  * Pops PYTHONPATH before spawning children (WorkBuddy sandbox shim breaks
    python subprocesses — see workspace test report E1).
  * Fail-closed: suite crash / timeout -> block (exit 1).
  * SDK_RELPATH is derived at runtime from this file's own location (F2, C0-2):
    renaming the SDK directory cannot silently bypass the gate.

Test / debug (no git needed):
  python git-pre-commit.py --dry-run --changed user-vibe_coding-sdk-moe/scripts/token-meter.py
  python git-pre-commit.py --dry-run --changed README.md        # docs-only -> skip
  python git-pre-commit.py --dry-run --changed scripts/data/baseline-tmp.json  # data gate
Exit codes: 0 = pass / 1 = blocked (gate failure).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# SDK dir = parent of scripts dir; repo-relative prefix is derived at runtime (F2).
SDK_DIR = SCRIPT_DIR.parent
DATA_PREFIXES = ("golden-set-", "baseline-")
# A-14：验收依据文件（改动需显式放行）—— 放宽其中任何一个都能让红灯自证为绿
ACCEPTANCE_CRITICAL = (
    "golden-set-*.json", "acceptance-contract.v1.json", "acceptance-weights.v1.json",
    "ci-steps.json", "mutation-audit.py", "ci-smoke.py", "accept-score.py",
)


def resolve_sdk_relpath(repo_top: str | None) -> str:
    """F2: derive the SDK's repo-relative prefix instead of hardcoding it.

    Real-hook mode (repo_top known): true relative path inside the repo.
    Dry-run mode (repo_top None): directory basename — still correct for any
    SDK dir name, so a renamed directory keeps the gate attached.
    """
    if repo_top:
        try:
            return str(SDK_DIR.resolve().relative_to(Path(repo_top).resolve()))
        except ValueError:
            pass
    return SDK_DIR.name


def resolve_changed_path(rel: str, repo_top: str | None) -> Path:
    """Locate a staged path: absolute as-is, else cwd-relative if present,
    else repo-top-relative (git contract: hook runs with cwd = repo top)."""
    p = Path(rel)
    if p.is_absolute():
        return p
    cwd_candidate = Path.cwd() / p
    if cwd_candidate.exists():
        return cwd_candidate
    if repo_top:
        return Path(repo_top) / p
    return p


def is_data_file(rel: str, rel_prefix: str) -> bool:
    """Data gate scope (F3, C0-4): SDK data-dir JSON or golden-set/baseline files."""
    if not rel.endswith(".json"):
        return False
    if rel.startswith(rel_prefix + "/scripts/data/"):
        return True
    return any(Path(rel).name.startswith(p) for p in DATA_PREFIXES)


def validate_data_file(rel: str, target: Path, env: dict) -> tuple[bool, str]:
    """JSON validity (fail-closed) + golden --validate-set for golden sets."""
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False, "file not found"
    except Exception as e:
        return False, f"read error: {type(e).__name__}: {e}"
    try:
        json.loads(text)
    except Exception as e:
        return False, f"invalid JSON: {type(e).__name__}: {e}"
    if Path(rel).name.startswith("golden-set-"):
        code, out = run([sys.executable, str(SCRIPT_DIR / "golden-run.py"),
                         "--set", str(target), "--validate-set"], env, timeout=120)
        if code != 0 or "VALID" not in out:
            return False, "golden --validate-set failed"
    return True, "valid"


def sanitize_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # sandbox shim interference (E1)
    # git internal vars must NOT leak into child git calls (worktree add / init in
    # throwaway suite fixtures): during a real commit git sets GIT_INDEX_FILE to a
    # temporary index — inherited, it makes child `git worktree add` fail.
    for k in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
              "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"):
        env.pop(k, None)
    return env


def run(cmd: list, env: dict, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=env, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 127, f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK pre-commit gate (robustness subset + privacy)")
    ap.add_argument("--dry-run", action="store_true", help="print plan and run checks (testing)")
    ap.add_argument("--changed", action="append", default=[], help="simulate staged changed paths")
    ap.add_argument("--new", action="append", default=[], help="simulate staged new paths")
    ap.add_argument("--allow-integrity", action="store_true",
                    help="A-14：显式放行「验收依据文件」的改动（golden 集/契约/权重/步骤清单/闸脚本），"
                         "不放行即拒绝提交 —— 改判定标准必须留痕；"
                         "真实 hook 模式下用环境变量 SDK_ALLOW_INTEGRITY=1（git 不向 hook 传参，F-74）")
    args = ap.parse_args()
    # F-74: --allow-integrity 只在手动/dry-run 模式可达（git 不给 pre-commit hook 传参）——
    # 契约重签等合法改动在真实 hook 下无逃逸通道，只能 --no-verify（违反 §10）。
    # 补一条环境变量通道：SDK_ALLOW_INTEGRITY=1 git commit ...；默认仍 fail-closed。
    allow_integrity = args.allow_integrity or os.environ.get("SDK_ALLOW_INTEGRITY") == "1"
    env = sanitize_env()

    if args.changed or args.new:
        changed, new = args.changed, args.new
        repo_top = None
    else:
        code, out = run(["git", "rev-parse", "--show-toplevel"], env, timeout=15)
        if code != 0:
            print("pre-commit gate: not a git repo — skip (nothing to gate)", flush=True)
            return 0
        repo_top = out.strip()
        code, out = run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], env, timeout=30)
        changed = [ln for ln in out.splitlines() if ln.strip()]
        code, out = run(["git", "diff", "--cached", "--name-only", "--diff-filter=A"], env, timeout=30)
        new = [ln for ln in out.splitlines() if ln.strip()]

    rel = resolve_sdk_relpath(repo_top)  # F2: runtime-derived, renamed-dir safe
    sdk_scripts = [c for c in changed if c.startswith(rel + "/scripts/") and c.endswith(".py")]
    sdk_new = [n for n in new if n.startswith(rel + "/")]
    data_files = [c for c in changed if is_data_file(c, rel)]
    # F-41（v2.10.0 治本）：SDK 内**文档**同样进 privacy 规则面 —— ALIGNMENT/CHANGELOG
    # 自引盘符路径两次漏网（F-25 → F-41），根因是"docs-only 跳过"把整个 privacy 闸跳掉了。
    sdk_docs = [c for c in changed
                if c.startswith(rel + "/") and c not in sdk_scripts and c not in data_files]
    if not sdk_scripts and not sdk_new and not data_files and not sdk_docs:
        print("pre-commit gate: docs-only / non-SDK change — skip", flush=True)
        return 0

    print(f"pre-commit gate: {len(sdk_scripts)} script(s), {len(data_files)} data file(s), "
          f"{len(sdk_docs)} doc(s), {len(sdk_new)} new file(s) under SDK", flush=True)
    problems: list[str] = []

    for rel_script in sdk_scripts:
        stem = Path(rel_script).stem
        code, out = run([sys.executable, str(SCRIPT_DIR / "robustness-suite.py"),
                         "--only", stem, "--json"], env, timeout=180)
        ok = code == 0
        if ok:
            try:  # accept 0/0 (no coverage for this script) — nothing to regress
                data = json.loads(out[out.index("{"):])
                ok = data.get("passed", 0) == data.get("total", 0)
            except (ValueError, json.JSONDecodeError):
                ok = False
        status = "OK" if ok else f"BLOCKED (exit {code})"
        print(f"  [gate] robustness subset  {stem:<22} {status}", flush=True)
        if not ok:
            problems.append(f"robustness gate failed for {Path(rel_script).name}")

    for df in data_files:
        target = resolve_changed_path(df, repo_top)
        ok, msg = validate_data_file(df, target, env)
        status = "OK" if ok else f"BLOCKED ({msg})"
        print(f"  [gate] data-file          {Path(df).name:<22} {status}", flush=True)
        if not ok:
            problems.append(f"data-file gate failed for {df}: {msg}")

    if sdk_new or sdk_docs:
        code, out = run([sys.executable, str(SCRIPT_DIR / "privacy-scan.py"),
                         str(SCRIPT_DIR.parent), "--json"], env, timeout=180)
        ok = code == 0
        print(f"  [gate] privacy-scan       {'OK' if ok else 'BLOCKED (leak found)'}", flush=True)
        if not ok:
            scope = "staged new files" if sdk_new else "staged docs (F-41: docs carry paths too)"
            problems.append(f"privacy-scan blocked: machine-specific content in {scope}")

    # v2.10.2 (F-43 治本之提交时刻): structural self-check. ~1s, zero-LLM.
    # Runs for ANY staged SDK change — the gate that was missing is the one that
    # would have caught 5 unregistered scripts (v2.8.2~v2.10.0) at commit time
    # instead of surfacing them a month later in a self-check round.
    # NOTE: no --quiet — stdout JSON is parsed below to report the concrete drift.
    # Degrades (instead of blocking) when the tree is not a complete SDK checkout:
    # the C0-2 renamed-dir fixture copies only 5 scripts, and a partial checkout has
    # no manifest to diff against — §6 rule: unavailable -> next in chain, never block.
    if not (SCRIPT_DIR / "toolstack.json").exists() or not (SDK_DIR / "SKILL.md").exists():
        print("  [gate] selfcheck-static   SKIPPED (incomplete SDK tree — no manifest to diff)",
              flush=True)
    else:
        code, out = run([sys.executable, str(SCRIPT_DIR / "selfcheck-static.py")],
                        env, timeout=120)
        ok = code == 0
        print(f"  [gate] selfcheck-static   {'OK' if ok else 'BLOCKED (structure drift)'}",
              flush=True)
        if not ok:
            try:  # surface the concrete drift, not just the exit code
                data = json.loads(out[out.index("{"):])
                detail = "; ".join(data.get("problems", []))
            except (ValueError, json.JSONDecodeError):
                detail = out.strip()[:200]
            problems.append(f"selfcheck-static blocked: {detail or 'structure drift'}")

    # --- A-14（v2.11.2，AOS §15 工作区完整性）：验收依据文件改动必须显式放行 ---
    # 这些文件被静默放宽 = 绿灯可以自证（F-50 的上游形态）：golden accept 规则、
    # 验收契约、权重表、步骤清单、用例声明、变异锚点。改它们不是禁止，而是**必须
    # 显式 --allow-integrity 并留痕**（与 tier-4 push 门同一哲学：结构性强迫声明）。
    # 只管 **SDK 自己的**验收依据文件（临时目录里的同名 fixture 不算 —— 否则会误伤
    # 既有用例，也会把别人的同名文件拖进闸里）
    hits = [c for c in changed
            if c.startswith(rel + "/")
            and any(fnmatch.fnmatch(Path(c).name, pat) for pat in ACCEPTANCE_CRITICAL)]
    if hits:
        if allow_integrity:
            print(f"  [gate] workspace-integrity  ALLOWED({'--allow-integrity' if args.allow_integrity else 'env SDK_ALLOW_INTEGRITY=1'}) "
                  f"{len(hits)} file(s): " + ", ".join(Path(h).name for h in hits[:5]),
                  flush=True)
        else:
            print("  [gate] workspace-integrity  BLOCKED — 验收依据文件被改动："
                  + ", ".join(Path(h).name for h in hits[:5])
                  + "  （确认是有意变更则加 --allow-integrity 重跑，改动随即留痕）",
                  flush=True)
            problems.append("workspace-integrity: acceptance-critical files changed "
                            "without --allow-integrity: "
                            + ", ".join(Path(h).name for h in hits[:3]))

    if args.dry_run:
        print("  (dry-run — no commit affected)", flush=True)
    if problems:
        print("pre-commit gate: BLOCKED — " + "; ".join(problems), file=sys.stderr, flush=True)
        return 1
    print("pre-commit gate: PASS", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
