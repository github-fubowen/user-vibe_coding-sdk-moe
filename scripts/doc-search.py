#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc-search.py — 参考语料池检索（L1 档，stdlib 关键词打分）

Why: 语料池 ≥20 份后，「人工记忆 + grep」不再是检索方式。本脚本与
cybersecurity-skills-router 的 search.py（114 行 stdlib）同构 —— **不引第三方
检索库**（脚本纪律），L2 才谈 SQLite FTS5，L3 才谈向量 + rerank（规模驱动 §6）。

关键约束：**检索 = T2 档分类/匹配任务，不是推理任务**（SKILL §2.2，思考 OFF）。
所以这里只做打分排序，不做任何 LLM 调用。

Scoring: title×3 / tags×2 / 章节正文×1（命中章节才计入，避免整份文档稀释）。
Query 切分：拉丁按词，CJK 按 2-gram（中文无空格，单字召回噪声太大）。

Usage:
    python scripts/doc-search.py "资源管理层 设计" [--top-k 5] [--json]
                                 [--section] [--max-tokens 8000]
                                 [--corpus-root DIR] [--index PATH]

Exit: 0 = 有结果 · 1 = 用法/环境错误 · 2 = 索引不可用（D-01/D-02 fail-closed）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import re
import sys

try:
    from _common import EXIT_ERROR, EXIT_GATE, EXIT_OK, schema
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from _common import EXIT_ERROR, EXIT_GATE, EXIT_OK, schema

SCHEMA_ID = schema("doc-index")
OUT_SCHEMA = "doc-search.v1"
DEFAULT_CORPUS_ROOT = pathlib.Path("D:" + os.sep + "WorkBuddy") / "data" / "SDK_Reference"
CORPUS_ENV = "SDK_DOCS_ROOT"
SDK_INDEX_REL = "scripts/data/doc-index.json"

W_TITLE, W_TAGS, W_BODY = 3.0, 2.0, 1.0
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def corpus_root(cli: str | None = None) -> pathlib.Path:
    for cand in (cli, os.environ.get(CORPUS_ENV)):
        if cand:
            return pathlib.Path(cand)
    return DEFAULT_CORPUS_ROOT


def query_terms(q: str) -> list[str]:
    """拉丁按词 + CJK 按 2-gram（短词补单词，避免 <2 字查询召回为空）。"""
    terms = [w.lower() for w in TOKEN_RE.findall(q)]
    cjk = "".join(CJK_RE.findall(q))
    if len(cjk) == 1:
        terms.append(cjk)
    else:
        terms += [cjk[i:i + 2] for i in range(len(cjk) - 1)]
    return [t for t in terms if t]


def count_hits(text: str, terms: list[str]) -> int:
    low = text.lower()
    return sum(low.count(t) for t in terms)


def sublinear(tf: int) -> float:
    """次线性 tf：1+log(tf)。长文档靠堆词频刷分是 L1 检索最常见的排序崩坏。"""
    return 0.0 if tf <= 0 else 1.0 + math.log(tf)


def section_hits(text: str, kept: list[dict], terms: list[str]) -> list[dict]:
    """在 kept 章节范围内统计命中，返回 {title,line,hits,char_start,tokens_est}。"""
    out = []
    for i, s in enumerate(kept or []):
        end = kept[i + 1]["char_start"] if i + 1 < len(kept) else len(text)
        body = text[s["char_start"]:end]
        hits = count_hits(s.get("title", ""), terms) * 2 + count_hits(body, terms)
        if hits:
            out.append({"title": s.get("title"), "level": s.get("level"),
                        "line": s.get("line"), "char_start": s.get("char_start", 0),
                        "hits": hits, "tokens_est": int(len(body) * 0.6)})
    return sorted(out, key=lambda x: -x["hits"])


def snippet(text: str, char_start: int, terms: list[str], max_chars: int = 600) -> str:
    seg = text[char_start:char_start + max_chars * 3]
    low = seg.lower()
    pos = min([low.find(t) for t in terms if low.find(t) >= 0] or [0])
    start = max(0, pos - 80)
    body = seg[start:start + max_chars].replace("\n", " ").strip()
    return ("…" if start else "") + body + ("…" if len(seg) > start + max_chars else "")


def merge_kept(idx: dict, root: pathlib.Path) -> bool:
    """kept 外置（§6-10）后的运行时回填：SDK 登记簿没有 kept，从语料池镜像补。

    镜像缺盘/损坏 → 返回 False，`--section` 降级为仅文档级命中（fail-soft，
    不判失败 —— 与 D-03′ 跨盘降级同一哲学）。
    """
    if all((d.get("shape") or {}).get("kept") for d in idx.get("docs", [])):
        return False
    try:
        mirror = json.loads((root / "index.json").read_text(encoding="utf-8"))
        by_path = {d.get("path"): (d.get("shape") or {}).get("kept", [])
                   for d in mirror.get("docs", [])}
        merged = False
        for d in idx.get("docs", []):
            if not (d.get("shape") or {}).get("kept"):
                kept = by_path.get(d.get("path"))
                if kept:
                    d.setdefault("shape", {})["kept"] = kept
                    merged = True
        return merged
    except (OSError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="doc-search.py",
        description="参考语料池关键词检索（L1，stdlib；title×3/tags×2/body×1）")
    ap.add_argument("query", nargs="+", help="检索词（Latin 按词 / CJK 按 2-gram）")
    ap.add_argument("--top-k", type=int, default=5, help="返回文档数（默认 5）")
    ap.add_argument("--section", action="store_true", help="附带命中章节与片段")
    ap.add_argument("--max-tokens", type=int, default=8000,
                    help="单轮注入软上限（D-06，默认 8000；超限截断并提示）")
    ap.add_argument("--corpus-root", default=None)
    ap.add_argument("--index", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = corpus_root(args.corpus_root)
    idx_path = pathlib.Path(args.index) if args.index else \
        pathlib.Path(__file__).resolve().parent.parent / SDK_INDEX_REL
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"doc-search: D-01/D-02 索引不可用：{e}", file=sys.stderr)
        return EXIT_GATE
    if idx.get("schema") != SCHEMA_ID:
        print(f"doc-search: D-02 schema mismatch: {idx.get('schema')}", file=sys.stderr)
        return EXIT_GATE
    kept_from_mirror = merge_kept(idx, root)

    terms = query_terms(" ".join(args.query))
    if not terms:
        print("doc-search: 查询为空", file=sys.stderr)
        return EXIT_ERROR

    # 两趟打分（tf-idf）：先收齐各词在各文档的 tf，才能算 IDF。
    # 为什么不用裸词频：初版实测「资源管理层 规模」把通用词（资源/规模）当主信号，
    # 13/13 全命中且 ResourceOS 排不进 top-3 —— 召回有了，**排序是噪声**。
    # 次线性 tf(1+log) 抑制长文档刷分，IDF 抬高区分度高的词。
    records, degraded = [], []
    for d in idx.get("docs", []):
        p = root / d.get("path", "")
        card = root / d.get("card", "") if d.get("card") else None
        text = ""
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
        else:
            degraded.append(d.get("id"))   # 缺盘降级：仅靠 name/tags/卡片
        card_text = card.read_text(encoding="utf-8", errors="replace") \
            if card and card.exists() else ""
        fields = {"title": d.get("name", ""),
                  "tags": " ".join(d.get("tags", [])),
                  "body": text + " " + card_text}
        rec = {"doc": d, "text": text,
               "tf": {t: {k: count_hits(v, [t]) for k, v in fields.items()}
                      for t in terms}}
        records.append(rec)

    n = max(1, len(records))
    df = {t: sum(1 for r in records
                 if sum(r["tf"][t].values()) > 0) for t in terms}
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in terms}

    scored = []
    for r in records:
        d = r["doc"]
        score = 0.0
        for t in terms:
            tf = r["tf"][t]
            score += (W_TITLE * sublinear(tf["title"])
                      + W_TAGS * sublinear(tf["tags"])
                      + W_BODY * sublinear(tf["body"])) * idf[t]
        if score <= 0:
            continue
        item = {"id": d.get("id"), "name": d.get("name"), "type": d.get("type"),
                "status": d.get("status"), "score": round(score, 2),
                "path": d.get("path"),
                "card": d.get("card"), "tokens_est": d.get("shape", {}).get("tokens_est")}
        sec = section_hits(r["text"], d.get("shape", {}).get("kept", []), terms) \
            if args.section and r["text"] else []
        if sec:
            budget = args.max_tokens
            kept_secs, used = [], 0
            for s in sec:
                if s["tokens_est"] > budget:
                    # 单节就超预算（典型：H1 在文件头，span 覆盖全文）→ 跳过它
                    # 继续试更小的命中节，而不是整体放弃（2026-09-07 实测 ch02 全空）。
                    continue
                if used + s["tokens_est"] > budget:
                    break
                kept_secs.append(s)
                used += s["tokens_est"]
                if not args.json:
                    s["snippet"] = snippet(r["text"], s.get("char_start", 0), terms)
            item["sections"] = kept_secs
            item["sections_tokens"] = used
        scored.append(item)

    scored.sort(key=lambda x: -x["score"])
    top = scored[:max(1, args.top_k)]
    total_tokens = sum(s.get("sections_tokens", 0) for s in top)

    out = {"schema": OUT_SCHEMA, "query": " ".join(args.query), "terms": terms,
           "total_docs": len(idx.get("docs", [])), "hits": len(scored),
           "results": top, "degraded_missing_corpus": degraded,
           "kept_externalized": bool(idx.get("kept_externalized")),
           "kept_from_mirror": kept_from_mirror,
           "budget": {"max_tokens": args.max_tokens,
                      "sections_tokens": total_tokens,
                      "over_budget": total_tokens > args.max_tokens}}

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"# doc-search · {out['query']} · hits {out['hits']}/{out['total_docs']}")
        for r in top:
            print(f"- [{r['score']}] {r['id']} · {r['name']} "
                  f"(~{r['tokens_est']} tok, {r['status']})")
            for s in r.get("sections", []):
                print(f"    § {s['title']} (line {s['line']}, hits {s['hits']})")
                if s.get("snippet"):
                    print(f"      {s['snippet'][:200]}")
        if out["budget"]["over_budget"]:
            print(f"! D-06: 注入 {total_tokens} tok > 软上限 {args.max_tokens}（已截断）")
        if degraded:
            print(f"! 语料缺失（仅卡片/元数据可用）: {degraded}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
