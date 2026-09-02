"""Benchmark a model backend against the workflow's 8-Block extraction task.

Usage (from the skill dir, or anywhere — paths are resolved relative to file):
    python models/bench.py --backend all          # rule + needle
    python models/bench.py --backend needle --n 6
    python models/bench.py --backend needle --json out.json

Notes:
  * needle backend needs `import needle` to work — run with the python of a
    checkout where cactus-needle + its C++ engine are available
    (e.g. D:\\models\\needle\\.venv\\Scripts\\python.exe from cwd D:\\models\\needle).
  * A warmup call happens before timing so engine init is excluded.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.backends import _norm, load_backend  # noqa: E402
from models.schema import BLOCK_ORDER  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples", "prompts.json")


def _tokens(prompt: str) -> int:
    return len([t for t in prompt.split(",") if t.strip()])


def _rule_map(rule_fields: dict) -> dict:
    """token -> block for everything the rule baseline classified."""
    out = {}
    for block, tags in rule_fields.items():
        for t in tags:
            out[t] = block
    return out


def _needle_map(needle_fields: dict) -> dict:
    out = {}
    for block, tags in (needle_fields or {}).items():
        if not isinstance(tags, list):
            continue
        for t in tags:
            out[_norm(t)] = block
    return out


def _agreement(rule_fields: dict, needle_fields: dict):
    rule_map = _rule_map(rule_fields)
    ndl_map = _needle_map(needle_fields)
    if not rule_map:
        return None, None, None
    agree = sum(1 for t, b in rule_map.items() if ndl_map.get(t) == b)
    covered = sum(1 for t in rule_map if t in ndl_map)
    extra = len(set(ndl_map) - set(rule_map))
    return agree / len(rule_map), covered / len(rule_map), extra


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", choices=["rule", "needle", "minicpm", "all"], default="all")
    ap.add_argument("--n", type=int, default=0, help="limit sample count (0 = all)")
    ap.add_argument("--json", help="write metrics to this JSON file")
    ap.add_argument("--max-new-tokens", type=int, default=384,
                    help="needle max_new_tokens")
    args = ap.parse_args()

    with open(SAMPLES, encoding="utf-8") as fh:
        samples = json.load(fh)
    if args.n:
        samples = samples[: args.n]

    backends = ["rule", "needle"] if args.backend == "all" else [args.backend]
    print(f"# 8-Block extraction bench — {len(samples)} prompts | backends: {', '.join(backends)}")

    all_metrics = {}
    for name in backends:
        try:
            backend = load_backend(name, max_new_tokens=args.max_new_tokens)
        except Exception as err:
            print(f"\n## {name}: FAILED to load — {err}")
            continue

        # warmup (excludes engine init / schema grammar compile)
        backend.extract("masterpiece, best quality, 1girl, solo, close-up")

        rows, lat, confs, ok, results = [], [], [], 0, []
        for s in samples:
            t0 = time.perf_counter()
            fields = backend.extract(s["prompt"])
            ms = (time.perf_counter() - t0) * 1000
            conf = getattr(backend, "last_confidence", None)
            lat.append(ms)
            if conf is not None:
                confs.append(conf)
            if fields:
                ok += 1
            results.append(fields)
            rows.append((s["id"], s["theme"], _tokens(s["prompt"]),
                         round(ms, 1), conf if conf is not None else "-",
                         "Y" if fields else "N"))

        # agreement vs rule baseline (skip when backend IS the rule baseline;
        # reuses loop results — no second extraction pass)
        agree = cover = extra = None
        if name != "rule":
            rule = load_backend("rule")
            agrees = [_agreement(rule.extract(s["prompt"]), fields)
                      for s, fields in zip(samples, results)]
            good = [x for x in agrees if x[0] is not None]
            if good:
                agree = round(statistics.mean(x[0] for x in good) * 100, 1)
                cover = round(statistics.mean(x[1] for x in good) * 100, 1)
                extra = round(statistics.mean(x[2] for x in good), 1)

        metrics = {
            "backend": name,
            "n": len(samples),
            "success_rate": round(ok / len(samples) * 100, 1),
            "latency_ms": {
                "avg": round(statistics.mean(lat), 1),
                "p50": round(statistics.median(lat), 1),
                "p95": round(sorted(lat)[int(len(lat) * 0.95) - 1], 1),
                "min": round(min(lat), 1),
                "max": round(max(lat), 1),
            },
            "confidence": ({"avg": round(statistics.mean(confs), 3),
                            "min": round(min(confs), 3),
                            "max": round(max(confs), 3)}
                           if confs else None),
            "agreement_pct": agree,
            "rule_coverage_pct": cover,
            "extra_tokens_avg": extra,
            "rss_delta_mb": backend.rss_mb() if hasattr(backend, "rss_mb") else None,
            "llm_tokens_used": 0,  # on-device model: no API tokens
        }
        all_metrics[name] = metrics

        print(f"\n## {name}  — success {metrics['success_rate']}% | "
              f"latency avg {metrics['latency_ms']['avg']}ms "
              f"(p50 {metrics['latency_ms']['p50']} / p95 {metrics['latency_ms']['p95']})")
        if metrics["confidence"]:
            print(f"   confidence avg {metrics['confidence']['avg']} "
                  f"(min {metrics['confidence']['min']} / max {metrics['confidence']['max']})")
        if agree is not None:
            print(f"   agreement vs rule {agree}% | rule coverage {cover}% | extra {extra}")
        if metrics["rss_delta_mb"] is not None:
            print(f"   engine RSS delta ≈ {metrics['rss_delta_mb']} MB")
        print("   | id | theme | tags | ms | conf | ok |")
        print("   |----|-------|------|----|------|----|")
        for r in rows:
            print(f"   | {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
        backend.close()

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(all_metrics, fh, ensure_ascii=False, indent=2)
        print(f"\nmetrics written to {args.json}")


if __name__ == "__main__":
    main()
