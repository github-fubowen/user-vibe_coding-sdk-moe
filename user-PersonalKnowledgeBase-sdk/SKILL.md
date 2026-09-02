---
name: user-PersonalKnowledgeBase-sdk
description: Use when the user says "知识库", "knowledge base", "KB", "PKOS", "personal knowledge", "个人知识管理", or asks to 采集/抓取/导入/整理/归档/检索/问答/总结/备份 knowledge content, or explicitly asks to start a knowledge-base session or manage their knowledge tools. Also use when the user describes a task about collecting, organizing, retrieving, creating, maintaining, or backing up knowledge/memory/notes/documents. Routes to the right skill stack based on knowledge task mode (ingest / organize / retrieve / create / maintain / build). PKOS v2.0 (MoE-optimized).
---

# Personal Knowledge Base SDK v2.0 — 一键加载知识库技能栈（MoE 优化版）

Activate the right knowledge tool stack before touching knowledge content. Load only what the task needs — not everything.

> **版本历史**：完整 changelog（v1.0–v1.11）见 `CHANGELOG.md`（渐进披露，不进热路径）。
>
> **v2.0 差异（vs v1.11，2026-08-22）**：MoE 层接入（对齐 user-vibe_coding-sdk-moe）—— ① 强制英文思维链（thinking 零 CJK）· ② 思考预算按任务分档 · ③ KB LLM 模型路由矩阵（LongCat-2.0 默认链已固定）· ④ Token 闸门 G1-G6 · ⑤ 质量闸门（输出规范 + 来源纪律 grounding）· ⑥ 渐进披露（changelog 移出热路径 → `CHANGELOG.md`）· ⑦ Build 路由改 `user-vibe_coding-sdk-moe`。领域内容（Mode/Path/Tool Routing/Registry/Rules 1-13）100% 保留。

---

## MoE-2. 语言规则与思考预算（非协商，进入本 SDK 即生效）

- **⛔ THINK IN ENGLISH**：thinking 链一律英文骨架 `[GOAL] → [CONSTRAINTS] → [PLAN] → [EXECUTE] → [VERIFY]`；首 token 必须是 `[`；thinking 内零 CJK（本宿主可见思考，须与输出同等严格）。输出语言跟随用户（默认中文）。
- **思考预算分档（知识库任务）**：

| 档位 | KB 任务示例 | Thinking | 预算 |
|------|-------------|----------|------|
| T0 | 知识架构设计、多源深度综述、复杂推理 | ON | high |
| T1 | 报告/章节生成、wiki 生成、管线调试、大型整理 | ON | medium（写作类 low–medium 防过度润色） |
| T2 | 分类/打标签/抽取/格式化/检索问答/采集清洗 | OFF | 0 |
| T3 | 实时问答、简单检索 | OFF | 0 |

- 默认档位：检索问答 T2（OFF）；采集/整理 T2；知识创作/报告 T1；知识库开发 T0/T1。
- Overthinking 检查：thinking tokens >70% 且无质量提升 → 砍预算。

## MoE-3. KB LLM 模型路由矩阵（LLM 调用类任务）

| Tier | KB 任务 | 模型（经 OmniRoute） | 备注 |
|------|---------|---------------------|------|
| T0 | 知识架构、复杂综述 | DeepSeek V4 / Qwen3.5-Max | thinking ON, temp 0.2 |
| T1 | 章节写作、报告生成、wiki | **openai/LongCat-2.0**（chapter_writer 默认，`thinking:{"type":"disabled"}` 防污染）→ GLM-4.6 → Doubao-1.5-pro | fallback 链已在 chapter_writer.py |
| T2 | 标签/分类/抽取/重排 | V4-Flash / 本地 embedding（MiniLM 384 维） | 批量零成本 |
| T3 | 实时问答 | V4-Flash / local | 延迟优先 |

- **工具协议差异**：LongCat/DeepSeek/Qwen 用 JSON schema function calling；GLM 用 XML tool 模板 —— chapter_writer 已封装适配层，勿对 GLM 强套 JSON schema。
- 版本固定：生产用固定 ID（LongCat-2.0 已固定）；换模型先 golden-set 回归（MoE-8）。

## MoE-4. Token 闸门（每会话执行）

| 闸门 | 规则（KB 语境） |
|------|-----------------|
| G1 上下文最小化 | 只加载任务所需：模式对应路由表 + 工具探针 + 记忆（日志 → MEMORY.md）；不整库加载 |
| G2 渐进披露 | 本 SKILL.md 为入口；`CHANGELOG.md` / `docs/` / `scripts/` 按需加载（脚本细节看头注释） |
| G3 静态工具路由 | §Tool Routing 已静态化；探针每会话一次，不重复探测 |
| G4 max_tokens 余量 | LLM 写作 `max_tokens = thinking + 期望答案 × 1.5`（chapter_writer 默认关 thinking） |
| G5 稳定前缀 | 系统提示 + 任务固定指令在前（可缓存）；用户输入/检索结果在最后 |
| G6 廉价模型卸载 | 批量清洗/打标签 → V4-Flash/本地 embedding；高价值创作 → LongCat-2.0/旗舰 |

## MoE-5. 质量闸门

- **输出规范**（任何 LLM 调用 prompt 必带）：直接给结果，禁止开场白/寒暄/"好的/让我们"；思考内容不得出现在输出；格式按需 Markdown/JSON。
- **来源纪律（KB 特有 grounding，v1.8 起）**：每条断言必须 [n] 引用素材（引用必须真实存在于素材）；无出处不交付；报告来源覆盖率 <90% 不交付。
- **提交前自检**：逻辑重算？约束全满足？引用真实存在？格式字节一致？thinking 语言扫描（零 CJK）？

## MoE-7. 上下文装配（稳定前缀）

```text
[System prompt（角色/规则/思考协议/输出规范）]   ← 固定，缓存命中区
[任务固定指令（模式/路由/纪律，不变部分）]         ← 固定
[素材池（记忆日志/MEMORY.md/检索 chunk，版本化）] ← 半稳定
-----------------------------------------------------------------
[本次用户输入 / 本次检索结果]                     ← volatile，最后
```

- 字节级一致前缀 = 提供方缓存命中；一处空格/换行/时间戳即破。
- KB 会话：记忆（日志/MEMORY.md）属稳定前缀区；检索 chunk 属 volatile 区。
- 长上下文：整文档注入适合整书/整报告分析（引用章节）；代码库用关键文件+树；问答用 top-k 检索（8–16K）。

## MoE-8. 评估与版本漂移

- **Golden set**：20–50 个 KB 样本（检索/提取/总结/报告生成），每次改 prompt/模型/参数/本 SDK 后回归。
- **指标**：通过率 · token 效率（out+think tokens / 通过任务）· think 占比（>70% 无收益 = overthinking）· 来源覆盖率 · 版本漂移（月度重跑）。
- **版本固定**：生产模型用固定 ID；本 SDK 每次改动升版本 + `CHANGELOG.md` 顶部条目 + git commit（§Rules 16）。

---

## 0. Mode Selection — pick ONE first (decides workflow weight)

| Mode | Triggers | 路由 |
|------|----------|------|
| **Ingest** (采集入库) | 采集、抓取、导入、收藏、存下来、同步、加一篇、收藏夹 | 网页深度提取 → 文档转换 → RSS/热点管道 → 云盘/连接器 → 入库存档 |
| **Organize** (整理归档) | 整理、分类、打标签、去重、归档、建索引、知识图谱、结构化 | 命名规范 → 索引/embedding → 图谱 → 去重清理 |

> **重叠裁决**：Organize vs Maintain 都含"去重/清理"。裁决规则 —— 针对**内容本身**（标签/分类/索引/重命名/去重）→ Organize；针对**资产生命周期**（备份/删除/迁移/蒸馏旧日志/磁盘清理）→ Maintain。删任何东西一律走 Maintain 的 personal_files_safety 流程。
| **Retrieve** (检索问答) | 找、查、搜索、回顾、上次说的、问答、有哪些、在哪里 | 本地检索 → 记忆检索 → 图谱/代码检索 → ima/外部 → Web 兜底 |
| **Create** (知识创作) | 笔记、总结、报告、文章、教程、写文档、输出知识 | 资料收集 → 大纲 → 生成 → 校验来源 → 沉淀回库 |
| **Maintain** (维护备份) | 备份、清理、巡检、迁移、过期、合并、整理记忆 | 备份先行 → 记忆维护 → 清理/审计 → 安全检查 |
| **Build** (知识库开发) | 给知识库加功能、写代码、改 PKOS、修 bug、部署 | 路由到 `user-vibe_coding-sdk-moe`（本 SDK 不做编码纪律） |

> **MoE 档位映射**：Ingest / Organize / Retrieve / Maintain → T2（thinking OFF）；Create → T1（ON medium）；Build → T0/T1（由编程 SDK 决定）。

## Mandatory Base

Load first, always:

- `using-superpowers` — skill system foundation. Invoke relevant skills BEFORE any response or action.
- **记忆优先**：任何"找/回顾/上次"类请求，先查本地记忆再回答 —— ① 工作区日志 `D:\WorkBuddy\KnowledgeBase\.workbuddy\memory/YYYY-MM-DD.md`（最近优先）→ ② 工作区 `MEMORY.md` → ③ `conversation_search`（跨会话检索）。无历史依赖才跳过。
- 需求澄清：涉及需求澄清且无明确输入时，一次一问，收敛后再动手。

## Context Engineering — check at session start

- **知识库目录约定**：本项目（`D:\WorkBuddy\KnowledgeBase`）= 知识库根。记忆在 `.workbuddy/memory/`（MEMORY.md 长期 + YYYY-MM-DD.md 日志，append-only）。`knowledge-os/` 仅是本机**可用工具之一**（见下），不是知识库本体——知识库本体是工作区 + 记忆系统。
- **本机工具（可选启用）**：`knowledge-os`（D:\WorkBuddy\KnowledgeBase\knowledge-os，FastAPI + MCP server，embedding/faiss 索引 + RRF rerank + 知识图谱 + RSS + 网页抓取）——需要本地语义索引/检索服务时才启用；服务未跑或项目删除不影响本 SDK 其余能力。快速了解：`knowledge-os/docs/`、`pyproject.toml`、`knowledge_os/` 模块布局。
- 术语漂移/新架构决策 → 触发 `context-modeling`：维护 CONTEXT.md 词汇表 + docs/adr/。
- Priority: 用户直接指令 > 记忆文件（MEMORY.md / 日志）> skills > 默认行为。

## Scenario Router

### Path A — Ingest 采集入库

```
来源识别 → 抓取/转换 → 清洗 → 元数据 → 入库/备份
```

- **网页/长文**：`crawl4ai-art`（深度提取，CSS/XPath/LLM 三策略，JS 渲染）；内容管道 `rsshub-art`（Pixiv/Civitai/ArtStation 等 300+ 站点 RSS）、`trendradar-hotspot`（11 个中文平台热点）、`agent-reach`（14 平台搜索阅读）
- **GitHub 热门项目**：`github-trending-cn`（GitHub Trending 榜单，日/周/月，真实 Search API）、`github-ai-trends`（AI/ML/LLM 仓库榜单）；深入仓库资料用 `github` skill（gh CLI：issues/PR/releases/code search）。采集结果按元数据纪律入库，后续可扩展 repo 监控/release 追踪
- **文档文件**（PDF/Word/PPT/Excel/图片 OCR/音频转录）→ `markitdown-skill` 转 Markdown 再入库
- **书籍/文档蒸馏为可复用技能**（book-to-skill，已登记）：`/book-to-skill <pdf|epub|文件夹|glob>` → 生成 Agent Skill（SKILL.md + 分章文件 + glossary/patterns/cheatsheet），之后用 `/技能名 <问题>` 按需问答，适合反复查阅的技术书/文档集（比整书 dump 省 24-51× token）
- **云盘/连接器**：`cloud-upload-backup`（腾讯 SMH）；待连接：ima-mcp / tencent-docs / wps-knowledgebase / baidu-netdisk / tencent-weiyun；**OpenWiki 连接器**（已登记，装后可用）：`openwiki ingest` 可采集 git-repo / Notion / Gmail / X / Hacker News / Slack / web-search 作为知识来源（OAuth 用 `openwiki auth <provider>`）
- 入库纪律：**每条必须带来源元数据**（URL/作者/日期/标签），否则未来不可信、不可检索
- **知识原子化（v1.9 新增，大型知识库构建核心）**：批量文档摄入后运行 `scripts/knowledge_atomizer.py <文档目录> <原子输出目录>` → 切分为知识原子（chunks/*.json + atoms.jsonl + MANIFEST）。原子带 heading_path 层级/来源追溯/元数据，供语义索引（Phase 2）与图谱检索消费。原子化后再建图（graphify），避免整篇文档进图谱
- **知识源 triage（v1.8 新增，大规模摄入时启用）**：批量摄入（>50 份源）登记 `docs/knowledge/triage.md` 或 CSV，每份源一行五态状态机：`needs-triage`（待分类）→ `needs-info`（缺信息）→ `ready-for-agent`（可摄入）→ `ready-for-human`（需人工确认）→ `wontfix`（废弃/重复）。摄入前先 triage，避免盲目解析
- 记忆写入：采集/导入完成后，append 到当日日志（记录来源、去向、规模）

### Path B — Organize 整理归档

```
命名 → 分类/打标签 → 索引构建 → 图谱 → 去重
```

- 命名规范先行（见 Rules §3）；分类打标签用 CONTEXT.md 统一词汇，术语漂移触发 `context-modeling`
- **知识库建图（graphify，核心整理手段）**：`graphify <目录>` 把任意知识目录（代码/文档/PDF/图片/视频）映射为可查询知识图谱——跨文档关联浮出（Surprising Connections）、知识领域划分（社区检测）、核心概念（God Nodes）；产出 graph.html + GRAPH_REPORT.md + graph.json。知识库增长后用 `graphify <目录> --update` 只重提取变更文件；`--obsidian` 可导出 Obsidian vault
- 索引：需要本地语义索引/检索时可用 `knowledge-os` 的 embedding/faiss 与 RRF 重排（见 `docs/rrf-reranking-detail.md`，服务未跑则跳过）；代码库建图与 graphify 二选一，勿重复建索引（graphify 偏全库理解+可视化，codebase-memory-mcp 偏极速检索）
- 去重/归档前遵循 personal_files_safety：扫描只读 → 列清单 → 确认 → 备份 → 小批量（≤10 文件/批）

### Path C — Retrieve 检索问答

```
本地 → 记忆 → 图谱 → ima/外部 → Web
```

1. **本地检索**：`knowledge-os` 检索（若服务在跑）；文档内容用 `markitdown-skill` 转文本后查
2. **记忆检索**：当日日志 → MEMORY.md → `conversation_search`（跨会话/项目）
3. **图谱检索**：目录已建图（存在 graphify-out/graph.json）→ `graphify query "<问题>"` 图谱问答（BFS 广谱上下文 / DFS 追路径 / --budget 限 token），`graphify path A B` 找概念最短路径，`graphify explain X` 解释节点；或 graphify-mcp 的 query_graph/get_node/get_neighbors。代码知识 → `codebase-memory-mcp`（trace_path / search_graph）或 graphify（query_graph）
4. **ima/外部**：`ima:knowledge-base`（若 connector 已信任）；库文档 → `find-docs` / `context7-cli`
5. **Web 兜底**：`agent-reach` / `WebSearch`；答案必须附来源，禁止无出处断言

### Path D — Create 知识创作（v1.8 双档模式）

**档位选择**：单篇笔记/简单总结 → **轻量模式**（直线流程）；大型报告/多源综述/知识库改造 → **工程模式**（spec→tickets→implement→review 闭环）。工程模式输出存 `docs/knowledge/specs/` + `docs/knowledge/plans/`（模板见 `docs/knowledge/README.md`）。

**轻量模式（默认）**：
- 基于库内资料创作：先检索（Path C）收集素材并标注来源 → 大纲 → 生成 → **来源校验**（每条论断可回溯）→ 成果沉淀回库（当日日志记录 + 可选入库）
- **Wiki 自动生成（OpenWiki，已登记）**：`openwiki personal` 让 AI 代理把知识来源综合成相互链接的 Markdown wiki（写入 `~/.openwiki/wiki`，OKF 格式）；代码库文档用 `openwiki`（code 模式，写入仓库 `openwiki/`）；`--init` 初始化 / `--update` 随变更持续维护 / `visualize` 交互浏览（127.0.0.1:4321）。首次使用需 `/api-key` 配置模型提供方（支持 OpenAI/Anthropic/Gemini/Bedrock/Ollama 等 12 种）；本机走 OmniRoute + LongCat-2.0（实战 recipe 见 CHANGELOG v1.11 补充）
- 涉及"写文档/PPT/Excel"交付物 → 路由 `docx` / `tencent-docs-routing` / `tencent-local-office-edit` 等

**工程模式（大型知识项目，v1.8 新增）**：

```
grill（需求拷问，一次一问收敛目标/范围/验收）
   ↓
to-spec → docs/knowledge/specs/YYYY-MM-DD-<项目>-spec.md
  ├── Problem Statement（要回答什么问题）
  ├── 章节大纲（每章论点）
  ├── 证据清单（每论点需要的来源）
  └── 验收标准（DoD）+ 风格指南
   ↓
to-tickets → docs/knowledge/plans/YYYY-MM-DD-<项目>/NN-<章>.md
  ├── 垂直切片（每章一个工单，可并行）
  ├── 阻塞边（前置章依赖）
  └── 每工单声明"素材需求 + 验证方式"
   ↓
implement（逐章生成）
  ├── 素材收集（Ingest 管道按需触发）
  ├── 章节生成（子代理并行 or 串行，避免长文档单次生成上限）
  └── 来源校验（每条断言映射到证据清单项）
   ↓
review（双轴校验）
  ├── 轴1 来源完整性：所有断言有出处？无出处标 TODO？
  └── 轴2 逻辑一致性：章节间矛盾？术语统一（CONTEXT.md 对照）？
   ↓
合并交付 → 归档留痕（spec/plan/tickets 保留，append 当日日志）
```

- 拆章可并行：2+ 独立章节 → `dispatching-parallel-agents`（并行子代理逐章产出）
- 多会话长项目 → `handoff`（压缩会话为交接文档，含 suggested skills、脱敏、引用工件）
- 完成定义（DoD）未过 → 不交付，回 implement 补来源/修矛盾
- LLM 章节生成走 MoE-3 路由（LongCat-2.0 默认，thinking disabled 防推理链污染）

### Path E — Maintain 维护备份

```
备份先行 → 记忆维护 → 清理审计
```

- 备份：`cloud-upload-backup`；关键目录变更前先备份（`cp -r` / `robocopy`），确认成功并告知备份位置
- 记忆维护：30 天前日志蒸馏进 MEMORY.md（按主题），随后删除旧日志；**append-only 纪律** —— 当日日志只追加不覆写
- 清理审计：删除/移动任何文件前遵循 personal_files_safety 全流程（扫描只读 → 列清单 → 明确确认 → 备份 → 回收站/小批量）
- 自动化：定期巡检/备份可用 `automation_update` 创建定时任务

### Path F — Build 知识库开发

- 给 knowledge-os 加功能 / 修 bug / 新知识库工具开发 → **直接路由 `user-vibe_coding-sdk-moe`**（MoE 优化版），按其 Mode Selection 走 Engineering / SDD / Debug / Review 流程；备选 `user-vibe_coding-sdk`
- 开发中新增的可用工具 → 登记进本 SDK §Tool Registry（见 Rules §6）

## Always-On Tools — 知识库工具生态（2026-08-04）

**基础设施（非工具）**
- WorkBuddy 记忆系统 — 工作区 `.workbuddy/memory/`（MEMORY.md + 日志）+ 用户级 `~/.workbuddy/MEMORY.md` + `conversation_search`

**采集/转换**
- `markitdown-skill` — 文档转 Markdown（PDF/Word/PPT/Excel/OCR/音频）
- `crawl4ai-art` — 网页深度提取（CSS/XPath/LLM、JS 渲染、反检测、无限滚动）
- `rsshub-art` — RSSHub 内容管道（300+ 站点）
- `trendradar-hotspot` — 11 中文平台热点聚合
- `agent-reach` — 14 平台搜索阅读（Twitter/X、Reddit、YouTube、GitHub、Bilibili 等）

**爬虫/浏览器自动化（venv 托管，uv 管理）**
- `Crawl4AI` — 50K+ star 异步爬虫，通用深度提取（CSS/XPath/LLM 策略、JS 渲染、反检测、无限滚动）。环境：`C:\Users\fu268\.workbuddy\binaries\python\envs\default`（uv pip install crawl4ai；浏览器内核 `crawl4ai.install_browser()` 按需）。与 crawl4ai-art 分工：crawl4ai-art 面向 AI 绘画社区页面，Crawl4AI 本体用于通用网页
- `Playwright` — 浏览器自动化（venv 装 playwright；浏览器内核 `playwright install` 按需）；`xbrowser`（浏览器自动化 skill，token 更省）为 skill 侧替代
- 运行探针：`"$VENV/Scripts/python.exe" -c "import crawl4ai, markitdown, playwright"`

**数据处理（venv 托管）**
- `markitdown` — 文档→Markdown（PDF/Word/PPT/Excel/图片 OCR/音频转录），`markitdown <file>` 或库调用
- `beautifulsoup4` — HTML/XML 解析（4.13.3）
- `pandas` — 表格数据处理（2.2.3）
- `httpx` — HTTP 客户端（0.28.1）
- ⚠ 不依赖 `D:\Software\python3.13.2\myenv`（requests 目录损坏不可读，见 CHANGELOG v1.7）

**文档蒸馏（书籍→Skill，已安装）**
- `book-to-skill` — virgiliojr94（MIT，Agent Skills 标准）。已安装：`~/.workbuddy/skills/book-to-skill`（git clone，安全审计 P2）。把书籍/文档集（PDF/EPUB/DOCX/MD/HTML/RTF/MOBI 等）蒸馏成 Agent Skill：`/book-to-skill <路径|文件夹|glob> [skill名]` → SKILL.md（心智模型 ~4K）+ chapters/（按章 ~1K，按需加载）+ glossary/patterns/cheatsheet；比整书进上下文省 24-51× token、无幻觉。生成环节需 LLM（可用 OmniRoute 网关），提取依赖 pdftotext/docling/ebooklib 等（`python scripts/extract.py --check` 探测）。版权：处理自有书籍/文档，输出为个人笔记不传播

**GitHub 生态（Ingest 管道）**
- `github-trending-cn` — GitHub Trending 榜单（日/周/月，真实 Search API）
- `github-ai-trends` — AI/ML/LLM 热门仓库榜单报告
- `github` — gh CLI（issues/PR/releases/code search），深入仓库资料
- 待扩展：repo 监控 / release 追踪 / 代码知识图谱联动

**Wiki 自动生成（已安装 v0.3.0）**
- `openwiki` — langchain-ai 自我维护 wiki（MIT）。`npm install -g openwiki`；原生依赖：`npm install -g --allow-scripts=better-sqlite3 openwiki`（better-sqlite3 在 openwiki 嵌套 node_modules）。**shim 已修复**（见 CHANGELOG v1.3 ⚠；npm 重装后需重应用）。AI 代理把知识来源合成相互链接的 Markdown wiki：`personal` 模式（`~/.openwiki/wiki`，OKF 格式）/ `code` 模式（仓库 `openwiki/`）；连接器 ingest（git-repo/Notion/Gmail/X/HN/Slack/web-search）；`visualize` 交互浏览 127.0.0.1:4321；`--init` / `--update` 持续维护；12 种模型提供方。与 graphify 互补：graphify 建**图谱**，openwiki 写**文档**

**图谱/检索**
- `graphify` — **已集成**（graphifyy v0.9.32，CLI `~/.local/bin/graphify`，graphify-mcp 已装）。知识库建图：`graphify <目录>` → graph.html + GRAPH_REPORT.md + graph.json；图谱问答：`query/path/explain`；增量：`--update`；MCP：query_graph/get_node/get_neighbors/get_community/god_nodes/graph_stats/shortest_path
- `codebase-memory-mcp` — 代码知识图谱（快检索/trace）
- `find-docs` / `context7-cli` — 库文档检索

**本机工具（可选启用）**
- `knowledge-os` — 本地语义索引/检索服务（embedding/faiss + RRF 重排 + 图谱 + RSS + 抓取），服务未跑则跳过

**外部知识库（connector 待信任）**
- `ima:knowledge-base` / `ima:notes` — ima 知识库
- `wps-knowledgebase` / `tencent-docs` / `baidu-netdisk` / `tencent-weiyun` — 文档/网盘
- `cloud-upload-backup` — 腾讯 SMH 云备份

**Obsidian 生态（已安装）**
- Obsidian — 已安装，vault `C:\Users\fu268\Documents\Obsidian Vault`（obsidian.json 注册）
- `obsidian-skills`（kepano 官方，已安装 `~/.workbuddy/skills/obsidian-skills`，审计 P2）— 5 个技能：`obsidian-markdown`（方言 Markdown：wikilinks/embeds/callouts/properties）、`obsidian-bases`（.base 库）、`json-canvas`（.canvas 画布）、`obsidian-cli`（Obsidian CLI，需另装 CLI 二进制 + Obsidian 打开）、`defuddle`（网页→干净 Markdown）。基础笔记读写无需 CLI

**上下文工程**
- `context-engineering` — AGENTS.md；`context-modeling` — CONTEXT.md + docs/adr/

**系统纪律（非 skill，强制执行）**
- `personal_files_safety` — 系统内建安全流程：涉及个人目录（Desktop/Downloads/Documents 等）的扫描/清理/删除/移动，必须扫描只读 → 列清单 → 明确确认 → 备份 → 回收站/小批量

## Tool Routing（v1.10）— 模式 → 工具集 静态路由表

Mode Selection 确定后，**自动带上该模式对应的工具集**（下表）。映射是静态的，执行时按需调用——不动态列举全部工具，无关工具不触发。

| Mode | 自动带上的工具（按优先级） | 用途 | 可用性探针 |
|------|--------------------------|------|-----------|
| **Ingest** | `markitdown`/`markitdown-skill`（文档转换）→ `Crawl4AI`/`crawl4ai-art`（深度提取）→ `Playwright`/`xbrowser`（浏览器自动化）→ `book-to-skill`（书籍/文档蒸馏，已登记）→ `defuddle`（Obsidian，网页→干净MD，已登记）→ `github-trending-cn`/`github-ai-trends` → `rsshub-art`/`trendradar-hotspot`/`agent-reach` → `openwiki ingest`（连接器，已登记）→ `cloud-upload-backup` | 文档转换 + 深度提取 + 浏览器自动化 + 书籍→Skill + 网页净化 + GitHub 热门项目 + 内容管道 + 连接器采集 + 云备份 | `"$VENV/Scripts/python.exe" -c "import crawl4ai, markitdown"` / `ls ~/.workbuddy/skills/book-to-skill` / `ls ~/.workbuddy/skills/obsidian-skills` |
| **Organize** | `scripts/knowledge_atomizer.py`（知识原子化，v1.9）→ `graphify`（建图）→ `book-to-skill`（蒸馏结构化，已登记）→ `obsidian-markdown`/`obsidian-bases`（vault 笔记整理，已登记）→ `context-modeling` → `codebase-memory-mcp`（代码库时）→ `knowledge-os`（可选，服务在跑时） | 知识原子化 + 知识库建图 + 蒸馏结构化 + Obsidian 笔记 + 统一词汇 + 代码建图 + 本地索引 | `ls scripts/knowledge_atomizer.py` / `command -v graphify` / skill 是否在列 / MCP 工具注册 / 服务端口 |
| **Retrieve** | `.workbuddy/memory/`（日志 → MEMORY.md）→ `conversation_search` → `graphify query`（目录已建图时）→ `knowledge-os`（可选，服务在跑时）→ `find-docs`/`context7-cli` → `agent-reach`/WebSearch | 记忆检索 + 图谱问答 + 本地检索 + 库文档 + Web 兜底 | 记忆目录存在 / `graphify-out/graph.json` / 服务端口 / MCP 注册 |
| **Create** | Path C 全套 →（工程模式）`scripts/report_pipeline.py`（报告编译管线，v1.10）→ `dispatching-parallel-agents`（并行拆章）→ `handoff`（多会话交接）→ `openwiki`（wiki 自动生成，已登记）→ `obsidian-markdown`/`json-canvas`（Obsidian 创作，已登记）→ `docx` / `tencent-docs-routing` | 素材检索 + 报告编译管线（检索→引用→并行→装配→校验）+ 交接 + wiki/文档 + 交付物 | `ls scripts/report_pipeline.py` / `command -v openwiki` / skill 是否在列 |
| **Maintain** | `cloud-upload-backup` → 记忆蒸馏流程 → personal_files_safety 审计 | 备份 + 记忆维护 + 清理 | `command -v` / 备份目标可写 |
| **Build** | `user-vibe_coding-sdk-moe`（全量路由，MoE 优化）→ 降级 `user-vibe_coding-sdk` → 无 SDK 时自行执行其 Engineering/SDD/Debug/Review 纪律 | 编码纪律由编程 SDK 承担 | 直接调用 |

### 可用性探针规则

1. **轻量探测**（每会话一次，非每次调用）：进入模式时检查路由表中工具是否可用——CLI 用 `command -v <bin>`；connector/MCP 检查是否已"信任"（connector-status 中 connected）。
2. **自动降级**：不可用工具跳过，用路由表下一顺位替代（如 markitdown 不可用 → 用 Read 直读 PDF/ipynb；ima 未连接 → Web 兜底）。降级不阻塞任务，最终报告注明"哪些不可用、用了什么替代"。
3. **不重复探测**：会话内已确认可用的直接复用；只有报错时才重新探测。
4. **token 原则**：先调用能给出最精确答案的（记忆检索 > 图谱 > grep 读文件）；一次调用能回答的问题不拆两次。

## Tool Registry — 新工具登记（扩展机制）

将来接入新知识库工具时，按此流程登记（保证路由表始终可用）：

1. **Always-On Tools** 加一行：工具名 — 一句话能力定位
2. **Tool Routing 表** 对应 Mode 行插入优先级位置（按精确度排序）
3. **可用性探针** 补一行探测命令（CLI 用 `command -v`，connector 记"信任后生效"）
4. 版本号升位，CHANGELOG.md 顶部记一行（`## vX.Y（日期）— 摘要`）

## Creating / Extending Skills

- 新知识库子技能 → `writing-skills`；维护本 SDK 同法
- 安装第三方 skill → **安全审计先行**（约 36% 第三方 skill 含 prompt-injection 风险），仅装官方/可信源

## Rules

1. **记忆优先** — "找/回顾"先查记忆（日志 → MEMORY.md → conversation_search）再回答，不凭空断言
2. **来源纪律** — 任何入库/创作的知识必须带来源元数据（URL/作者/日期）；无出处不交付。大型报告必须产出**来源覆盖率**（断言→证据清单映射检查）作为完成门槛
3. **命名/词汇统一** — 分类标签用 CONTEXT.md 统一词汇；术语漂移触发 context-modeling
4. **append-only** — 当日记忆日志只追加不覆写；30 天日志蒸馏进 MEMORY.md 后可删旧
5. **personal_files_safety 全流程** — 删除/移动/清理文件：扫描只读 → 列清单 → 明确确认 → 备份 → 回收站/小批量
6. **扩展登记** — 新工具进 Always-On Tools + Tool Routing + 探针，版本升位记 CHANGELOG.md
7. **双层架构** — 本 SDK 负责编排（路由/纪律），模型调用技能承载执行（markitdown/graphify 等）；本 SDK 不重复实现子技能能力
8. **指针式增强维护** — 对第三方技能的增强只加一行 `> 增强：…见 user-PersonalKnowledgeBase-sdk §…` 引用，上游覆盖后重加引用行即可恢复
9. **环境约定** — Python 依赖用 uv；git push 前必须询问用户；默认中文回复
10. **Build 边界** — 编码/调试/审查任务路由 `user-vibe_coding-sdk-moe`（主）→ `user-vibe_coding-sdk`（备），不在本 SDK 内重造
11. **两档模式（v1.8）** — 轻量任务直线执行；大型知识项目（大型报告/多源摄入/知识库改造）必须走 Path D 工程模式闭环（grill→to-spec→to-tickets→implement→review），DoD 未过不交付
12. **上下文工程（v1.8）** — 会话开始先确认知识库三层上下文（AGENTS.md / CONTEXT.md / docs/adr/）；决策留痕写 ADR；术语漂移更新 CONTEXT.md
13. **知识源 triage（v1.8）** — 批量摄入（>50 份源）先 triage 五态登记，再解析；禁止盲目全量解析
14. **英文思维链（MoE-2）** — thinking 一律英文骨架：首 token `[`、零 CJK；输出跟随用户语言（默认中文）
15. **Token 纪律（MoE-4）** — 每会话执行闸门：最小上下文、渐进披露（CHANGELOG.md 按需加载）、稳定前缀、廉价模型卸载
16. **版本纪律** — 每次改动升版本 + `CHANGELOG.md` 顶部条目 + git commit（本地默认，push 需确认）；与 user-vibe_coding-sdk-moe §10 对齐
