# ref-26 — 参考语料池（doc-index.v1 / D 系列闸）

> v2.10.13 · 2026-09-06 · 来源：《集成方案-SDK参考文档资源池-2026-09-06》
> 加载时机：**需要引用 SDK 参考资源类长文档时**。日常编码任务不需要读本文件。

## 0. 一条硬结论（别违反）

**语料外置、索引内嵌、分级加载**：文档正文永不在 SDK 内，永不进稳定前缀，永不整份注入。

证据（09-06 对照试验，175 runs，Wilcoxon p<0.0001）：全量注入 78.5KB → 质量 **0pp 增益**、
输入 **+11.4K tok/轮**、cache 命中 43%→23%、路由 exact **0/35**；而 1.8KB 静态路由表
exact 12/35。**"多给上下文"在这类语料上是负收益。**

## 1. 布局

```text
<SDK_DOCS_ROOT>\      ← 语料池（外置；环境变量 SDK_DOCS_ROOT 可覆盖）
├── index.json                        ← 权威索引（语料池侧镜像）
├── INDEX.md                          ← 人读目录（`doc-pipeline index` 生成）
├── .cards\d-<id>.card.md             ← 摘要卡（≤2K token/份）
├── <type>\<doc>.md                   ← 正文按 type 分子目录（2026-09-07 已迁移，见 §6-11）
└── book\<repo>\<chapter>.md          ← 书籍类按仓库分子目录（`iter_corpus_md` 已递归）

~/.workbuddy/skills/user-vibe_coding-sdk-moe\
├── scripts\data\doc-index.json       ← 登记副本（fail-closed；唯一写入方=doc-pipeline）
├── scripts\doc-pipeline.py           ← 摄入流水线 scan/register/probe/abstract/index/check
└── scripts\doc-search.py             ← L1 检索（tf-idf，stdlib）
```

## 2. 加载四级（渐进披露）

`元数据 → 摘要卡（≤2K）→ 命中章节（≤8K）→ 全文（禁止）`

摘要卡结构（v2.10.15 起）：`首屏要点（自动·未校对）` + `高频术语 Top-8（自动·未校对）`
+ `一句话` + `章节地图` + `关键条款` + `与 SDK 的关系`。前两节是**机械抽取**、后四节人工补写；
凡自动节一律标「未校对」，不得当作已核实结论（§5.2 grounding）。

- 单文档 ≥8K token 必须切章节加载；`unsectionable` 文档（无 heading，如 ChatGPT 平铺导出）
  只走人工卡，**不失败退出**。
- 注入片段打 `<source doc="d-xxx" section="§5.2" sha256="…">`（§5.2 grounding，机器可校验）。

## 3. 命令

```bash
python scripts/doc-pipeline.py scan                       # 语料池清点（含未登记项）
python scripts/doc-pipeline.py register --scan --init      # 首次回填 / 增量登记
python scripts/doc-pipeline.py register <path> --type architecture --tags "scale,registry"
python scripts/doc-pipeline.py register <path> --repo o/r --commit <sha> --url <u>   # GitHub 来源须三件套
python scripts/doc-pipeline.py register <path> --type book --id d-aabook-en-ch02-context-engineering \
        --tags "ai-agent-book,context-engineering" --repo bojieli/ai-agent-book --commit <sha> \
        --url <u> --license Apache-2.0        # 书籍按章登记，逐章给不同 tags（见 §6-7）
python scripts/doc-pipeline.py check --all --json [--update]   # D-01..D-08（hard fail → exit 2）
python scripts/doc-search.py "resource capability registry" --top-k 3 --section
```

`--corpus-root` / `--index` 可写在子命令**前后任一位置**（argparse SUPPRESS 复刻）。

## 4. 门禁矩阵（D 系列）

| 编号 | 闸 | 判据 | 执行者 |
|---|---|---|---|
| D-01 | 索引存在性 | `doc-index.json` 缺失/不可解析 → exit 2 | selfcheck-static（docs 段）+ doc-pipeline |
| D-02 | schema 合规 | 非 `doc-index.v1` / 缺必填字段（`tags` 允许空 list）→ exit 2 | 同上 |
| D-03 | sha256 漂移 | local → warn；github → fail；语料缺失 → fail | `doc-pipeline check` |
| D-03′ | 跨盘降级 | 语料池根不存在 → warn + `corpus_available:false`，**不判失败** | 同上 |
| D-04 | 卡片缺失 | `absorbed` 无卡 → fail；`indexed/abstracted` 无卡 → warn | 同上 |
| D-05 | 重复登记 | 四级：sha256 精确 → 内容指纹 Jaccard ≥0.7 → 文件名 Jaccard ≥0.95 → taxonomy Jaccard ≥0.7 | `register`（`--allow-duplicate` 放行） |
| D-06 | 尺寸软闸 | 单卡 >2K tok / 单轮注入 >8K tok → 提示不拦截 | `check` / `doc-search --max-tokens` |
| D-07 | 脚本登记 | `doc-*.py` 未登记 toolstack → exit 2 | selfcheck-static（既有） |
| D-08 | 来源合规 | GitHub 缺 repo/commit/url → fail；非可再分发许可证且已 vendored 正文 → fail（应 `--pointer-only`） | `register` / `check` |

## 5. 规模阶梯（不自动升级，人工确认）

| 档 | 份数 | 检索 |
|---|---|---|
| L0 | ≤20 | 人工 / grep / `doc-search` |
| L1 | 20–200（**当前 26，2026-09-07 跨线**） | `doc-search.py` tf-idf（已实装，L0 亦可提前用） |
| L2 | 200–2000 | + SQLite FTS5（`doc-index.db`） |
| L3 | >2000 | + 本地嵌入召回 / bge-reranker（本机已有资产，届时才评估） |

`check --all` 会打印 `tier{current, facility}`；跨档时**只提示不自动升级**（ResourceOS §34：
设施升级须人工确认）。L1 设施（`doc-search.py`）已实装，故 26 份跨线无需新增组件。

## 6. 踩过的坑（改本子系统前先读）

1. **D-05 用文件名判重会误杀**：本机命名模板化（`agent-*-architecture`、`GPT-Github_Action*`），
   2-gram 名重叠 0.76–0.94 却是不同文档；且 `overlap/min` 对子串恒为 1.0。→ 内容优先（sha256 + 内容指纹），
   文件名只兜底且阈值提到 0.95 对称 Jaccard。
2. **必填校验别用真值**：`tags: []` 是合法的，"not d.get('tags')" 会 13/13 全误报。
3. **裸词频排序是噪声**：初版 `资源管理层 规模` 13/13 全命中且目标文档进不了 top-3；
   改次线性 tf(1+log) × IDF 后 top-1 命中 4/4（抽样）。
4. **语料是英文为主**（架构类 8 份 CJK 占比 0.0，GPT 导出类才是中文）—— 检索词要跟着语料语言走。
5. **检索是 T2 档**（分类/匹配，思考 OFF），不要给它开推理预算。
6. **跨语言查询无解**：tf-idf 是纯字面匹配，无跨语言映射。实测「资源管理层 规模」在全库
   **精确串 0 命中**（目标 `ResourceOS-Architecture.md` 是英文，CJK 计数全 0）—— 这不是回归，
   是查询词与语料语言不匹配。判据：先 `grep` 目标串，0 命中就换语料语言再查。
7. **整本书不能当一份登记**：单份 1.3MB / ~26 万 token 远超 8K 切分上限，且检索粒度退化为
   「整本命中」。按章拆 13 份后 top-1 命中 5/5（context / multi-agent / tools / eval / post-training）。
8. **同书各章 tags 必须互不相同**：D-05 末级是 `(type+tags)` Jaccard ≥0.7。13 章若共用同一组
   tags，两两 Jaccard = 1.0，第 2 章起全被扣住。做法：1 个书级公共 tag + 1–2 个**唯一**章节 tag。
9. **子目录必须递归**：初版 `root.glob("*.md")` 只看顶层，`book/ai-agent-book-en/` 一建就全部失明。
   现 `iter_corpus_md` 用 `rglob` 并排除 `.cards/`、点目录、根 `INDEX.md`（产物不是原料）。
10. **SDK 侧索引线性膨胀**：13→26 份时 `scripts/data/doc-index.json` 69KB→102KB（≈3.9KB/份，
    `shape.kept` 占大头）；27 份重扫后 119KB。按此斜率 L2（200 份）≈780KB 会随技能包分发 ——
    **跨 L2 前必须把 `kept` 外置**到语料池镜像，SDK 副本只留 `id/name/type/tags/card/tokens_est`。
11. **转义标题 → 假 unsectionable**：ChatGPT / 网页导出把 `#` 写成 `\#`，`scan_sections` 认不出 →
    整份 `sections=0`、章节地图全空、卡片退化为「无正文段落」（实测 2/27 份中招）。
    修法：`H_RE` 允许 1–3 个前导反斜杠。改完**必须** `probe --all --update` 重扫 shape
    （sha256 不变，probe 只比对 shape，可放心跑）。
12. **自动富化的边界**：首屏要点/高频术语是词频与首段的机械抽取，**取不到就写「无正文段落」，
    不臆造**；只有 `unsectionable` 文档才退化到「从头取首段」（有 heading 却取不到 → 宁缺勿滥）。
    另需清噪声：`&#x20;` 实体、`\[ref][1]` 转义引用、ASCII 框线、纯表格行。
13. **状态不撒谎（fail-closed）**：骨架卡带 `（TODO 人工补写` 标记 → **不晋升** `abstracted`；
    人工补完后再跑一次 `abstract`（**不要** `--force`，否则覆盖人工内容）即自动晋升。
14. **别在 ci-smoke 运行中改 SDK 文件**：robustness 的 F-63 用例会**嵌套启动** ci-smoke →
    嵌套 version-check 读七戳一致性。v2.10.16 实录：后台全量 ci-smoke 跑到 robustness 步时
    版本字符串刚 bump（v2.10.16）而 CHANGELOG 未写 → 嵌套 exit 2 → F-63 红灯。
    保留机制本身（left=7/最旧清理/新报告在）实测完好。规程：**先改完所有 SDK 文件（含
    CHANGELOG）再跑 ci-smoke**，运行窗口内 SDK 目录只读。
15. **补写卡片时同步改卡片头部 status**：`abstract` 只晋升**索引**状态，卡内 `· status: X`
    戳是写卡时的快照。批量补写脚本应顺带把戳改成终态（absorbed/abstracted），
    且仅当卡内已零 TODO（fail-closed：有 TODO 就别改戳，让状态继续撒谎前先修卡）。

## 7. 书籍类语料入库（2026-09-07 实践：bojieli/ai-agent-book）

- **定版**：`--commit <sha>` 钉死版本（`006d2368361e5dd35b7d94a7791ce640b5ef1b67`），
  `origin.kind=github` + 三件套齐全 → D-03 漂移按 **fail**（local 来源才 warn）。
- **许可证**：Apache-2.0 → 可 vendored 正文，`pointer_only=false`；若遇 CC BY-NC / All Rights
  Reserved → 必须 `--pointer-only`，只留指针不落正文（D-08）。
- **语种**：以 `book-en/` 为基准（英文版），登记 id 统一带 `-en-`，避免与后续中文版撞 id。
  **book-zh 决策（2026-09-07，v2.10.16）：不入库** —— 用户既定 "en 版本为基准"；中译版与英版
  语义重复（D-05 指纹级近重复 + 同书双版本 token 翻倍无检索增益）。需要中英对照时走**检索期
  翻译**（命中英文章节后按需译出），不做双份入库。
- **命名**：保留仓库内原文件名（`chapter2.md`）以便回溯；语义靠 `id` + `tags` +
  `shape.kept[0].title`（= 章节 H1，如 `Context Engineering`）。
- **粒度现实**：`kept` 只收 level≤2，本书正文多为 H3/H4 → 13 章共 335 heading 只留 111 条，
  `--section` 回片偏粗（8K 截断）。要更细需放宽 `scan_sections` 的 level 上限 —— **代价是索引
  继续膨胀**（见 §6-10），L2 之前不建议。
