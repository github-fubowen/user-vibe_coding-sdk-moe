#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robustness-suite.py — SDK 鲁棒性回归套件 (v1.0, 2026-08-22)

Purpose: freeze the robustness audit's 20 fault-injection cases into a
deterministic regression suite (ref-19 建议 #2). Run after ANY script change:
`python scripts/robustness-suite.py` — exit 0 = all green, 2 = regression.

Design rules (SDK §3/G-gates, robustness-audit-2026-08-22):
  * Python 3.9+ stdlib only. JSON out via --json. Exit 0/2 (对齐 0/2 约定).
  * Each case = subprocess invocation with expected exit code + marker checks
    (must-contain / must-not-contain "Traceback").
  * Fixtures (bad JSON / bad regex set / empty set / missing store) built in
    a temp dir; NEVER touches the SDK repo or network (all offline cases).

Usage:
  python robustness-suite.py                # human PASS/FAIL table
  python robustness-suite.py --json         # machine-readable
  python robustness-suite.py --only golden-run  # filter by script name substring
Exit codes: 0 = all cases pass / 2 = at least one regression (or suite error).
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
PY = sys.executable

BAD_JSON = "{bad json"
BAD_REGEX_SET = '{"samples":[{"id":"x","task_type":"qa","prompt":"p","accept":[{"type":"regex","pattern":"["}]}]}'
EMPTY_SET = '{"samples":[]}'
ONE_SET_NO_ACCEPT = '{"samples":[{"id":"a","task_type":"qa","prompt":"p"}]}'
ONE_SET_OK = '{"samples":[{"id":"a","task_type":"qa","prompt":"1+1","accept":[{"type":"contains","text":"2"}],"response":"2"}]}'
GARBAGE_LOG = "not json at all\n{\"partial\": true\nmore garbage\n"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run_case(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    """Run a case; returns (exit_code, combined_output). Never raises."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             stdin=subprocess.DEVNULL)
        out = (res.stdout or "") + (res.stderr or "")
        return res.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 127, f"suite error: {type(e).__name__}: {e}"


def build_cases(tmp: Path) -> list[dict]:
    """Build the 20-case matrix. Returns [{name, script, args, expect, want, dont}]."""
    (tmp / "bad.json").write_text(BAD_JSON, encoding="utf-8")
    (tmp / "badregex.json").write_text(BAD_REGEX_SET, encoding="utf-8")
    (tmp / "empty.json").write_text(EMPTY_SET, encoding="utf-8")
    (tmp / "noaccept.json").write_text(ONE_SET_NO_ACCEPT, encoding="utf-8")
    (tmp / "ok.json").write_text(ONE_SET_OK, encoding="utf-8")
    (tmp / "garbage.jsonl").write_text(GARBAGE_LOG, encoding="utf-8")
    (tmp / "empty.log").write_text("", encoding="utf-8")

    # privacy-scan fixtures (v1.16.0)
    (tmp / "clean").mkdir()
    (tmp / "clean" / "ok.txt").write_text("hello world\n", encoding="utf-8")
    (tmp / "leak").mkdir()
    (tmp / "leak" / "secret.txt").write_text(
        'key = "sk-TEST-abcdefghijklmnopqrstuvwxyz"\npath = "C:\\\\Users\\\\alice\\\\x"\n',  # TEST fixture: fake key + fake path
        encoding="utf-8")

    # probe-tools "missing manifest" needs an isolated copy (its manifest lives in scripts/)
    isolated = tmp / "isolated"
    isolated.mkdir()
    (isolated / "probe-tools.py").write_text(
        (SCRIPT_DIR / "probe-tools.py").read_text(encoding="utf-8"), encoding="utf-8")

    def C(name, script, args, expect, want=(), dont=("Traceback",), expect_any=()):
        return {"name": name, "script": script,
                "cmd": [PY, str(SCRIPT_DIR / script), *[str(a) for a in args]],
                "expect": expect, "expect_any": tuple(expect_any),
                "want": want, "dont": dont}

    return [
        # --- golden-run: universal boundaries ---
        C("golden-run: --help", "golden-run.py", ["--help"], 0, want=("usage",)),
        C("golden-run: missing --set", "golden-run.py", [], 2, want=("required",)),
        C("golden-run: nonexistent set", "golden-run.py", ["--set", tmp / "nope.json"], 2, want=("not found",)),
        C("golden-run: empty samples", "golden-run.py", ["--set", tmp / "empty.json"], 2, want=("no samples",)),
        # --- golden-run: validate-set pre-check (v1.15.0) ---
        C("golden-run: validate-set bad regex", "golden-run.py",
          ["--set", tmp / "badregex.json", "--validate-set"], 2, want=("regex compile failed",)),
        C("golden-run: validate-set ok set", "golden-run.py",
          ["--set", tmp / "ok.json", "--validate-set"], 0, want=("VALID",)),
        # --- golden-run: adversarial judging ---
        C("golden-run: bad regex offline judge", "golden-run.py",
          ["--set", tmp / "badregex.json", "--offline"], 2, want=("bad accept rule",)),
        C("golden-run: no accept key", "golden-run.py", ["--set", tmp / "noaccept.json", "--offline"], 2,
          want=("no accept rules",)),
        C("golden-run: LLM conn refused", "golden-run.py",
          ["--set", tmp / "ok.json", "--llm-url", "http://localhost:1/v1", "--timeout", "3"], 2,
          want=("LLM call failed",)),
        # --- verify-runner ---
        C("verify-runner: bad JSON config", "verify-runner.py", ["--config", tmp / "bad.json"], 2,
          want=("invalid JSON",)),
        C("verify-runner: cmd not found", "verify-runner.py",
          ["--json", "--cmd", "definitely-not-a-real-cmd-xyz"], 2, want=("exit_code", "127")),
        C("verify-runner: passing cmd", "verify-runner.py",
          ["--cmd", PY, "-c", "print('ok')"], 0, want=("ALL PASS",)),
        # --- bump-version guards (v1.14.1) ---
        C("bump-version: invalid version", "bump-version.py", ["vX"], 1, want=("invalid version",)),
        C("bump-version: old==new abort", "bump-version.py", ["--apply", "v9.9.9", "--old", "v9.9.9"], 1,
          want=("nothing to bump",)),
        # --- error-sig / case-search / env-snapshot ---
        C("error-sig: match missing store", "error-sig.py",
          ["match", "--text", "x", "--store", tmp / "nosigs.json"], 2, want=("store not found",)),
        C("case-search: nonexistent dir", "case-search.py", ["--q", "x", "--dir", tmp / "nodir"], 0),
        C("env-snapshot: missing log (json)", "env-snapshot.py",
          ["--log", tmp / "nope.log", "--json"], 0, want=("not found",)),
        # --- token-meter / review-prefilter ---
        C("token-meter: empty file", "token-meter.py", ["--log", tmp / "empty.log"], 0, want=("no records",)),
        C("token-meter: garbage lines", "token-meter.py", ["--log", tmp / "garbage.jsonl"], 0, want=("records",)),
        C("review-prefilter: non-git dir", "review-prefilter.py",
          ["--base", "HEAD", "--cwd", str(tmp)], 0, want=("Not a git repository",)),
        # --- probe-tools (isolated copy, no manifest) / toolstack gate ---
        {"name": "probe-tools: missing manifest", "script": "probe-tools.py",
         "cmd": [PY, str(isolated / "probe-tools.py")], "expect": 1, "expect_any": (1,),
         "want": ("manifest not found",), "dont": ("Traceback",)},
        C("toolstack-pipeline: push non-TTY", "toolstack-pipeline.py", ["--push"], 0,
          want=("skip",), expect_any=(0, 2)),
        # --- privacy-scan (v1.16.0) ---
        C("privacy-scan: clean dir", "privacy-scan.py", [tmp / "clean"], 0, want=("CLEAN",)),
        C("privacy-scan: leak detection", "privacy-scan.py", [tmp / "leak"], 2,
          want=("blocker",)),
        C("privacy-scan: nonexistent dir", "privacy-scan.py", [tmp / "nodir"], 2,
          want=("not a directory",)),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="SDK robustness regression suite (20 cases)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", default=None, help="filter by script-name substring")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="rob-suite-") as td:
        tmp = Path(td)
        cases = build_cases(tmp)
        if args.only:
            cases = [c for c in cases if args.only in c["script"]]

        results = []
        for c in cases:
            code, out = run_case(c["cmd"], timeout=args.timeout)
            expect_ok = code == c["expect"] or (c.get("expect_any") and code in c["expect_any"])
            ok = expect_ok and all(w in out for w in c["want"]) and not any(d in out for d in c["dont"])
            results.append({"name": c["name"], "script": c["script"], "exit": code,
                            "expected": c["expect"], "ok": ok})

        passed = sum(1 for r in results if r["ok"])
        report = {"time": now_iso(), "total": len(results), "passed": passed,
                  "pass_rate": round(passed / len(results), 3) if results else 0.0,
                  "results": results}

        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"== robustness-suite ({len(results)} cases) ==")
            for r in results:
                mark = "OK " if r["ok"] else "!! "
                print(f"  {mark}[{r['exit']}/{r['expected']}] {r['name']}")
            print(f"Verdict: {passed}/{len(results)} passed")

        return 0 if passed == len(results) else 2


if __name__ == "__main__":
    sys.exit(main())
