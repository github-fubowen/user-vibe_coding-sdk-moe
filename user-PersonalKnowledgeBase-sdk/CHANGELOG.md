# CHANGELOG — user-PersonalKnowledgeBase-sdk

渐进披露文件（G2）：完整版本历史在此，不进 SKILL.md 热路径。SKILL.md 仅保留一行指针。

## v2.0（2026-08-22）— MoE 层接入（对齐 user-vibe_coding-sdk-moe）

MoE 化升级（自举：用 moe SDK 方法论改造本 SDK）：

- **强制英文思维链**（MoE-2）：thinking 一律英文骨架 `[GOAL]→[CONSTRAINTS]→[PLAN]→[EXECUTE]→[VERIFY]`，首 token `[`，零 CJK；输出跟随用户语言
- **思考预算分档**（MoE-2）：T0 知识架构/深度综述 ON high；T1 报告/章节/wiki 生成 ON medium；T2 分类/打标签/抽取/检索 OFF；T3 实时问答 OFF
- **KB LLM 模型路由矩阵**（MoE-3）：T0 DeepSeek V4/Qwen3.5-Max；T1 LongCat-2.0（chapter_writer 默认，thinking disabled 防污染）→ GLM-4.6 → Doubao；T2 V4-Flash/本地 MiniLM embedding；T3 V4-Flash。协议差异（JSON schema vs GLM XML）已在 chapter_writer 封装适配层
- **Token 闸门 G1-G6**（MoE-4）：上下文最小化 / 渐进披露 / 静态工具路由 / max_tokens 余量 / 稳定前缀 / 廉价模型卸载
- **质量闸门**（MoE-5）：输出规范（禁开场白/思考泄漏）+ 来源纪律 grounding（无出处不交付、覆盖率 <90% 不交付）+ 提交前自检
- **上下文装配**（MoE-7）：固定前缀（角色/任务指令/记忆）在前、volatile（用户输入/检索结果）在后，保缓存命中
- **评估闭环**（MoE-8）：golden set 20-50 样本回归；token 效率/think 占比/覆盖率/月度版本漂移
- **结构收敛**：v1.0–v1.11 changelog 块移出 SKILL.md 热路径 → 本文件（渐进披露）
- **Build 路由**：Path F / Tool Routing Build 行改指向 `user-vibe_coding-sdk-moe`（主）→ `user-vibe_coding-sdk`（备）
- **版本纪律**：每次改动升版本 + 本文件顶部条目 + git commit（本地默认，push 需确认）

领域内容（Mode Selection / Scenario Router A-F / Always-On Tools / Tool Routing / Registry / Rules 1-13）100% 保留。

---

## v1.11 补充（2026-08-10）— openwiki 用 LongCat 生成 wiki 实战成功

四份知识底座（货币政策/利率/离岸金融/经济物理引擎）→ 6 页相互链接的中文 wiki（`macroecon-cognition/wiki/`）。关键经验：

- **运行方式**：必须在**隔离目录**运行（`--mode code` 基于 cwd 扫描；直接跑 knowledge/ 会扫到用户目录 codex-runtimes 等无关文件）。命令：`cd <隔离目录> && NODE_OPTIONS="--use-system-ca" OPENWIKI_TELEMETRY_DISABLED=1 openwiki --mode code --modelId openai/LongCat-2.0 --print --init "<message>"`（后台运行，agent 多轮 LLM 调用约 7 分钟）
- **LongCat 需支持 tool_calling**（已验证 openai/LongCat-2.0 支持，openwiki agent 必需）；`--print` 是 CI/非 TTY 模式，配合 message 参数一次性执行
- **已知 bug**：openwiki 生成互链会加 `../` 前缀指向 wiki root 外 → 需 sed 移除 `(../` → `(`；同时删除 `<!-- openwiki: broken internal link` 注释
- 产物：quickstart.md（入口+导航表）+ index.md（索引）+ 4 概念页，OKF v0.1 front matter，长文用 LongCat 生成约 1 万+ 字

## v1.11 变更（2026-08-10）— 机构研报模板

报告管线升级为**机构研报模板**（用户反馈"报告简陋，不像大型机构研报"）。详见 `docs/knowledge/specs/2026-08-10-institutional-report-template-spec.md`：

- **`scripts/report_templates.py`**（新增）：研报骨架模板 —— 封面元数据（标题/类型/日期/版本/范围，从 spec `> 标题：` front-matter 解析）、执行摘要、核心观点、风险提示、免责声明、参考文献（含完整来源路径）、Markdown 表格渲染 + 数字启发式提取
- **`scripts/chapter_writer.py`** 增强：新增 `generate_executive_summary`（3-5 段核心结论）/ `generate_key_points`（5-8 条带引用观点）/ `generate_risk_section`（政策+市场+模型风险）；`generate_chapter` 强化为结构化章节（核心论点框 + 编号小节 + 数据表格）
- **`scripts/report_pipeline.py`** 增强：`--title/--report-type/--date/--version/--scope` 封面参数；P4.5 前置区块生成（摘要/观点/风险/数据附录）；装配器按研报骨架装配；`_renumber_subheadings` 统一小节编号（LLM 每章从 1.1 开始 → 装配为 1.1-5.6 全文唯一）；`_strip_leading_h1` 去 LLM 自带标题
- **实测**：165 原子库 → 5 章 + 执行摘要 + 7 核心观点 + 4 风险提示 + 数据表格 + 免责声明，462 行研报，0 推理链污染
- 兼容：`--writer compile`（无 LLM）降级为"模板骨架 + 原子拼接"，不破坏 v1.10

## v1.10 变更（2026-08-10）— 大型报告编译管线

新增**大型报告编译管线**（衔接 v1.9 知识原子化），解决"知识库→大型报告"的手工作业问题。详见 `docs/knowledge/specs/2026-08-10-report-pipeline-spec.md`：

- **管线六阶段**：P1 需求对齐(spec) → P2 素材检索(knowledge-os RAG) → P3 原子引用(自动参考文献) → P4 逐章生成(并行) → P5 合并装配(编号/TOC/引用) → P6 校验交付(来源覆盖率)
- **`scripts/report_pipeline.py`**：一条命令 `--spec <spec> --kb <knowledge-atoms> --out <report.md> [--retriever rag]` 产出完整报告 + 覆盖率报告。实测：165 原子库 → 4 章报告 → 引用 20 处
- **`scripts/knowledgeos_bridge.py`**（v1.10 Phase 2 完成）：接入 knowledge-os **RAG 语义检索**（embedding MiniLM 384 维 + FTS5 + RRF 混合重排）。实测相关性显著优于关键词版（命中主题相关内容而非无关文本）。`--init` 建索引（需用 knowledge-os 的 .venv 运行）；检索自动复用索引
- **`scripts/chapter_writer.py`**（v1.10 Phase 3 完成）：**LLM 真实章节生成**——按 spec 论点 + RAG 素材撰写连贯章节，自动 [n] 引用标注。默认模型 **`openai/LongCat-2.0`**（美团 LongCat 平台，2026-08-10 接入 OmniRoute，`thinking:{"type":"disabled"}` 关闭推理链防污染），含 fallback 链。实测 5 章报告 = 连贯深度论述 + 精准引用 + 0 推理链污染
- **LongCat 接入**：`omniroute setup --add-provider --provider openai --provider-name longcat --provider-base-url https://api.longcat.chat/openai`（`--api-key` 与全局选项冲突，须用 node 脚本直调 `runSetupCommand`）。模型标识 `openai/LongCat-2.0`
- **覆盖率纪律**：`coverage_pct <90%` 报告不交付（v1.8 纪律自动化）；LLM 引用覆盖率仅统计实际引用原子
- 环境注意：RAG+LLM 全流程在 **default venv** 运行（已补装 sentence_transformers/faiss/fastapi/jieba 等）；OmniRoute 启动必须**重定向到日志文件**（`> ~/.omniroute/server.log 2>&1`），用 `| head/tail` 管道截断会导致事件循环阻塞

## v1.9 变更（2026-08-10）— 大型知识库构建模式

升级为**大型知识库构建模式**（多层知识系统：Source → Document → Chunk 原子 → Concept → View），解决"构建只停留在文档层/总结报告"的问题。详见 `docs/knowledge/specs/2026-08-10-knowledge-base-v1.9-spec.md`：

- **知识原子化管线**：`scripts/knowledge_atomizer.py` —— Markdown 文档按标题层级/对话流水切分为知识原子（Chunk），带 heading_path/来源追溯/双向链接元数据；输出 chunks/*.json + atoms.jsonl + MANIFEST。实测：5 文档 → 165 原子
- **多层知识架构**：文档层（markdown）→ 原子层（chunks/）→ 概念层（graphify 图谱）→ 视图层（报告/问答）
- **语义检索待接线**：knowledge-os 的 embedding + FTS5 + RRF 混合检索能力已确认（`knowledge_os/embedding/` + `retrieval/hybrid.py`），Phase 2 接入
- 环境修复固化：`scripts/setup_env.sh`（MSYS 路径/依赖/浏览器内核/graphify 一键修复）
- v1.8 变更记录见知识库记忆日志 2026-08-08（三层上下文 + Path D 工程闭环 + 知识源 triage）

## v1.8 变更（2026-08-08）— 大型知识库项目管理框架

借鉴代码仓库管理模式（superpowers / mattpocock/skills / user-vibe_coding-sdk v2.1 技术栈），升级为**大型知识库项目管理框架**（详见 `docs/adr/ADR-0001`）：

- **三层上下文落地**：知识库根 `AGENTS.md`（操作约定）+ `CONTEXT.md`（领域词汇表）+ `docs/adr/`（决策记录）—— 已建，见 `D:\WorkBuddy\KnowledgeBase\`
- **Path D 升级为知识项目工程闭环**：grill（需求拷问）→ to-spec（论点+证据清单）→ to-tickets（章工单）→ implement（逐章生成）→ review（双轴校验：来源完整性+逻辑一致性）—— 支持大型报告拆章并行生成，解决单次生成上限
- **两档模式**：轻量模式（简单问答/单篇笔记，走原 Path D 直线流程）+ 工程模式（大型报告/多源摄入，走 spec→tickets→implement→review 闭环）
- **知识源 triage（v1.8 新增）**：大规模摄入源五态管理（needs-triage/needs-info/ready-for-agent/ready-for-human/wontfix），登记文件 `docs/knowledge/triage.md` 或 CSV
- **知识验证回路（替代 TDD）**：断言→来源映射检查、跨章一致性、来源覆盖率报告（v1.8 以纪律要求形式落地，脚本化在 Phase D）
- 备份：v1.7 存档于 `D:\WorkBuddy\KnowledgeBase\docs\backups\SKILL.v1.7-2026-08-08.md`

## v1.7 变更（2026-08-05）— 网络爬虫/浏览器自动化 + 数据处理工具群

集成**网络爬虫/浏览器自动化 + 数据处理**工具群（均为现成/可安装）：**Crawl4AI**（50K+ star 异步爬虫，deep web 提取：CSS/XPath/LLM 策略、JS 渲染、反检测）与 `crawl4ai-art`（绘画社区定制版）分工；**Playwright**（浏览器自动化）；`xbrowser`（浏览器自动化 skill）；**markitdown**（文档→Markdown：PDF/Word/PPT/Excel/OCR/音频）；bs4/pandas/httpx（HTML 解析/数据处理/请求）。**已安装**：venv `C:\Users\fu268\.workbuddy\binaries\python\envs\default`（uv 管理，crawl4ai+markitdown+bs4 4.15+httpx 验证通过；pandas 未装可按需 uv 加；Playwright 浏览器内核 `playwright install` 按需）。⚠ 系统 `D:\Software\python3.13.2\myenv` 的 requests 目录损坏（Windows 层不可读）——**不要依赖 myenv**，工具一律装 venv。定位：**Ingest 深度采集层 + 文档处理层**。

## v1.6 变更（2026-08-05）— Obsidian 生态

登记并安装 **obsidian-skills**（kepano/Obsidian 官方，https://github.com/kepano/obsidian-skills，MIT，Agent Skills 标准）——教 agent 使用 Obsidian 的 5 个技能：`obsidian-markdown`（方言 Markdown：wikilinks/embeds/callouts/properties）、`obsidian-bases`（.base 结构化库：视图/过滤/公式）、`json-canvas`（.canvas 画布）、`obsidian-cli`（Obsidian CLI 交互 vault/插件开发）、`defuddle`（网页→干净 Markdown 去杂波）。**已安装**：`~/.workbuddy/skills/obsidian-skills`（git clone，安全审计 P2——MIT 官方、无危险模式）。**本机环境**：Obsidian 已装，vault = `C:\Users\fu268\Documents\Obsidian Vault`，CLI 未装（obsidian-cli 技能需 Obsidian 打开 + CLI 二进制，基础笔记读写不需要）。定位：**Obsidian 知识库的正确读写**（Organize/Create 主导 + Ingest defuddle）。

## v1.5 变更（2026-08-04）— book-to-skill 登记

登记并安装 **book-to-skill**（virgiliojr94，https://github.com/virgiliojr94/book-to-skill，MIT，Agent Skills 开放标准）——把技术书籍/文档集蒸馏成 **Agent Skill**（SKILL.md 核心心智模型 ~4K + chapters/ 按章 ~1K + glossary/patterns/cheatsheet），按需加载章节，比整书 dump 省 24-51× token，无幻觉。**已安装（skill 方式）**：`~/.workbuddy/skills/book-to-skill`（git clone，安全审计 P2 通过——纯本地处理，自带生成产物安全扫描）。用法：`/book-to-skill <pdf|epub|文件夹|glob> [skill名]`。定位：**书籍/文档 → 可复用知识技能**（Ingest 转化 + Organize 蒸馏 + Retrieve 按需问答）。与 markitdown（纯格式转换）/ graphify（图谱）/ openwiki（wiki）互补。

## v1.4 变更（2026-08-04）— OpenWiki 可运行

OpenWiki **已配置可运行** —— 模型走本机 **OmniRoute LLM 网关**（`http://127.0.0.1:20128/v1`，openai-compatible，REQUIRE_API_KEY=false 匿名可用），用 `auto/best-coding` 等 combo 模型（支持 tool_calling）。运行方式：`NODE_OPTIONS="--use-system-ca" openwiki personal --modelId auto/best-coding`（必须去 WorkBuddy safe-delete 注入，否则 openwiki 删临时文件失败退出）。OmniRoute 启动：`env -u CODEBUDDY_SESSION_ID -u CLAUDE_SESSION_ID NODE_OPTIONS="--use-system-ca --max-old-space-size=8192" node .../omniroute/bin/omniroute.mjs serve`（需 better-sqlite3 原生驱动，见知识库日志 2026-08-04）。

## v1.3 变更（2026-08-04）— OpenWiki 登记

登记并安装 **OpenWiki**（langchain-ai，https://github.com/langchain-ai/openwiki，MIT）——自我维护 wiki 工具，AI 代理自动生成并持续维护相互链接的 Markdown wiki。**已安装 v0.3.0**（`npm install -g openwiki` + `--allow-scripts=better-sqlite3` 构建原生依赖）。双模式：`code`（为代码仓库生成文档）/ `personal`（个人知识库 → `~/.openwiki/wiki`）；连接器 ingest 可采集 Notion/Gmail/X/HN/Slack/git-repo/web-search 为知识来源；`openwiki visualize` 交互可视化器（127.0.0.1:4321）；输出 OKF v0.1 格式，可迁移。定位：**AI 自动撰写/维护 wiki**（Create 主导，Ingest 连接器为辅）。

### ⚠ OpenWiki 维护注意（2026-08-04）

本环境 Git Bash 缺 cygpath，npm 生成的 shim（`D:\Software\NodeJS\node_global\openwiki`）路径转换失败（报 `d:\d\Software\...` MODULE_NOT_FOUND）。已修复：把 shim 末行改为 `exec "$PROG_EXE" "D:/Software/NodeJS/node_global/node_modules/openwiki/dist/cli.js" "$@"`。**npm 重装 openwiki 后需重新应用此修复**；better-sqlite3 原生模块位于 `openwiki/node_modules/better-sqlite3/`（嵌套私有依赖，非顶层）。

## v1.2 变更（2026-08-04）— graphify 集成

正式集成 **graphify**（现成项目，已安装 graphifyy v0.9.32，CLI 在 `~/.local/bin/graphify`，graphify-mcp 已装）——知识库目录（代码/文档/PDF/图片/视频）一键建图：graph.html 交互可视化 + GRAPH_REPORT.md 审计报告 + graph.json（GraphRAG-ready）；`graphify query/path/explain` 图谱问答代替 grep；`--update` 增量重提取；`--mcp` 提供 query_graph/get_node/get_neighbors/god_nodes 等。定位：**知识库建图 + 图谱检索**双能力（Organize + Retrieve）。

## v1.1 变更（2026-08-04）— 定位修正

定位修正 —— `knowledge-os` 从"核心资产"降为**可用工具之一**（与其余工具平级，仅在本机且需要语义索引/检索时启用）；集成 **GitHub 热门项目采集**（`github-trending-cn` / `github-ai-trends` / `gh` CLI），作为 Ingest 的内容管道之一。后续更多 GitHub 生态工具（repo 监控、release 追踪等）按 §Tool Registry 登记。

## v1.0（2026-08-04）— 初版

模仿 user-vibe_coding-sdk 骨架建立 —— Mode Selection → Scenario Router → Always-On Tools → Tool Routing 静态路由表。工具生态盘点自当前环境（WorkBuddy 记忆系统 + knowledge-os + ima/图谱/采集/转换/备份工具群）。**扩展机制内置**：新知识库工具登记到 §Tool Registry，路由表自动生效。
