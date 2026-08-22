#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
golden-run.py — 金标回归 1 命令化 (v1.0, 2026-08-22)

Purpose: turn §8/ref-05 golden-set regression into ONE command. Runs samples
against an LLM (default $OMNIROUTE_URL, OpenAI-compatible), judges
STRUCTURALLY (regex/contains — zero LLM-as-judge), and emits the ref-05 metric
table (pass rate / token efficiency / cost). Supports baseline diff (A/B).

Design rules (SDK §3/G-gates, §8, ref-05):
  * Python 3.9+ stdlib only. urllib for HTTP. JSON in/out.
  * Structural judging only — no LLM-as-judge (ref-05 §3 posture: judge
    structurally where the golden set permits, LLM-judge only as opt-in).
  * Exit: 0 = all pass / 2 = any fail or baseline regression >2%.
  * Never writes; never pushes.

Golden-set JSON schema (--set):
  {"samples": [
     {"id":"qa-01","task_type":"qa","prompt":"...","accept":[
        {"type":"regex","pattern":"..."} | {"type":"contains","text":"..."}],
      "expected":"...", "difficulty":"hard"}
  ]}

Usage:
  python golden-run.py --set golden-set-v3.json --json
  python golden-run.py --set golden-set.json --llm-url "$OMNIROUTE_URL" --model auto
  python golden-run.py --set golden-set.json --baseline baseline.json --json   # A/B diff
Exit codes: 0 = pass rate 100% / 2 = any sample failed or baseline regression >2%.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"[fatal] file not found: {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def parse_llm_response(raw: bytes) -> dict:
    """Parse an OpenAI-compatible response; tolerates SSE-streamed bodies (some
    gateways — e.g. OmniRoute for LongCat — return `data: {...}` chunks even when
    stream is not requested). Returns {text, usage, error}."""
    text_parts: list[str] = []
    usage: dict = {}
    try:
        data = json.loads(raw.decode("utf-8"))
        text_parts.append((data.get("choices") or [{}])[0].get("message", {}).get("content", ""))
        usage = data.get("usage") or {}
        return {"text": "".join(text_parts), "usage": usage, "error": None}
    except json.JSONDecodeError:
        pass  # fall through to SSE parsing
    try:
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                continue
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            delta = (chunk.get("choices") or [{}])[0].get("delta", {})
            if isinstance(delta, dict) and delta.get("content"):
                text_parts.append(delta["content"])
            u = chunk.get("usage")
            if isinstance(u, dict):
                usage = u
        return {"text": "".join(text_parts), "usage": usage, "error": None}
    except Exception as e:
        return {"text": "", "usage": {}, "error": f"response parse failed: {type(e).__name__}: {str(e)[:120]}"}


def llm_complete(url: str, model: str, prompt: str, timeout: int,
                 api_key: str | None = None) -> dict:
    """OpenAI-compatible chat completion via urllib. Returns {text, usage, error}."""
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2, "max_tokens": 2048}
    req = urllib.request.Request(url + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        return {"text": "", "usage": {}, "error": f"HTTP {e.code}: {detail}"}
    except Exception as e:  # URLError / timeout / connection refused
        return {"text": "", "usage": {}, "error": f"{type(e).__name__}: {str(e)[:150]}"}
    return parse_llm_response(raw)


def structural_judge(sample: dict, response: str) -> tuple[bool, str]:
    """Zero-LLM judging: all accept rules must match. Returns (ok, detail)."""
    accepts = sample.get("accept") or []
    if not accepts:
        return bool(sample.get("expected", "").strip()), "no accept rules — expected only"
    for rule in accepts:
        try:
            if rule.get("type") == "regex":
                if not re.search(rule["pattern"], response, re.S | re.I):
                    return False, f"regex not matched: {rule['pattern'][:60]}"
            elif rule.get("type") == "contains":
                if rule["text"] not in response:
                    return False, f"contains not matched: {rule['text'][:60]}"
        except (re.error, KeyError, TypeError) as e:
            return False, f"bad accept rule in golden set: {type(e).__name__}: {str(e)[:80]}"
    return True, "all accept rules matched"


def token_est(text: str) -> int:
    """Rough token estimate: CJK chars / 2, other chars / 4 (ref-06 style)."""
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other = len(text) - cjk
    return cjk // 2 + other // 4


def validate_set(samples: list[dict]) -> tuple[bool, list[str]]:
    """Pre-check all accept rules: regex must compile, keys must exist.
    Returns (ok, problems). Fail-fast before any LLM call (ref-19)."""
    problems: list[str] = []
    for s in samples:
        sid = s.get("id", "?")
        accepts = s.get("accept") or []
        if not accepts and not s.get("expected"):
            problems.append(f"{sid}: no accept rules and no expected")
            continue
        for i, rule in enumerate(accepts):
            if not isinstance(rule, dict):
                problems.append(f"{sid}: accept[{i}] not an object")
                continue
            rtype = rule.get("type")
            if rtype not in ("regex", "contains"):
                problems.append(f"{sid}: accept[{i}] unknown type {rtype!r}")
                continue
            if rtype == "regex":
                try:
                    re.compile(rule["pattern"])
                except re.error as e:
                    problems.append(f"{sid}: accept[{i}] regex compile failed: {e}")
                except KeyError:
                    problems.append(f"{sid}: accept[{i}] missing 'pattern'")
            else:
                if "text" not in rule:
                    problems.append(f"{sid}: accept[{i}] missing 'text'")
    return (len(problems) == 0, problems)


def main() -> int:
    ap = argparse.ArgumentParser(description="Golden-set regression in one command (ref-05)")
    ap.add_argument("--set", required=True, help="golden-set JSON path")
    ap.add_argument("--llm-url", default=os.environ.get("OMNIROUTE_URL", ""),
                    help="OpenAI-compatible base URL (default: $OMNIROUTE_URL env)")
    ap.add_argument("--model", default="auto", help="model id")
    ap.add_argument("--api-key", default=None, help="Bearer token if required")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--offline", action="store_true", help="skip LLM calls, judge samples with pre-filled 'response' field")
    ap.add_argument("--baseline", default=None, help="baseline JSON for A/B diff")
    ap.add_argument("--validate-set", action="store_true", help="pre-check accept rules (regex compile) then exit — no LLM calls")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    args = ap.parse_args()

    gs = load_json(Path(args.set))
    samples = gs.get("samples", [])
    if not samples:
        print(f"[fatal] no samples in {args.set}")
        return 2

    if args.validate_set:
        ok, problems = validate_set(samples)
        report = {"set": args.set, "samples": len(samples), "valid": ok, "problems": problems}
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"== golden-set validation: {args.set} ({len(samples)} samples) ==")
            if ok:
                print("  VALID — all accept rules OK")
            else:
                for p in problems:
                    print(f"  !! {p}")
        return 0 if ok else 2

    if not args.offline and not args.llm_url:
        print("[fatal] no LLM URL: set OMNIROUTE_URL env or pass --llm-url", file=sys.stderr)
        return 2

    rows = []
    for s in samples:
        if args.offline:
            resp = {"text": s.get("response", ""), "usage": s.get("usage", {}), "error": None}
        else:
            resp = llm_complete(args.llm_url, args.model, s["prompt"], args.timeout, args.api_key)
        ok, detail = structural_judge(s, resp["text"])
        if resp.get("error"):
            ok, detail = False, f"LLM call failed: {resp['error']}"
        usage = resp.get("usage") or {}
        in_t = usage.get("prompt_tokens") or token_est(s.get("prompt", ""))
        out_t = usage.get("completion_tokens") or token_est(resp.get("text", ""))
        rows.append({
            "id": s.get("id", "?"), "task_type": s.get("task_type", "?"),
            "ok": ok, "detail": detail, "in_tokens": in_t, "out_tokens": out_t,
            "response_len": len(resp.get("text", "")),
        })

    passed = sum(1 for r in rows if r["ok"])
    pass_rate = passed / len(rows) if rows else 0.0
    in_sum = sum(r["in_tokens"] for r in rows)
    out_sum = sum(r["out_tokens"] for r in rows)
    eff = (in_sum + out_sum) / passed if passed else float("inf")

    baseline_note = None
    if args.baseline:
        base = load_json(Path(args.baseline))
        base_rate = base.get("pass_rate", 0.0)
        drop = base_rate - pass_rate
        baseline_note = {"baseline_pass_rate": base_rate, "current": pass_rate, "drop": drop}
        if drop > 0.02:
            print(f"[fail] regression: pass rate {base_rate:.1%} -> {pass_rate:.1%} (drop >2%)")

    report = {
        "time": now_iso(), "set": args.set, "model": args.model,
        "samples": len(rows), "passed": passed, "pass_rate": pass_rate,
        "in_tokens": in_sum, "out_tokens": out_sum, "total_tokens": in_sum + out_sum,
        "token_efficiency": eff, "baseline": baseline_note, "rows": rows,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"  {'OK ' if r['ok'] else '!! '} {r['id']:<12} [{r['task_type']:<8}] {r['detail'][:80]}")
        print(f"\nPass rate: {passed}/{len(rows)} = {pass_rate:.1%}")
        print(f"Tokens: in={in_sum} out={out_sum} total={in_sum + out_sum} eff={eff:.0f}/pass")

    failed = len(rows) - passed
    if baseline_note and baseline_note["drop"] > 0.02:
        return 2
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
