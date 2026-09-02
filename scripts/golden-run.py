#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
golden-run.py — 金标回归 1 命令化 (v2.0, 2026-08-30)

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
     {"id":"qa-01","task_type":"qa","cell":"qa","prompt":"...","accept":[
        {"type":"regex","pattern":"..."} | {"type":"contains","text":"..."}],
      "expected":"...", "difficulty":"hard"}
  ]}
  NOTE: `cell` = 8-class fine-grained taxonomy (code/bug_fix/refactor/review/
  tool-use/qa/extraction/long-text); `task_type` = 5-class coarse. Recording
  uses `cell` — using `task_type` left 3 cells permanently empty (F-11).

v2.0 changes (2026-08-30, 自查 F-01/F-02/F-11):
  * 失败分类 classify_failure() → infra / timeout / empty / quality；前三类记
    outcome='infra_fail'，**不进能力后验**（此前空响应被当能力失败，sr 被压到 12%~40%）。
  * cost / latency_ms / level 传真实值（此前硬编码 0，导致三项指标全死）。
    成本需 --price-per-1k 或 --prices；未给价格时 cost=0 且 report 标注 cost_basis=none。
  * report 增 failure_taxonomy / capability_pass_rate / mean_latency_ms。

Usage:
  python golden-run.py --set golden-set-v3.json --json
  python golden-run.py --set golden-set.json --llm-url "$OMNIROUTE_URL" --model auto
  python golden-run.py --set golden-set.json --baseline baseline.json --json   # A/B diff
  python golden-run.py --set v3.json --model auto --record scripts/data/router-stats.db \
      --level 0 --price-per-1k 0.002
Exit codes: 0 = pass rate 100% / 2 = any sample failed or baseline regression >2%.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


SCHEMA = "diagnostic.v1"  # unified diagnostic schema (coding-agent-os §28.3, T7)


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


def load_router_stats():
    """Load scripts/router-stats.py as a module (feedback loop, T11)."""
    import importlib.util
    path = Path(__file__).resolve().parent / "router-stats.py"
    spec = importlib.util.spec_from_file_location("router_stats", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- 失败分类（F-01）-------------------------------------------------------
# 空响应/超时/5xx 属于基础设施失败，不是模型能力失败。v2.6.1 之前全部记成 fail，
# 把 bandit 后验压到 sr=12%~40%（自查实测 44 条 fail 中 35 条 tokens<50）。
INFRA_ERR_HINTS = (
    "timed out", "timeout", "connection refused", "connectionreseterror",
    "urlopen error", "temporarily unavailable", "name or service not known",
    "remote end closed", "ssl", "proxyerror", "httperror",
)
TIMEOUT_HINTS = ("timed out", "timeout", "deadline exceeded")


def classify_failure(ok: bool, error: str | None, detail: str, out_tokens: int,
                     empty_threshold: int) -> str | None:
    """Return error_class for a FAILED row, or None when the row passed.

    taxonomy: infra / timeout / empty / quality
      * infra / timeout / empty → 记 outcome='infra_fail'，不进能力后验
      * quality                → 记 outcome='fail'，正常计入后验
    """
    if ok:
        return None
    if error:
        low = error.lower()
        if any(h in low for h in TIMEOUT_HINTS):
            return "timeout"
        if re.search(r"http (5\d\d|429)", low):
            return "infra"
        if any(h in low for h in INFRA_ERR_HINTS):
            return "infra"
        return "infra"  # 调用未完成 = 基础设施问题，默认不惩罚模型
    if int(out_tokens) < empty_threshold:
        return "empty"  # 空响应/截断：无内容可判，不算能力失败
    return "quality"


def cost_of(total_tokens: int, model: str, prices: dict, flat: float | None) -> float:
    """Real cost estimate (F-02). Without a price table cost stays 0 — and the
    report says so explicitly instead of silently faking a number."""
    per_1k = flat if flat is not None else prices.get(model)
    if per_1k is None:
        return 0.0
    return round(total_tokens / 1000.0 * float(per_1k), 8)


def record_rows(rows: list[dict], args: argparse.Namespace) -> int:
    """Record per-row outcomes into the router-stats bandit store (zero-LLM).

    v2.7.0 (F-01/F-02/F-11):
      * cell 取样本的 `cell` 字段（8 分类细粒度），而非 `task_type`（5 分类粗粒度）——
        后者导致 bug_fix/review/refactor 三个 cell 恒无数据。
      * 失败按 error_class 分流：quality→fail，infra/timeout/empty→infra_fail。
      * cost / latency / level 传真实值（此前硬编码 0）。
    """
    mod = load_router_stats()
    db = Path(args.record)
    n = 0
    for row in rows:
        cell = args.cell or row.get("cell") or row.get("task_type") or "unknown"
        eclass = row.get("error_class")
        if row["ok"]:
            outcome = "pass"
        elif eclass in ("infra", "timeout", "empty"):
            outcome = "infra_fail"
        else:
            outcome = "fail"
        try:
            mod.record_outcome(db, task=str(args.set), cell=cell, model=args.model,
                               level=int(getattr(args, "level", 0) or 0), outcome=outcome,
                               tokens=int(row["in_tokens"]) + int(row["out_tokens"]),
                               cost=float(row.get("cost", 0.0)),
                               latency_ms=int(row.get("latency_ms", 0)),
                               error_class=eclass,
                               response_tokens=int(row.get("out_tokens_text", 0)))
            n += 1
        except ValueError as e:
            print(f"[warn] record skipped: {e}", file=sys.stderr)
    return n


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
    ap.add_argument("--record", default=None, help="router-stats.db path — record outcomes into bandit store (T11 feedback loop)")
    ap.add_argument("--cell", default=None,
                    help="cell tag for --record (default: sample `cell` field, 8-class)")
    ap.add_argument("--level", type=int, default=0,
                    help="escalation level for --record (F-02: 0=primary, 1+=fallback tier)")
    ap.add_argument("--prices", default=None,
                    help='JSON: {"model_id": price_per_1k_total_tokens}')
    ap.add_argument("--price-per-1k", type=float, default=None,
                    help="flat price per 1k total tokens (overrides --prices)")
    ap.add_argument("--infra-token-threshold", type=int, default=32,
                    help="output tokens below this on a failed call = empty response (infra, not capability)")
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

    prices = json.loads(args.prices) if args.prices else {}
    rows = []
    for s in samples:
        t0 = time.monotonic()
        if args.offline:
            resp = {"text": s.get("response", ""), "usage": s.get("usage", {}), "error": None}
        else:
            resp = llm_complete(args.llm_url, args.model, s["prompt"], args.timeout, args.api_key)
        latency_ms = int((time.monotonic() - t0) * 1000)
        ok, detail = structural_judge(s, resp["text"])
        err = resp.get("error")
        if err:
            ok, detail = False, f"LLM call failed: {err}"
        usage = resp.get("usage") or {}
        in_t = usage.get("prompt_tokens") or token_est(s.get("prompt", ""))
        out_t = usage.get("completion_tokens") or token_est(resp.get("text", ""))
        # F-01 修复补丁：空响应检测必须用**文本实导**的 token 数。实测 Ollama 在
        # finish_reason=length 时 usage.completion_tokens 会虚报（如 2048）而
        # text 实际为空 —— 用 usage 判定会把空响应误判成 quality 能力失败。
        out_t_text = token_est(resp.get("text", ""))
        rows.append({
            "id": s.get("id", "?"), "task_type": s.get("task_type", "?"),
            "cell": s.get("cell") or s.get("task_type") or "unknown",
            "ok": ok, "detail": detail, "in_tokens": in_t, "out_tokens": out_t,
            "out_tokens_text": out_t_text,
            "response_len": len(resp.get("text", "")),
            "error": err, "latency_ms": latency_ms,
            "cost": cost_of(int(in_t) + int(out_t), args.model, prices, args.price_per_1k),
            "error_class": classify_failure(ok, err, detail, out_t_text,
                                            args.infra_token_threshold),
        })

    passed = sum(1 for r in rows if r["ok"])
    pass_rate = passed / len(rows) if rows else 0.0
    in_sum = sum(r["in_tokens"] for r in rows)
    out_sum = sum(r["out_tokens"] for r in rows)
    eff = (in_sum + out_sum) / passed if passed else float("inf")

    recorded = 0
    if args.record:
        recorded = record_rows(rows, args)
        if not args.json:
            print(f"  [record] {recorded}/{len(rows)} outcomes -> {args.record}")

    baseline_note = None
    if args.baseline:
        base = load_json(Path(args.baseline))
        base_rate = base.get("pass_rate", 0.0)
        drop = base_rate - pass_rate
        baseline_note = {"baseline_pass_rate": base_rate, "current": pass_rate, "drop": drop}
        if drop > 0.02:
            print(f"[fail] regression: pass rate {base_rate:.1%} -> {pass_rate:.1%} (drop >2%)")

    # 失败分类汇总（F-01）：区分「模型不行」与「供应商抽风」
    taxonomy: dict[str, int] = {}
    for r in rows:
        if r["ok"]:
            continue
        taxonomy[r.get("error_class") or "unknown"] = taxonomy.get(r.get("error_class") or "unknown", 0) + 1
    infra_n = sum(v for k, v in taxonomy.items() if k != "quality")
    cap_total = len(rows) - infra_n
    cost_total = round(sum(r.get("cost", 0.0) for r in rows), 8)

    report = {
        "schema": SCHEMA,
        "time": now_iso(), "set": args.set, "model": args.model,
        "samples": len(rows), "passed": passed, "pass_rate": pass_rate,
        "in_tokens": in_sum, "out_tokens": out_sum, "total_tokens": in_sum + out_sum,
        "token_efficiency": eff, "baseline": baseline_note, "recorded_outcomes": recorded,
        "failure_taxonomy": taxonomy, "infra_failures": infra_n,
        # 剔除基础设施噪声后的真实能力通过率
        "capability_pass_rate": round(passed / cap_total, 4) if cap_total else None,
        "cost_total": cost_total,
        "cost_basis": ("flat" if args.price_per_1k is not None
                       else ("table" if prices else "none")),
        "mean_latency_ms": round(sum(r.get("latency_ms", 0) for r in rows) / len(rows), 1) if rows else 0,
        "rows": rows,
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
