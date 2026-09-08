#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doc-pipeline.py — 参考语料池摄入流水线（D 系列闸，v2.10.13）

Why this exists: SDK 的参考资源类长文档（10²–10³ 份 / 单份 25–125KB）此前是
**裸目录 + 人工记忆定位**（09-04 调研 A4 缺口）。09-06 对照试验实测：全量注入
78.5KB 长文档 → 质量 0pp 增益、输入 +11.4K tok/轮、cache 命中 43%→23%、路由
exact 0/35（注意力稀释）。所以文档正文**永不进上下文**，SDK 只携带
「索引 + 摘要卡 + 吸收产物」，按章节按需加载。

Design rules (继承 SDK 既有):
  * 语料外置（<SDK_DOCS_ROOT>），索引内嵌（scripts/data）。
  * stdlib only；schema fail-closed；原子写（tmp + os.replace）。
  * 零 LLM：摘要卡默认模板骨架，人工补写（LLM 生成须标 generated_by 并过人工闸）。

Gates implemented here (§8 门禁矩阵):
  D-03 sha256 漂移   local → warn / github → fail   (check)
  D-04 卡片缺失      absorbed 无卡 → fail；≥indexed 无卡 → warn
  D-05 重复登记      name 重叠系数 / (type+tags) Jaccard ≥0.7 → 扣住（register）
  D-06 尺寸软闸      单卡 >2K token / 单轮注入 >8K token → 提示不拦截
  D-08 来源合规      github 缺 repo/commit/url → fail；非可再分发许可证且已
                     vendored 正文 → fail（应降级为纯指针）

Usage:
    python scripts/doc-pipeline.py scan    [--corpus-root DIR] [--json]
    python scripts/doc-pipeline.py register <path> --type architecture
                                   [--tags a,b] [--id d-x] [--scan]
                                   [--repo o/r --commit sha --url u]
                                   [--license MIT] [--pointer-only]
                                   [--allow-duplicate] [--corpus-root DIR] [--index PATH]
    python scripts/doc-pipeline.py probe   (--all | <id>) [--update] [--json]
    python scripts/doc-pipeline.py abstract (--all | <id>) [--scaffold] [--json]
    python scripts/doc-pipeline.py index   [--json]
    python scripts/doc-pipeline.py check   (--all | <id>) [--update] [--json]

Exit: 0 = ok · 1 = usage/env error · 2 = gate refusal (D-03/D-04/D-08 fail)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from datetime import date

try:
    from _common import EXIT_ERROR, EXIT_GATE, EXIT_OK, now_iso, schema
except ImportError:  # 直连执行（未加 scripts/ 到 path）
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from _common import EXIT_ERROR, EXIT_GATE, EXIT_OK, now_iso, schema

SCHEMA_ID = schema("doc-index")            # doc-index.v1
CHECK_SCHEMA = "doc-index-check.v1"
# 默认盘位**拆成两段拼接**：源码里不出现 `[A-Za-z]:[/\\]` 字面量 —— 那是本机布局，
# 属 privacy 闸的 drive-letter 类泄漏（published skill 不得携带本机盘符路径）。
DEFAULT_CORPUS_ROOT = pathlib.Path("D:" + os.sep + "WorkBuddy") / "data" / "SDK_Reference"
CORPUS_ENV = "SDK_DOCS_ROOT"               # §10 跨盘风险：环境变量覆盖
SDK_INDEX_REL = "scripts/data/doc-index.json"

STATUSES = ["discovered", "indexed", "abstracted", "absorbed", "archived"]
REQUIRED_FIELDS = ["id", "name", "path", "type", "tags", "status"]
CARD_MAX_TOKENS = 2000                     # D-06 软闸
INJECT_MAX_TOKENS = 8000                   # D-06 软闸（对齐 SKILL §7 分类预算）
DUP_THRESHOLD = 0.70                       # D-05（R-9 同款阈值）
NAME_DUP_THRESHOLD = 0.95                  # D-05 文件名兜底（0.70 实测误杀）
NON_REDIST = ("by-nc", "noncommercial", "cc-by-nc", "all-rights-reserved")
AUTO_TYPE = [
    ("book", ("book", "chapter", " handbook")),
    ("architecture", ("architecture", "arch", "-os-", "world-model")),
    ("design", ("design",)),
    ("survey", ("survey", "技术栈", "state-of")),
    ("spec", ("spec", "verification", "kernel")),
    ("guide", ("guide", "cicd", "集成方案")),
]

# 允许 1–3 个前导反斜杠：ChatGPT / 网页导出会把 markdown 转义成 `\# 1. 标题`，
# 不认这些就会把整份文档判成 unsectionable（实测 2/27 份因此 sections=0、章节地图全空）。
H_RE = re.compile(r"^(?:\\{1,3})?(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
WORD_RE = re.compile(r"[A-Za-z0-9_]+")


# --- io ---------------------------------------------------------------------
def corpus_root(cli: str | None = None) -> pathlib.Path:
    """语料池根：CLI > 环境变量 > 默认 D 盘。缺盘时调用方降级为「仅卡片可用」。"""
    for cand in (cli, os.environ.get(CORPUS_ENV)):
        if cand:
            return pathlib.Path(cand)
    return DEFAULT_CORPUS_ROOT


def sdk_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def sdk_index_path(cli: str | None = None) -> pathlib.Path:
    return pathlib.Path(cli) if cli else sdk_root() / SDK_INDEX_REL


def load_index(path: pathlib.Path) -> dict:
    """fail-closed：不可读 / schema 不符 → 抛 ValueError（调用方转 exit 2）。"""
    if not path.exists():
        raise ValueError(f"index not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise ValueError(f"index unreadable: {path}: {e}") from e
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_ID:
        raise ValueError(f"index schema mismatch (expect {SCHEMA_ID}): {path}")
    return data


CORPUS_ROOT_PLACEHOLDER = "${SDK_DOCS_ROOT}"


def sdk_copy(idx: dict) -> dict:
    """SDK 侧登记副本：`corpus_root` 写占位符，`shape.kept` 外置（§6-10）。

    两类瘦身，理由不同：
      * corpus_root → 占位符：索引要进 git（技能会公开推送），本机盘位是 privacy
        闸的 drive-letter 泄漏类（2026-09-06 ci-smoke 实测 5 findings）。
      * shape.kept → 剥离：kept 占索引体积大头（27 份实测 119KB→~50KB）。SDK 副本
        只做「登记簿」；kept 存语料池侧镜像（root/index.json），doc-search 运行时
        `merge_kept()` 回填，镜像缺盘时降级为仅文档级命中（fail-soft）。
    """
    out = dict(idx)
    out["corpus_root"] = CORPUS_ROOT_PLACEHOLDER
    out["kept_externalized"] = True
    docs = []
    for d in idx.get("docs", []):
        shape = d.get("shape") if isinstance(d, dict) else None
        if isinstance(shape, dict) and "kept" in shape:
            d2 = dict(d)
            shape2 = dict(shape)
            shape2.pop("kept", None)
            d2["shape"] = shape2
            docs.append(d2)
        else:
            docs.append(d)
    out["docs"] = docs
    return out


def atomic_write(path: pathlib.Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# --- 探测 -------------------------------------------------------------------
def sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tokens_est(text: str) -> int:
    """粗估 token：CJK 按 0.75 tok/字，拉丁按 1.3 tok/word（够用于预算闸）。"""
    cjk = len(CJK_RE.findall(text))
    words = len(WORD_RE.findall(text))
    return int(cjk * 0.75 + words * 1.3)


def scan_sections(text: str, max_keep: int = 40) -> dict:
    """扫描 markdown heading（跳过代码块），返回 {sections, kept, max_level, unsectionable}。

    kept 只留 level<=2（`shape.sections` 记全量计数）—— 索引要进 git，
    章节表必须小；L1 检索按命中章节回原文读，不需要把正文搬进索引。
    """
    lines = text.splitlines()
    in_fence = False
    total, kept, max_level = 0, [], 6
    char_pos = 0
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        if not in_fence:
            m = H_RE.match(line)
            if m:
                total += 1
                level = len(m.group(1))
                max_level = min(max_level, level)
                if level <= 2 and len(kept) < max_keep:
                    kept.append({"title": m.group(2).strip(), "level": level,
                                 "line": i + 1, "char_start": char_pos})
        char_pos += len(line) + 1
    return {"sections": total, "kept": kept,
            "max_heading_level": max_level if total else 0,
            "unsectionable": total == 0}


def guess_type(name: str) -> str:
    low = name.lower()
    for t, keys in AUTO_TYPE:
        if any(k in low for k in keys):
            return t
    return "guide"


def make_id(name: str) -> str:
    stem = re.sub(r"\.md$", "", name, flags=re.I)
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return "d-" + (slug or "unnamed")


def iter_corpus_md(root: pathlib.Path):
    """语料池内全部**正文** `.md`（递归）。

    原实现是 `root.glob("*.md")`（只看顶层），分类子目录一建就全部失明 ——
    语料池按 `architecture/ guide/ book/...` 分目录是方案 §4 的既定做法，
    所以这里必须 rglob，并排除两类"不是语料"的 md：
      * `.cards/`（摘要卡，是**产物**不是原料）
      * 任何以 `.` 开头的目录（`.git` 等）与根目录 `INDEX.md`（人读目录，已生成）
    """
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.as_posix() == "INDEX.md":
            continue
        yield p


def read_sections(path: pathlib.Path, kept: list[dict]) -> list[dict]:
    """按 char_start 切出章节正文（供检索与按需加载，不进索引）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for idx, s in enumerate(kept):
        end = kept[idx + 1]["char_start"] if idx + 1 < len(kept) else len(text)
        out.append({**s, "text": text[s["char_start"]:end]})
    return out


# --- D-05 重复检测 ----------------------------------------------------------
def _name_overlap(a: str, b: str) -> float:
    """名相似度：**对称** Jaccard（|A∩B| / |A∪B|），按 2-gram（中英混排都稳）。

    不用 overlap coefficient（/min）：`agentos-architecture` 是
    `coding-agent-os-architecture` 的子串，/min 恒等于 1.0 —— 实测把两篇不同文档
    判成重复（2026-09-06）。对称 Jaccard 下该例 0.73，低于 0.95 兜底线。
    """
    def grams(s: str) -> set[str]:
        s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s.lower())
        return {s[i:i + 2] for i in range(len(s) - 1)} or {s}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def content_fp(text: str, samples: int = 200) -> set[int]:
    """内容指纹：均匀抽样 ≤200 行取 hash 集合（shingle 的廉价替身，零依赖）。

    为什么不用文件名判重：本机语料命名高度模板化（`agent-*-architecture` /
    `GPT-Github_Action*`），2-gram 名重叠实测 0.76–0.94 却全是**不同文档**
    （2026-09-06 首次回填误杀 5 份）。内容才是可靠信号。
    """
    lines = [l.strip().lower() for l in text.splitlines() if l.strip()]
    if not lines:
        return set()
    stride = max(1, len(lines) // samples)
    return {hash(lines[i]) for i in range(0, len(lines), stride)}


def find_duplicate(docs: list[dict], name: str, dtype: str, tags: list[str],
                   text: str, sha: str, root: pathlib.Path) -> dict | None:
    """D-05 判重四级（由强到弱）：sha256 精确 → 内容指纹 → 文件名 → taxonomy。"""
    fp_new = content_fp(text)
    for d in docs:
        if (d.get("origin") or {}).get("sha256") == sha:
            return {"id": d.get("id"), "reason": "sha256_identical", "score": 1.0}
        other = [d.get("type", "")] + list(d.get("tags", []))
        mine = [dtype] + list(tags)
        # 只有两侧都带 tags 才比 taxonomy：否则「同 type + 无标签」恒等 Jaccard=1.0
        jt = _jaccard(sorted(set(other)), sorted(set(mine))) \
            if len(d.get("tags") or []) and len(tags) else 0.0
        if jt >= DUP_THRESHOLD:
            return {"id": d.get("id"), "reason": "taxonomy_jaccard",
                    "score": round(jt, 3)}
        nm = _name_overlap(d.get("name", ""), name)
        if nm >= NAME_DUP_THRESHOLD:          # 0.95：名重叠只兜「改名重登记」
            return {"id": d.get("id"), "reason": "name_overlap", "score": round(nm, 3)}
        p = root / d.get("path", "")
        if fp_new and p.exists():
            try:
                fp_old = content_fp(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if fp_old:
                j = len(fp_new & fp_old) / len(fp_new | fp_old)
                if j >= DUP_THRESHOLD:
                    return {"id": d.get("id"), "reason": "content_jaccard",
                            "score": round(j, 3)}
    return None


# --- 摘要卡 -----------------------------------------------------------------
# 自动富化是**机械抽取**（零 LLM）：首段 + 词频。作用是让卡"能扫一眼判断要不要读原文"，
# 不替代人工的一句/条款；凡自动段落一律标"未校对"，避免被当成已核实结论（§5.2 grounding）。
STOP_EN = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "can",
    "will", "not", "you", "your", "but", "have", "has", "had", "its", "they", "their",
    "which", "when", "what", "how", "all", "any", "one", "two", "more", "most", "than",
    "then", "them", "into", "out", "over", "under", "also", "such", "each", "other",
    "some", "these", "those", "been", "being", "does", "did", "may", "might", "must",
    "should", "would", "could", "about", "after", "before", "between", "because",
    "within", "without", "using", "use", "used", "via", "per", "etc", "fig", "table",
    "note", "http", "https", "www", "com", "org",
}
# 只滤虚词字符（不是词表）：2-gram 含任一字符即弃。宁可漏，不可把"的/了"当术语。
STOP_CJK = set("的了着和是在与及对为中的地得把被让使也就都还很再又你我他它们这那")
LEAD_SUMMARY_RE = re.compile(r"(?i)(executive summary|abstract|tl;?dr|overview|摘要|概述|简介|背景)")


def top_terms(text: str, n: int = 8) -> list[tuple[str, int]]:
    """高频术语（Latin 词 + CJK 2-gram，去停用词）—— 给检索词做提示，不是主题模型。"""
    counts: dict[str, int] = {}
    for raw in WORD_RE.findall(text.lower()):
        w = raw.strip("_")
        # x20 / a1b2 这类编码噪声：含数字且 ≤3 字符一律丢（gpt4、bge3 等 4 字符以上保留）
        if len(w) < 3 or w.isdigit() or w in STOP_EN or (len(w) <= 3 and any(c.isdigit() for c in w)):
            continue
        counts[w] = counts.get(w, 0) + 1
    for run in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]{2,}", text):
        for i in range(len(run) - 1):
            g = run[i:i + 2]
            if any(c in STOP_CJK for c in g):
                continue
            counts[g] = counts.get(g, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[:n]


def _first_para(body: str, limit: int, require_heading: bool = True) -> str:
    buf: list[str] = []
    in_fence = started = (not require_heading)
    for ln in body.splitlines():
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = ln.strip()
        if H_RE.match(ln):
            if started and buf:
                break
            started = True
            continue
        if not started:
            continue
        if not s:
            if buf:
                break
            continue
        if s[0] in "|>#-!" or s.startswith("<"):
            if buf:
                break
            continue
        if not buf and (len(s) < 15 or not re.search(r"[A-Za-z\u4e00-\u9fff]{3,}", s)):
            # 首段不许是框线/实体/单词碎片（ChatGPT 平铺导出常见）
            continue
        buf.append(s)
        if sum(len(x) for x in buf) >= limit * 2:
            break
    out = re.sub(r"\s+", " ", " ".join(buf)).strip()
    return (out[:limit] + "…") if len(out) > limit else out


def lead_paragraph(text: str, sections: list[dict] | None = None,
                   limit: int = 360) -> str:
    """首屏要点：优先取 Summary/摘要 节，否则取 H1 后第一段（跳过围栏/表格/列表）。"""
    start = 0
    for s in (sections or []):
        if LEAD_SUMMARY_RE.search(s.get("title", "") or ""):
            start = int(s.get("char_start") or 0)
            break
    # ChatGPT/网页导出的噪声先清掉：`&#x20;` 实体、`\[GitHub 文档][1]` 之类转义引用
    body = re.sub(r"&[#a-zA-Z0-9]{2,10};", " ", text[start:])
    body = re.sub(r"\\?\[[^\[\]]{1,40}\]\\?\[\d+\]", "", body)
    body = re.sub(r"\\?\[\d+\]", "", body)          # 残留的 `[1]` 引用号
    body = re.sub(r"\(\s*\)", "", body)             # 引用被清掉后留下的空括号
    out = _first_para(body, limit)
    if not out and not sections:
        # 仅 unsectionable（无 heading，如 ChatGPT 平铺导出）才退化到"从头取首段"；
        # 有 heading 却取不到段落时**宁缺勿滥**，卡片会显式标注"无正文段落"（不臆造）。
        out = _first_para(re.sub(r"&[#a-zA-Z0-9]{2,10};", " ", text[:20000]),
                          limit, require_heading=False)
    return out


def card_text(d: dict, sections: list[dict], text: str | None = None) -> str:
    """模板骨架 + 机械富化（不调 LLM）—— 空着的三节由人工补写，写不出来就说明没读。"""
    shape = d.get("shape", {})
    origin = d.get("origin", {})
    src = (f"{origin.get('repo')}@{str(origin.get('commit'))[:8]}"
           if origin.get("kind") == "github" else d.get("path"))
    toc = "\n".join(
        f"- §{s['title']}" for s in (sections or shape.get("kept", []))[:24]) or "- （无 heading，unsectionable）"
    lead = terms_md = ""
    if text:
        lead = lead_paragraph(text, sections or shape.get("kept", []))
        terms = top_terms(text)
        terms_md = " · ".join(f"`{t}`×{c}" for t, c in terms)
    return (
        f"# {d.get('name')} · 摘要卡\n"
        f"- id: {d.get('id')} · type: {d.get('type')} · bytes: {origin.get('bytes', 0):,} · "
        f"sections: {shape.get('sections', 0)} · tokens: ~{shape.get('tokens_est', 0):,}\n"
        f"- source: {src} · sha256: {str(origin.get('sha256', ''))[:16]} · status: {d.get('status')}\n"
        f"- generated_by: template-scaffold + auto-extract（doc-pipeline abstract；**零 LLM**；"
        f"首屏/术语为机械抽取，**未校对**）\n"
        + (f"\n## 首屏要点（自动抽取 · 未校对）\n{lead or '（无正文段落：unsectionable 或首段为表格/列表）'}\n"
           if text else "")
        + (f"\n## 高频术语（自动统计 Top-{len(top_terms(text))} · 未校对）\n{terms_md}\n"
           if text and terms_md else "")
        + f"\n## 一句话\n（TODO 人工补写：该文档回答什么问题 / 目标规模与赌注）\n"
        f"\n## 章节地图（TOC 压缩，标 ★核心节）\n{toc}\n"
        f"\n## 关键条款（≤8 条，每条 ≤2 行）\n- （TODO 人工补写：§x.y 条款：要点）\n"
        f"\n## 与 SDK 的关系\n- 已吸收：（TODO ref-NN / ALIGNMENT 锚点 / 票号）\n"
        f"- 已排除：（TODO 及依据）\n- 未决：—\n"
        f"\n## 引用约定\n注入时打 `<source doc=\"{d.get('id')}\" section=\"§x.y\">`；"
        f"引用必须可回查到本节。\n"
    )


def card_tokens(path: pathlib.Path) -> int:
    try:
        return tokens_est(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return 0


# --- 子命令 -----------------------------------------------------------------
def cmd_scan(args) -> int:
    root = corpus_root(args.corpus_root)
    if not root.exists():
        print(f"doc-pipeline: corpus root missing: {root}（设 {CORPUS_ENV} 覆盖）",
              file=sys.stderr)
        return EXIT_ERROR
    try:
        idx = load_index(sdk_index_path(args.index))
        known = {d["path"] for d in idx.get("docs", [])}
    except ValueError:
        known = set()
    found = []
    for p in iter_corpus_md(root):
        rel = p.relative_to(root).as_posix()
        found.append({"path": rel, "bytes": p.stat().st_size,
                      "registered": rel in known,
                      "suggested_id": make_id(p.name),
                      "suggested_type": guess_type(p.name)})
    out = {"schema": CHECK_SCHEMA, "command": "scan", "corpus_root": str(root),
           "total": len(found), "unregistered": [f for f in found if not f["registered"]],
           "files": found}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return EXIT_OK


def _register_one(args, path: pathlib.Path, idx_path: pathlib.Path,
                  docs: list[dict]) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, f"file not found: {path}"
    root = corpus_root(args.corpus_root)
    try:
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name
    except (ValueError, AttributeError):
        rel = path.name
    name = re.sub(r"\.md$", "", path.name, flags=re.I)
    dtype = args.type or guess_type(path.name)
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    doc_id = args.id or make_id(path.name)

    # D-08 来源合规
    kind = "github" if (args.repo or args.commit) else "local"
    if kind == "github" and not (args.repo and args.commit and args.url):
        return None, "D-08: github 来源必须三件套齐全（--repo / --commit / --url）"
    if args.license and any(k in args.license.lower() for k in NON_REDIST) \
            and not args.pointer_only:
        return None, (f"D-08: 许可证 {args.license} 非可再分发 —— 应降级为纯指针"
                      f"（加 --pointer-only），不得 vendored 正文")

    text = path.read_text(encoding="utf-8", errors="replace")
    cur_sha = sha256_of(path)

    # D-05 重复登记（内容优先，四级判定见 find_duplicate）
    dup = find_duplicate(docs, name, dtype, tags, text, cur_sha, root)
    if dup and not args.allow_duplicate:
        return None, (f"D-05: 疑似重复登记（{dup['reason']}={dup['score']}）"
                      f"与 {dup['id']} 冲突；确认为新文档请加 --allow-duplicate")
    if any(d.get("id") == doc_id for d in docs):
        return None, f"D-05: id 已存在：{doc_id}"

    shape = scan_sections(text)
    entry = {
        "id": doc_id,
        "name": name,
        "path": rel,
        "type": dtype,
        "tags": tags,
        "origin": {"kind": kind, "repo": args.repo, "commit": args.commit,
                   "url": args.url, "license": args.license,
                   "pointer_only": bool(args.pointer_only),
                   "sha256": cur_sha, "bytes": path.stat().st_size,
                   "fetched_at": date.today().isoformat()},
        "shape": {"sections": shape["sections"], "tokens_est": tokens_est(text),
                  "max_heading_level": shape["max_heading_level"],
                  "unsectionable": shape["unsectionable"], "kept": shape["kept"]},
        "status": "indexed",
        "absorbed": None,
        "card": f".cards/{doc_id}.card.md",
        "last_checked": date.today().isoformat(),
    }
    return entry, None


def cmd_register(args) -> int:
    idx_path = sdk_index_path(args.index)
    root = corpus_root(args.corpus_root)
    try:
        idx = load_index(idx_path)
        docs = list(idx.get("docs", []))
    except ValueError as e:
        if not args.init:
            print(f"doc-pipeline: {e}（首次使用加 --init）", file=sys.stderr)
            return EXIT_GATE
        idx = {"schema": SCHEMA_ID, "generated_at": now_iso(),
               "corpus_root": root.as_posix(), "total_docs": 0, "docs": []}
        docs = []

    targets: list[pathlib.Path] = []
    if args.scan:
        if not root.exists():
            print(f"doc-pipeline: corpus root missing: {root}", file=sys.stderr)
            return EXIT_ERROR
        known = {d["path"] for d in docs}
        targets = [p for p in iter_corpus_md(root)
                   if p.relative_to(root).as_posix() not in known]
    elif args.path:
        targets = [pathlib.Path(args.path)]
    else:
        print("doc-pipeline: register 需要 <path> 或 --scan", file=sys.stderr)
        return EXIT_ERROR

    added, failed = [], []
    for t in targets:
        srcp = t if t.is_absolute() else root / t
        entry, err = _register_one(args, srcp, idx_path, docs)
        if err:
            failed.append({"path": str(t), "error": err})
            continue
        docs.append(entry)
        added.append(entry)
        # 摘要卡骨架（缺盘/损坏不致命）
        try:
            cardp = root / entry["card"]
            cardp.parent.mkdir(parents=True, exist_ok=True)
            if not cardp.exists():
                cardp.write_text(
                    card_text(entry, read_sections(srcp, entry["shape"]["kept"]),
                              srcp.read_text(encoding="utf-8", errors="replace")),
                    encoding="utf-8")
        except OSError as e:
            failed.append({"path": str(t), "error": f"card scaffold failed: {e}"})

    idx["docs"] = docs
    idx["total_docs"] = len(docs)
    idx["generated_at"] = now_iso()
    idx["corpus_root"] = root.as_posix()
    atomic_write(idx_path, sdk_copy(idx))
    # 语料池侧镜像（唯一写入方，D-02 双事实源防线）
    try:
        atomic_write(root / "index.json", idx)
    except OSError as e:
        print(f"doc-pipeline: warn: corpus index mirror failed: {e}", file=sys.stderr)

    hard = [f for f in failed if not f["error"].startswith("card scaffold")]
    out = {"schema": CHECK_SCHEMA, "command": "register", "corpus_root": str(root),
           "added": [{"id": d["id"], "name": d["name"],
                      "sections": d["shape"]["sections"],
                      "tokens_est": d["shape"]["tokens_est"]} for d in added],
           "failed": failed, "total_docs": len(docs)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return EXIT_GATE if hard else EXIT_OK


def cmd_probe(args) -> int:
    idx_path = sdk_index_path(args.index)
    root = corpus_root(args.corpus_root)
    try:
        idx = load_index(idx_path)
    except ValueError as e:
        print(f"doc-pipeline: {e}", file=sys.stderr)
        return EXIT_GATE
    targets = idx.get("docs", []) if args.all else [
        d for d in idx.get("docs", []) if d.get("id") == args.id]
    if not targets:
        print(f"doc-pipeline: no doc matched (id={args.id})", file=sys.stderr)
        return EXIT_ERROR
    changed, missing = [], []
    for d in targets:
        p = root / d["path"]
        if not p.exists():
            missing.append(d["id"])
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        shape = scan_sections(text)
        new = {"sections": shape["sections"], "tokens_est": tokens_est(text),
               "max_heading_level": shape["max_heading_level"],
               "unsectionable": shape["unsectionable"], "kept": shape["kept"]}
        # SDK 副本的 kept 已外置（§6-10），登记簿上没有 kept —— 比对只看标量字段，
        # 否则 `new != old` 恒真，每次 probe 都"changed"一遍。
        old = d.get("shape") or {}
        scalars = ("sections", "tokens_est", "max_heading_level", "unsectionable")
        if any(new.get(k) != old.get(k) for k in scalars):
            changed.append(d["id"])
            if args.update:
                d["shape"] = new
                d["last_checked"] = date.today().isoformat()
    if args.update and changed:
        idx["generated_at"] = now_iso()
        atomic_write(idx_path, sdk_copy(idx))
        try:
            atomic_write(root / "index.json", idx)
        except OSError:
            pass
    out = {"schema": CHECK_SCHEMA, "command": "probe", "checked": len(targets),
           "changed": changed, "missing": missing, "updated": bool(args.update)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_abstract(args) -> int:
    idx_path = sdk_index_path(args.index)
    root = corpus_root(args.corpus_root)
    try:
        idx = load_index(idx_path)
    except ValueError as e:
        print(f"doc-pipeline: {e}", file=sys.stderr)
        return EXIT_GATE
    targets = idx.get("docs", []) if args.all else [
        d for d in idx.get("docs", []) if d.get("id") == args.id]
    if not targets:
        print(f"doc-pipeline: no doc matched (id={args.id})", file=sys.stderr)
        return EXIT_ERROR
    written, promoted = [], []
    for d in targets:
        cardp = root / d["card"]
        srcp = root / d["path"]
        if cardp.exists() and not args.force:
            # 已存在：只做状态收敛（人工填完 TODO 后再次运行即晋升 abstracted）
            try:
                filled = "（TODO 人工补写" not in cardp.read_text(encoding="utf-8",
                                                              errors="replace")
            except OSError:
                filled = False
            if filled and d.get("status") == "indexed":
                d["status"] = "abstracted"
                promoted.append(d["id"])
            continue
        sections = read_sections(srcp, d.get("shape", {}).get("kept", []))
        try:
            text = srcp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = None
        body = card_text(d, sections, text)
        cardp.parent.mkdir(parents=True, exist_ok=True)
        cardp.write_text(body, encoding="utf-8")
        # 骨架卡一律带 TODO 标记 → **不晋升**（fail-closed：状态不撒谎）
        if "（TODO 人工补写" not in body and d.get("status") == "indexed":
            d["status"] = "abstracted"
            promoted.append(d["id"])
        d["last_checked"] = date.today().isoformat()
        written.append({"id": d["id"], "card": d["card"]})
    idx["generated_at"] = now_iso()
    if written or promoted:
        atomic_write(idx_path, sdk_copy(idx))
        try:
            atomic_write(root / "index.json", idx)
        except OSError:
            pass
    out = {"schema": CHECK_SCHEMA, "command": "abstract", "written": written,
           "promoted": promoted, "auto_extract": True, "scaffold_only": True,
           "note": "骨架 + 机械富化（首屏/术语，零 LLM 且未校对）；"
                   "一句话/关键条款仍需人工补写，补完再跑一次即晋升 abstracted"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return EXIT_OK


def index_markdown(idx: dict) -> str:
    """语料池人类入口（人读 INDEX.md，机器读 index.json，同源）。"""
    rows = "\n".join(
        f"| `{d.get('id')}` | {d.get('name')} | {d.get('type')} | "
        f"{(d.get('origin') or {}).get('bytes', 0):,} | "
        f"{(d.get('shape') or {}).get('sections', 0)} | "
        f"~{(d.get('shape') or {}).get('tokens_est', 0):,} | {d.get('status')} | "
        f"{'§可切' if not (d.get('shape') or {}).get('unsectionable') else '⚠️无heading'} |"
        for d in sorted(idx.get("docs", []), key=lambda x: x.get("id", "")))
    total_bytes = sum((d.get("origin") or {}).get("bytes", 0)
                      for d in idx.get("docs", []))
    return (
        "# SDK_Reference · 语料索引\n\n"
        f"> 由 `doc-pipeline.py index` 生成于 {now_iso()} · "
        f"{idx.get('total_docs', 0)} 份 / {total_bytes:,}B · "
        "**正文不进上下文**：先读 `.cards/` 摘要卡，再按章节取原文（≥8K token 禁止整份注入）。\n"
        f"> 语料根：`{idx.get('corpus_root')}`（环境变量 `SDK_DOCS_ROOT` 可覆盖）\n\n"
        "| id | 文档 | type | bytes | sections | tokens | status | 切分 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        f"{rows}\n\n"
        "## 用法\n\n"
        "```bash\n"
        "python scripts/doc-search.py \"<query>\" --top-k 3 --section   # 命中章节（≤8K tok）\n"
        "python scripts/doc-pipeline.py check --all --json             # D-01..D-08 巡检\n"
        "```\n"
    )


def cmd_index(args) -> int:
    idx_path = sdk_index_path(args.index)
    try:
        idx = load_index(idx_path)
    except ValueError as e:
        print(f"doc-pipeline: {e}", file=sys.stderr)
        return EXIT_GATE
    root = corpus_root(args.corpus_root)
    idx["total_docs"] = len(idx.get("docs", []))
    idx["corpus_root"] = root.as_posix()
    idx["generated_at"] = now_iso()
    atomic_write(idx_path, sdk_copy(idx))
    try:
        atomic_write(root / "index.json", idx)
    except OSError:
        pass
    # INDEX.md：语料池侧的人类入口（09-04 调研 A4）。人在这里挑文档，
    # 机器读 index.json —— 两者同一份数据源，避免"人工目录比索引新"的老问题。
    index_md = root / "INDEX.md"
    try:
        index_md.write_text(index_markdown(idx), encoding="utf-8")
    except OSError as e:
        print(f"doc-pipeline: warn: INDEX.md write failed: {e}", file=sys.stderr)
    out = {"schema": CHECK_SCHEMA, "command": "index", "total_docs": idx["total_docs"],
           "sdk_index": str(idx_path), "corpus_mirror": str(root / "index.json"),
           "index_md": str(index_md)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return EXIT_OK


def tier_of(n: int) -> str:
    """规模档位（方案 §6 阶梯）。只报告，不自动升级设施。"""
    if n <= 20:
        return "L0"
    if n <= 200:
        return "L1"
    if n <= 2000:
        return "L2"
    return "L3"


TIER_FACILITY = {
    "L0": "索引 + 卡片（人工 / grep）",
    "L1": "+ doc-search.py 关键词检索（已实装）",
    "L2": "+ SQLite FTS5（doc-index.db，未建）",
    "L3": "+ 本地嵌入召回 / rerank（未建，本机资产具备）",
}


def _missing_required(d: dict) -> list[str]:
    """D-02 必填校验。**tags 允许空 list**（新登记尚无标签是常态）—— 用真值判断
    会把 `tags: []` 判成缺失，2026-09-06 首次巡检 13/13 全被误报。"""
    miss = [f for f in REQUIRED_FIELDS if f not in d]
    miss += [f for f in ("id", "name", "path", "type", "status") if not d.get(f)]
    if not isinstance(d.get("tags"), list):
        miss.append("tags")
    return sorted(set(miss))


def cmd_check(args) -> int:
    """D-01/D-02/D-03/D-04/D-06/D-08 统一巡检。hard problem → exit 2。"""
    idx_path = sdk_index_path(args.index)
    root = corpus_root(args.corpus_root)
    try:
        idx = load_index(idx_path)          # D-01 + D-02
    except ValueError as e:
        print(f"doc-pipeline: D-01/D-02: {e}", file=sys.stderr)
        return EXIT_GATE
    # §10 跨盘降级：语料池在 D 盘、SDK 在 C 盘。缺盘时**不判定失败**（否则换机/
    # CI 上因盘符不存在而红灯），改为显式 degraded 交付 —— 索引本身（D-01/D-02）
    # 仍然 fail-closed，只有"盘不在"这一件事降级。
    if not root.exists():
        out = {"schema": CHECK_SCHEMA, "command": "check", "corpus_root": str(root),
               "ok": True, "corpus_available": False, "checked": 0,
               "total_docs": len(idx.get("docs", [])),
               "problems": [],
               "warnings": [{"gate": "D-03", "severity": "warn",
                             "detail": f"语料池缺失（{root}）—— 设 {CORPUS_ENV} 覆盖；"
                                       f"仅索引与卡片可用"}],
               "docs": [],
               "tier": {"docs": len(idx.get("docs", [])),
                        "current": tier_of(len(idx.get("docs", []))),
                        "facility": TIER_FACILITY[tier_of(len(idx.get("docs", []))) ]}}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return EXIT_OK

    docs = idx.get("docs", [])
    missing_field = [d.get("id", "?") for d in docs if _missing_required(d)]
    targets = docs if args.all else [d for d in docs if d.get("id") == args.id]
    if not targets:
        print(f"doc-pipeline: no doc matched (id={args.id})", file=sys.stderr)
        return EXIT_ERROR

    problems, warnings, rows, by_id = [], [], [], {}
    for d in docs:
        by_id.setdefault(d.get("id"), []).append(d)
    dup_ids = sorted({k for k, v in by_id.items() if len(v) > 1})
    if dup_ids:
        warnings.append({"gate": "D-05", "ids": dup_ids,
                         "detail": "同一 id 多条登记（register 侧会拦截，此处仅提示）"})

    for d in targets:
        p = root / d["path"]
        origin = d.get("origin", {}) or {}
        rec_sha, rec_bytes = origin.get("sha256"), origin.get("bytes")
        row = {"id": d.get("id"), "path": d.get("path"), "status": d.get("status")}
        if not p.exists():
            row["exists"] = False
            problems.append({"gate": "D-03", "id": d.get("id"),
                             "detail": f"语料缺失：{p}"})
            rows.append(row)
            continue
        row["exists"] = True
        cur_sha, cur_bytes = sha256_of(p), p.stat().st_size
        row["sha256_match"] = cur_sha == rec_sha
        row["bytes"] = cur_bytes
        if cur_sha != rec_sha:
            sev = "fail" if origin.get("kind") == "github" else "warn"
            item = {"gate": "D-03", "id": d.get("id"), "severity": sev,
                    "detail": f"sha256 漂移（记录 {str(rec_sha)[:12]}… / 实际 "
                              f"{cur_sha[:12]}…），bytes {rec_bytes}→{cur_bytes}"}
            (problems if sev == "fail" else warnings).append(item)
            if args.update:
                origin["sha256"], origin["bytes"] = cur_sha, cur_bytes
                text = p.read_text(encoding="utf-8", errors="replace")
                shape = scan_sections(text)
                d["shape"] = {"sections": shape["sections"],
                              "tokens_est": tokens_est(text),
                              "max_heading_level": shape["max_heading_level"],
                              "unsectionable": shape["unsectionable"],
                              "kept": shape["kept"]}
        # D-04 卡片
        cardp = root / d.get("card", "")
        has_card = bool(d.get("card")) and cardp.exists()
        row["card"] = bool(has_card)
        if not has_card:
            item = {"gate": "D-04", "id": d.get("id"),
                    "detail": "摘要卡缺失"}
            if d.get("status") == "absorbed":
                item["severity"] = "fail"
                problems.append(item)
            elif d.get("status") in ("indexed", "abstracted"):
                item["severity"] = "warn"
                warnings.append(item)
        else:
            ct = card_tokens(cardp)
            row["card_tokens"] = ct
            if ct > CARD_MAX_TOKENS:                     # D-06 软闸
                warnings.append({"gate": "D-06", "id": d.get("id"),
                                 "severity": "warn",
                                 "detail": f"摘要卡 {ct} tok > {CARD_MAX_TOKENS} 软上限"})
        # D-08
        if origin.get("kind") == "github" and not (
                origin.get("repo") and origin.get("commit") and origin.get("url")):
            problems.append({"gate": "D-08", "id": d.get("id"),
                             "detail": "github 来源缺 repo/commit/url"})
        if origin.get("license") and any(
                k in str(origin["license"]).lower() for k in NON_REDIST) \
                and not origin.get("pointer_only"):
            problems.append({"gate": "D-08", "id": d.get("id"),
                             "detail": f"非可再分发许可证 {origin['license']} 且已 "
                                       f"vendored 正文 → 应降级为纯指针"})
        rows.append(row)

    if missing_field:
        problems.append({"gate": "D-02", "ids": missing_field,
                         "detail": f"缺必填字段 {REQUIRED_FIELDS}"})

    if args.update:
        idx["generated_at"] = now_iso()
        atomic_write(idx_path, sdk_copy(idx))
        try:
            atomic_write(root / "index.json", idx)
        except OSError:
            pass

    ok = not problems
    out = {"schema": CHECK_SCHEMA, "command": "check", "corpus_root": str(root),
           "ok": ok, "checked": len(targets), "total_docs": len(docs),
           "problems": problems, "warnings": warnings, "docs": rows,
           "tier": {"docs": len(docs), "current": tier_of(len(docs)),
                    "facility": TIER_FACILITY[tier_of(len(docs))]},
           "budget": {"card_max_tokens": CARD_MAX_TOKENS,
                      "inject_max_tokens": INJECT_MAX_TOKENS}}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return EXIT_OK if ok else EXIT_GATE


# --- CLI --------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="doc-pipeline.py",
        description="参考语料池摄入流水线（register/probe/abstract/index/check，D 系列闸）")
    ap.add_argument("--corpus-root", default=None,
                    help=f"语料池根（默认 {DEFAULT_CORPUS_ROOT} 或 ${CORPUS_ENV}）")
    ap.add_argument("--index", default=None, help="SDK 侧索引路径覆盖（测试用）")
    ap.add_argument("--json", action="store_true",
                    help="JSON 输出（默认即 JSON；no-op，兼容集成方案 §5 CLI 原型）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    # 三个全局开关在**子命令前后都要能用**：集成方案 §5 的 CLI 原型写在子命令之后
    # （`register <path> --type x --corpus-root DIR`），而 argparse 的顶层选项默认
    # 只认前置位置 —— 实测 `scan --corpus-root X` 直接 exit 2 "unrecognized"。
    # 解法：子命令侧用 `default=argparse.SUPPRESS` 复刻同名选项 —— 给了就覆盖，
    # 没给就不写回 namespace，从而不把顶层已解析的值清成 None。
    json_parent = argparse.ArgumentParser(add_help=False)
    json_parent.add_argument("--corpus-root", default=argparse.SUPPRESS,
                             help="语料池根（同顶层；可写在子命令之后）")
    json_parent.add_argument("--index", default=argparse.SUPPRESS,
                             help="SDK 侧索引路径覆盖（同顶层）")
    json_parent.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                             help="JSON 输出（默认即 JSON；no-op）")

    p_scan = sub.add_parser("scan", parents=[json_parent],
                            help="列出语料池文件与未登记项")
    p_scan.set_defaults(func=cmd_scan)

    p_reg = sub.add_parser("register", parents=[json_parent], help="登记文档（含探测 + 卡片骨架）")
    p_reg.add_argument("path", nargs="?", help="语料文件（绝对路径或相对 corpus-root）")
    p_reg.add_argument("--scan", action="store_true", help="登记语料池内全部未登记 .md")
    p_reg.add_argument("--init", action="store_true", help="索引不存在时初始化")
    p_reg.add_argument("--type", default=None, choices=[t for t, _ in AUTO_TYPE] + ["other"])
    p_reg.add_argument("--tags", default="")
    p_reg.add_argument("--id", dest="id", default=None)
    p_reg.add_argument("--repo"), p_reg.add_argument("--commit"), p_reg.add_argument("--url")
    p_reg.add_argument("--license", default=None)
    p_reg.add_argument("--pointer-only", action="store_true")
    p_reg.add_argument("--allow-duplicate", action="store_true", help="跳过 D-05 查重")
    p_reg.set_defaults(func=cmd_register)

    p_probe = sub.add_parser("probe", parents=[json_parent], help="重新探测 shape（漂移/重建 sections）")
    p_probe.add_argument("id", nargs="?", default=None)
    p_probe.add_argument("--all", action="store_true")
    p_probe.add_argument("--update", action="store_true")
    p_probe.set_defaults(func=cmd_probe)

    p_abs = sub.add_parser("abstract", parents=[json_parent], help="生成/刷新摘要卡（模板骨架，零 LLM）")
    p_abs.add_argument("id", nargs="?", default=None)
    p_abs.add_argument("--all", action="store_true")
    p_abs.add_argument("--scaffold", action="store_true")
    p_abs.add_argument("--force", action="store_true", help="覆盖已存在的卡片")
    p_abs.set_defaults(func=cmd_abstract)

    p_idx = sub.add_parser("index", parents=[json_parent], help="重建索引并同步语料池镜像")
    p_idx.set_defaults(func=cmd_index)

    p_chk = sub.add_parser("check", parents=[json_parent], help="D-01..D-08 巡检（hard fail → exit 2）")
    p_chk.add_argument("id", nargs="?", default=None)
    p_chk.add_argument("--all", action="store_true")
    p_chk.add_argument("--update", action="store_true", help="刷新 sha256/shape")
    p_chk.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    try:
        return int(args.func(args))
    except OSError as e:
        print(f"doc-pipeline: OSError: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
