#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
router-stats.py — 离线路由反馈与校准 (v2.0, 2026-08-30)

Purpose: implement the model-router feedback loop (coding-agent-os §6, §28.5)
as a DETERMINISTIC, OFFLINE, zero-LLM tool. The SDK §4 routing matrix stays
the static prior; this script learns per-(model, cell) success from golden-run
outcomes and reports calibration + cost-per-successful-task. No online router,
no daemon, no LLM inference.

Design rules (coding-agent-os §6.2 two-stage / §28.5 / §28.11 cold-start, SDK §4):
  * Stage 1 = hard filter (context fit / capability / health / task-type->class)
    is done by the AGENT using the §4 matrix + toolstack.json — NOT scripted.
  * Stage 2 = contextual bandit: Beta(alpha, beta) per (model, cell); Thompson
    sampling on utility = success prob − cost − failure penalty (+ exploration).
  * Cold start (§28.11): seed priors from golden baselines / benchmark tables
    via --priors (model->success_rate); with no data recommend prints priors.
  * Python 3.9+ stdlib only (sqlite3). JSON out. Exit: 0 = ok / 2 = error.

v2.0 changes (2026-08-30, 自查 F-01/F-03/F-04/F-11):
  * `outcome='infra_fail'` — 基础设施/空响应/超时失败**不进能力后验**（alpha/beta 不动），
    只累加 `infra_count`。此前空响应被当能力失败，把 sr 压到 12%~40%。
  * `error_class` 列（infra/quality/timeout/empty）+ `response_tokens` 列，可回溯诊断。
  * **校准改为「先验快照 vs 事后观测」**：`snapshot` 子命令冻结当前后验为 α0/β0，
    report 用快照之后的观测 sr 与之比对。旧实现 α≡sc、β≡n−sc，expected≡actual → MAE 恒 0。
  * `report` 增 `coverage`（golden set cell 覆盖度），暴露空转 cell。
  * 旧库自动迁移（PRAGMA table_info 检测缺失列后 ALTER TABLE）。

Usage:
  python router-stats.py init --db scripts/data/router-stats.db
  python router-stats.py record --db x.db --task t-01 --cell bug_fix --model deepseek-v4 --level 1 --outcome pass --tokens 1200 --cost 0.001 --latency 800
  python router-stats.py record --db x.db --cell qa --model auto --outcome infra_fail --error-class empty --response-tokens 7
  python router-stats.py snapshot --db x.db --json     # 重采基线前冻结先验
  python router-stats.py recommend --db x.db --cell bug_fix --top 3
  python router-stats.py report --db x.db --golden-set scripts/data/golden-set-v3.json --json
Exit codes: 0 = ok / 2 = error (invalid outcome / database error).
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTCOMES = ("pass", "fail", "escalated", "infra_fail")
# outcome that must NOT污染能力后验（F-01）
NON_CAPABILITY_OUTCOMES = ("infra_fail",)
ERROR_CLASSES = ("infra", "quality", "timeout", "empty")
DEFAULT_DB = Path(__file__).resolve().parent / "data" / "router-stats.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS routing_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, task TEXT, cell TEXT NOT NULL, model TEXT NOT NULL,
  level INTEGER DEFAULT 0, outcome TEXT NOT NULL, tokens INTEGER DEFAULT 0,
  cost REAL DEFAULT 0, latency_ms INTEGER DEFAULT 0,
  error_class TEXT, response_tokens INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bandit (
  model TEXT NOT NULL, cell TEXT NOT NULL,
  alpha INTEGER DEFAULT 0, beta INTEGER DEFAULT 0, n INTEGER DEFAULT 0,
  success_count INTEGER DEFAULT 0, cost_sum REAL DEFAULT 0, tokens_sum INTEGER DEFAULT 0,
  infra_count INTEGER DEFAULT 0,
  PRIMARY KEY (model, cell)
);
CREATE TABLE IF NOT EXISTS bandit_prior_snapshot (
  model TEXT NOT NULL, cell TEXT NOT NULL,
  alpha0 INTEGER NOT NULL, beta0 INTEGER NOT NULL, n0 INTEGER NOT NULL,
  ts TEXT NOT NULL,
  PRIMARY KEY (model, cell)
);
"""

# v1 -> v2 迁移：旧库缺的列/表自动补齐（幂等）
MIGRATIONS = (
    ("routing_log", "error_class", "ALTER TABLE routing_log ADD COLUMN error_class TEXT"),
    ("routing_log", "response_tokens",
     "ALTER TABLE routing_log ADD COLUMN response_tokens INTEGER DEFAULT 0"),
    ("bandit", "infra_count",
     "ALTER TABLE bandit ADD COLUMN infra_count INTEGER DEFAULT 0"),
)


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Add v2 columns to a v1 database. Idempotent; returns applied statements.

    v2.7.1 backfill (F-17): legacy rows predate the v2 columns — they carry real
    `tokens` but response_tokens=0 / error_class=NULL. Backfill maps them so the
    failure taxonomy has no NULL bucket:
      * response_tokens <- tokens (where v2 column still 0 and v1 value > 0)
      * error_class <- 'quality' for outcome='fail' rows (substantive responses;
        truly-empty legacy rows were already retagged by rebuild --retag)
    """
    applied = []
    for table, column, stmt in MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(stmt)
            applied.append(f"{table}.{column}")
    n1 = conn.execute(
        "UPDATE routing_log SET response_tokens = tokens"
        " WHERE response_tokens = 0 AND tokens > 0").rowcount
    n2 = conn.execute(
        "UPDATE routing_log SET error_class = 'quality'"
        " WHERE outcome = 'fail' AND error_class IS NULL").rowcount
    if n1:
        applied.append(f"backfill.response_tokens({n1})")
    if n2:
        applied.append(f"backfill.error_class({n2})")
    if applied:
        conn.commit()
    return applied


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        migrate(conn)
        return conn
    except sqlite3.Error as e:
        print(f"[fatal] database error: {db_path}: {e}", file=sys.stderr)
        sys.exit(2)


def record_outcome(db_path: Path, task: str, cell: str, model: str, level: int,
                   outcome: str, tokens: int, cost: float, latency_ms: int,
                   error_class: str | None = None,
                   response_tokens: int = 0) -> None:
    """Upsert bandit posterior + append routing_log. Raises ValueError on bad outcome.

    v2.0 (F-01): `outcome='infra_fail'` counts into `infra_count` and `tokens_sum`
    but leaves alpha/beta/n untouched — an empty 7-token response says nothing
    about model capability, and folding it into beta was deflating sr to 12-40%.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"invalid outcome {outcome!r} (expect one of {OUTCOMES})")
    if error_class is not None and error_class not in ERROR_CLASSES:
        raise ValueError(f"invalid error_class {error_class!r} (expect one of {ERROR_CLASSES})")
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO routing_log (ts, task, cell, model, level, outcome, tokens,"
            " cost, latency_ms, error_class, response_tokens)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (now_iso(), task, cell, model, level, outcome, tokens, cost, latency_ms,
             error_class, response_tokens))
        cur = conn.execute("SELECT alpha, beta, n, success_count, cost_sum, tokens_sum,"
                           " COALESCE(infra_count,0)"
                           " FROM bandit WHERE model=? AND cell=?", (model, cell))
        row = cur.fetchone()
        if row is None:
            a, b, n, sc, cs, ts_, ic = 0, 0, 0, 0, 0.0, 0, 0
        else:
            a, b, n, sc, cs, ts_, ic = row
        if outcome == "infra_fail":
            ic += 1  # 非能力失败：只计数，不动后验
        else:
            if outcome == "pass":
                a += 1
                sc += 1
            else:
                b += 1
            n += 1
        conn.execute(
            "INSERT OR REPLACE INTO bandit (model, cell, alpha, beta, n, success_count,"
            " cost_sum, tokens_sum, infra_count)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (model, cell, a, b, n, sc, cs + cost, ts_ + tokens, ic))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[fatal] database error: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        conn.close()


def beta_sample(alpha: float, beta: float, rng: random.Random) -> float:
    """One Thompson draw from Beta(alpha, beta)."""
    if alpha <= 0 and beta <= 0:
        return 0.5
    if alpha <= 0:
        return 0.0
    if beta <= 0:
        return 1.0
    x = rng.gammavariate(alpha, 1.0)
    y = rng.gammavariate(beta, 1.0)
    return x / (x + y)


def recommend(db_path: Path, cell: str, top: int, seed: int | None, priors: dict) -> dict:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT model, alpha, beta, n, success_count, cost_sum, tokens_sum"
        " FROM bandit WHERE cell=? ORDER BY n DESC", (cell,)).fetchall()
    rng = random.Random(seed)
    candidates = []
    for model, a, b, n, sc, cs, ts_ in rows:
        prob = beta_sample(a, b, rng)
        success_rate = sc / n if n else 0.0
        cost_per_task = cs / n if n else 0.0
        cost_penalty = min(0.3, cost_per_task * 1000)
        fail_penalty = 0.2 * (1 - success_rate)
        explore = 0.15 * min(1.0, n / 10.0)
        utility = round(0.6 * prob + explore - cost_penalty - fail_penalty, 4)
        candidates.append({
            "model": model, "alpha": a, "beta": b, "n": n,
            "success_rate": round(success_rate, 3),
            "expected_prob": round(a / (a + b), 3) if (a + b) else None,
            "cost_per_task": round(cost_per_task, 5),
            "utility": utility,
        })
    candidates.sort(key=lambda r: (-r["utility"], -r["n"]))
    out = {"schema": "diagnostic.v1", "cell": cell, "no_data": not candidates,
           "top": candidates[:top]}
    if not candidates and priors:
        out["priors"] = priors  # cold-start seeds (§28.11): {model: success_rate}
    conn.close()
    return out


def rebuild_bandit(db_path: Path, retag_threshold: int = 0, backup: bool = True) -> dict:
    """Rebuild `bandit` from `routing_log` (F-01 数据修复, 确定性、可重放).

    Optional retag: rows with outcome='fail' AND effective tokens < retag_threshold
    are reclassified as `infra_fail`/`empty` — these are provably empty or truncated
    responses (observed 3-13 tokens), never model reasoning. Effective tokens =
    COALESCE(NULLIF(response_tokens,0), tokens) — v2.7.1 (F-17): legacy rows carry
    the v1 `tokens` column; new rows carry `response_tokens`; either must retag.

    The posterior is then recomputed from scratch:
      alpha=pass · beta=fail+escalated · n=capability trials · infra_count=infra_fail
    infra_fail rows contribute tokens/cost to the sums but never to alpha/beta/n.
    """
    backup_path = None
    if backup and db_path.exists():
        backup_path = db_path.with_suffix(db_path.suffix + f".bak-{now_iso().replace(':','-')}")
        backup_path.write_bytes(db_path.read_bytes())
    conn = connect(db_path)
    retagged = 0
    if retag_threshold > 0:
        cur = conn.execute(
            "UPDATE routing_log SET outcome='infra_fail',"
            " error_class=CASE WHEN error_class IN ('timeout','infra') THEN error_class"
            " ELSE 'empty' END"
            " WHERE outcome='fail'"
            " AND COALESCE(NULLIF(response_tokens,0), tokens) < ?", (retag_threshold,))
        retagged = cur.rowcount
    conn.execute("DELETE FROM bandit")
    rows = conn.execute(
        "SELECT model, cell, outcome, tokens, cost FROM routing_log").fetchall()
    agg: dict[tuple[str, str], dict] = {}
    for model, cell, outcome, tokens, cost in rows:
        k = (model, cell)
        a = agg.setdefault(k, {"a": 0, "b": 0, "n": 0, "sc": 0, "cs": 0.0,
                               "ts": 0, "ic": 0})
        a["cs"] += cost or 0.0
        a["ts"] += tokens or 0
        if outcome == "infra_fail":
            a["ic"] += 1
        else:
            if outcome == "pass":
                a["a"] += 1
                a["sc"] += 1
            else:
                a["b"] += 1
            a["n"] += 1
    for (model, cell), a in agg.items():
        conn.execute(
            "INSERT OR REPLACE INTO bandit (model, cell, alpha, beta, n, success_count,"
            " cost_sum, tokens_sum, infra_count) VALUES (?,?,?,?,?,?,?,?,?)",
            (model, cell, a["a"], a["b"], a["n"], a["sc"], a["cs"], a["ts"], a["ic"]))
    conn.commit()
    conn.close()
    return {"schema": "diagnostic.v1", "rebuilt_cells": len(agg), "retagged_rows": retagged,
            "backup": str(backup_path) if backup_path else None,
            "retag_threshold": retag_threshold}


def snapshot_priors(db_path: Path) -> dict:
    """Freeze the current bandit posterior as the prior for the next window.

    Call this BEFORE re-running a baseline. Calibration (F-03) then compares the
    frozen prior against outcomes observed after `snapshot_ts` — without it,
    expected≡actual and the "MAE>0.1 调先验" gate can never fire.
    """
    conn = connect(db_path)
    rows = conn.execute("SELECT model, cell, alpha, beta, n FROM bandit").fetchall()
    ts = now_iso()
    for model, cell, a, b, n in rows:
        conn.execute("INSERT OR REPLACE INTO bandit_prior_snapshot"
                     " (model, cell, alpha0, beta0, n0, ts) VALUES (?,?,?,?,?,?)",
                     (model, cell, a, b, n, ts))
    conn.commit()
    conn.close()
    return {"schema": "diagnostic.v1", "snapshot_ts": ts, "frozen_cells": len(rows)}


def calibration(db_path: Path) -> dict:
    """先验 vs 事后观测（F-03 修复）。

    v1 用 bandit 自身的 α/(α+β) 比 sc/n —— 二者由同一组计数导出，恒等，MAE 恒 0。
    v2 用 `bandit_prior_snapshot` 冻结的 α0/β0 作 expected，只统计快照时间戳**之后**
    新观测到的 pass/fail/escalated 作 actual。
    """
    conn = connect(db_path)
    snaps = conn.execute(
        "SELECT model, cell, alpha0, beta0, ts FROM bandit_prior_snapshot").fetchall()
    detail: list[dict] = []
    for model, cell, a0, b0, ts in snaps:
        a0, b0 = a0 or 0, b0 or 0
        if a0 + b0 == 0:
            continue  # 无先验信息，跳过
        row = conn.execute(
            "SELECT SUM(outcome='pass'), SUM(outcome='fail'), SUM(outcome='escalated'), COUNT(*)"
            " FROM routing_log WHERE model=? AND cell=? AND ts >= ?",
            (model, cell, ts)).fetchone()
        p, f, e = (row[0] or 0, row[1] or 0, row[2] or 0)
        trials = p + f + e  # infra_fail 不计入能力试验
        if trials < 5:
            continue
        expected = a0 / (a0 + b0)
        actual = p / trials
        detail.append({"model": model, "cell": cell,
                       "expected": round(expected, 3), "actual": round(actual, 3),
                       "trials": trials, "err": round(abs(expected - actual), 3)})
    has_snapshot = bool(snaps)
    conn.close()
    errs = [d["err"] for d in detail]
    return {
        "method": "prior_snapshot_vs_observed",
        "has_snapshot": has_snapshot,
        "cells_measured": len(errs),
        "mean_abs_error": round(sum(errs) / len(errs), 3) if errs else None,
        "max_abs_error": max(errs) if errs else None,
        "note": None if has_snapshot else
                "no prior snapshot — run `snapshot` before re-baselining to enable calibration",
        "detail": detail,
    }


def coverage(db_path: Path, golden_set: Path | None) -> dict | None:
    """golden set cell 覆盖度（F-11）：暴露零数据、学习闭环空转的 cell。"""
    if golden_set is None:
        return None
    try:
        data = json.loads(Path(golden_set).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"error": f"cannot read golden set: {e}"}
    samples = data.get("samples", []) if isinstance(data, dict) else []
    # `cell` 才是 8 分类细粒度标签；`task_type` 是 5 分类粗粒度（F-11 根因：
    # golden-run 曾用 task_type 记账，导致 bug_fix/review/refactor 三个 cell 恒空）
    wanted = sorted({s.get("cell") or s.get("task_type") or "unknown" for s in samples})
    conn = connect(db_path)
    with_data = {r[0] for r in conn.execute(
        "SELECT DISTINCT cell FROM bandit WHERE n > 0")}
    conn.close()
    missing = [c for c in wanted if c not in with_data]
    return {"cells_in_golden": len(wanted), "cells_with_data": len(wanted) - len(missing),
            "missing": missing,
            "ratio": round((len(wanted) - len(missing)) / len(wanted), 3) if wanted else None}


def report(db_path: Path, golden_set: Path | None = None) -> dict:
    conn = connect(db_path)
    logs = conn.execute("SELECT COUNT(*), SUM(outcome='pass'), SUM(outcome='fail'),"
                        " SUM(outcome='escalated'), SUM(outcome='infra_fail'),"
                        " COALESCE(SUM(tokens),0), COALESCE(SUM(cost),0),"
                        " COALESCE(SUM(CASE WHEN latency_ms>0 THEN latency_ms ELSE 0 END),0)"
                        " FROM routing_log").fetchone()
    total, success, fail, escalated, infra, tokens, cost, latency = (
        logs[0] or 0, logs[1] or 0, logs[2] or 0, logs[3] or 0, logs[4] or 0,
        logs[5] or 0, logs[6] or 0.0, logs[7] or 0)
    # v2.7.1 (F-17): fail rows without an error_class = taxonomy hole.
    # migrate() backfills legacy rows; a non-zero count here means new rows are
    # being recorded without classification — investigate before trusting sr.
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM routing_log WHERE outcome='fail' AND error_class IS NULL"
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT cell, model, n, success_count, cost_sum, tokens_sum,"
        " COALESCE(infra_count,0) FROM bandit ORDER BY cell, n DESC").fetchall()
    per_cell: dict[str, list] = {}
    for cell, model, n, sc, cs, ts_, ic in rows:
        per_cell.setdefault(cell, []).append({
            "model": model, "n": n, "success_rate": round(sc / n, 3) if n else 0.0,
            "cost_per_success": round(cs / sc, 5) if sc else None,
            "tokens_per_success": round(ts_ / sc, 1) if sc else None,
            "infra_count": ic,
        })
    conn.close()
    trials = success + fail + escalated  # 能力试验数（不含 infra_fail）
    return {
        "schema": "diagnostic.v1",
        "records": total, "capability_trials": trials,
        "cells": sorted(per_cell.keys()),
        "outcomes": {"pass": success, "fail": fail, "escalated": escalated,
                     "infra_fail": infra},
        "unclassified_fail_rows": unclassified,
        "escalation_rate": round(escalated / trials, 3) if trials else 0.0,
        "infra_rate": round(infra / total, 3) if total else 0.0,
        "cost_per_successful_task": round(cost / success, 5) if success else None,
        "token_efficiency": round(tokens / success, 1) if success else None,
        "mean_latency_ms": round(latency / trials, 1) if trials else None,
        "calibration": calibration(db_path),
        "coverage": coverage(db_path, golden_set),
        "per_cell": per_cell,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline router feedback + calibration (bandit, zero-LLM)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_db(p: argparse.ArgumentParser) -> None:
        # NOTE: --db lives on subparsers, not the main parser — argparse routes
        # args after the subcommand token to the subparser only.
        p.add_argument("--db", default=str(DEFAULT_DB),
                       help="SQLite db path (default: scripts/data/router-stats.db)")

    i = sub.add_parser("init", help="create schema (auto-created on any command; init is explicit)")
    add_db(i)

    r = sub.add_parser("record", help="record one routing outcome")
    add_db(r)
    r.add_argument("--task", default="")
    r.add_argument("--cell", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--level", type=int, default=0)
    r.add_argument("--outcome", required=True)
    r.add_argument("--tokens", type=int, default=0)
    r.add_argument("--cost", type=float, default=0.0)
    r.add_argument("--latency", type=int, default=0)
    r.add_argument("--error-class", default=None,
                   help=f"failure taxonomy: one of {ERROR_CLASSES}")
    r.add_argument("--response-tokens", type=int, default=0,
                   help="completion tokens of the response (for empty-response forensics)")

    sp = sub.add_parser(
        "snapshot", help="freeze current bandit posterior as calibration prior (call before re-baselining)")
    add_db(sp)

    rb = sub.add_parser("rebuild", help="rebuild bandit from routing_log (F-01 data repair)")
    add_db(rb)
    rb.add_argument("--retag-threshold", type=int, default=0,
                    help="reclassify fail rows with tokens < N as infra_fail/empty (0 = no retag)")
    rb.add_argument("--no-backup", action="store_true", help="skip the .bak-<ts> copy")

    rc = sub.add_parser("recommend", help="Thompson-ranked model candidates for a cell")
    add_db(rc)
    rc.add_argument("--cell", required=True)
    rc.add_argument("--top", type=int, default=3)
    rc.add_argument("--seed", type=int, default=None, help="fix sampling for reproducibility")
    rc.add_argument("--priors", default=None, help='JSON: {"model": success_rate} cold-start seeds')

    rp = sub.add_parser("report", help="calibration + cost/token metrics")
    add_db(rp)
    rp.add_argument("--json", action="store_true")
    rp.add_argument("--golden-set", default=None,
                    help="golden-set JSON path — enables cell coverage report")

    args = ap.parse_args()
    db = Path(args.db)

    if args.cmd == "init":
        connect(db)
        print(json.dumps({"schema": "diagnostic.v1", "db": str(db), "created": True}))
        return 0

    if args.cmd == "record":
        try:
            record_outcome(db, args.task, args.cell, args.model, args.level,
                           args.outcome, args.tokens, args.cost, args.latency,
                           args.error_class, args.response_tokens)
        except ValueError as e:
            print(f"[fatal] {e}", file=sys.stderr)
            return 2
        print(json.dumps({"schema": "diagnostic.v1", "recorded": True, "cell": args.cell,
                          "model": args.model, "outcome": args.outcome,
                          "error_class": args.error_class}))
        return 0

    if args.cmd == "snapshot":
        out = snapshot_priors(db)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "rebuild":
        out = rebuild_bandit(db, args.retag_threshold, backup=not args.no_backup)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "recommend":
        priors = json.loads(args.priors) if args.priors else {}
        out = recommend(db, args.cell, args.top, args.seed, priors)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "report":
        rep = report(db, Path(args.golden_set) if args.golden_set else None)
        if args.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            print(f"== router-stats: {db} ({rep['records']} records, "
                  f"{rep['capability_trials']} capability trials, {len(rep['cells'])} cells) ==")
            o = rep["outcomes"]
            print(f"  outcomes: pass={o['pass']} fail={o['fail']} escalated={o['escalated']} "
                  f"infra_fail={o['infra_fail']}")
            print(f"  escalation_rate={rep['escalation_rate']}  infra_rate={rep['infra_rate']}")
            print(f"  cost/successful-task={rep['cost_per_successful_task']}  "
                  f"tokens/success={rep['token_efficiency']}  mean_latency={rep['mean_latency_ms']}ms")
            cal = rep["calibration"]
            if cal["mean_abs_error"] is not None:
                print(f"  calibration mean|err|={cal['mean_abs_error']} "
                      f"max|err|={cal['max_abs_error']} (cells: {cal['cells_measured']})")
            else:
                reason = cal["note"] or (
                    f"no cell reached 5 new trials since the snapshot "
                    f"(measured={cal['cells_measured']})")
                print(f"  calibration: unavailable — {reason}")
            cov = rep["coverage"]
            if cov and "error" not in cov:
                flag = "  ⚠️  缺数据" if cov["missing"] else ""
                print(f"  coverage: {cov['cells_with_data']}/{cov['cells_in_golden']}"
                      f" cells{flag} missing={cov['missing']}")
            for cell, rows_ in rep["per_cell"].items():
                for m in rows_:
                    print(f"  [{cell:<10}] {m['model']:<14} n={m['n']:<3} "
                          f"sr={m['success_rate']:.0%} cost/succ={m['cost_per_success']} "
                          f"infra={m['infra_count']}")
            if rep["infra_rate"] > 0.3:
                print("  [warn] infra_rate > 30% — 供应商/网络不稳定，能力评估不可信（ref-23 §8）")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
