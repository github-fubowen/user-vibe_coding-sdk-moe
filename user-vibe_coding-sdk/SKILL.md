---
name: user-vibe_coding-sdk
description: Use when the user says "start coding", "enter dev mode", "一键加载编程技能", "coding mode", "vibe coding", or explicitly asks to begin a coding/development session. Also use when the user describes a task that requires writing, debugging, reviewing, refactoring, or deploying code. Routes to the right skill stack based on task mode (vibe / engineering / SDD / debug / review / quick-edit).
---

# Coding SDK v2.1 — 一键加载编程技能栈

Activate the right skill stack before writing code. Load only what the task needs — not everything.

> **v2.1 变更（2026-08-02）**：融合 mattpocock/skills 工程纪律 —— 新增 `grilling`（需求盘问）、`context-modeling`（领域模型）、`to-spec`/`to-tickets`/`implement`（SDD 闭环）、`handoff`、`triage`；TDD 增强 seams 接缝纪律、Debug 增强 Phase 0 反馈回路、Review 增强双轴并行。详见各路径。
>
> **v2.1.1 变更（2026-08-04）**：新增 §Tool Routing 工具路由表 + 可用性探针 —— Mode Selection 后自动带上该模式对应的工具集（静态映射，零额外 token），调用前做轻量可用性探测，不可用自动降级。目的：提高效率与准确率、减少 token 消耗。
>
> **v2.1.2 变更（2026-08-09）**：新增 §External Tool Sources 外部工具源 —— 内置工具/skills 找不到合适工具时，回退到高星开源工具源检索参考实现，热门高星优先。首个收录：`Shubhamsaboo/awesome-llm-apps`（131.6k ⭐，100+ AI Agents/Agent Skills/RAG Apps，Apache-2.0）。
>
> **v2.1.3 变更（2026-08-11）**：外部工具源新增两个来源 —— ① 科学技能库 `K-Dense-AI/scientific-agent-skills`（33.2k ⭐，158+ 科学 Agent Skills / 100+ 科学数据库，MIT + 各技能独立许可），定位 AI 科学家；② 工程纪律技能包 `addyosmani/agent-skills`（85.8k ⭐，24 个生产级工程技能 + 4 人格 + 7 检查清单，MIT），填补 SDK 空白（security-and-hardening / performance-optimization / observability / api-and-interface-design / frontend-ui-engineering / doubt-driven-development）。两者均遵循 Agent Skills 开放标准。

## 0. Mode Selection — pick ONE first (decides workflow weight)

| Mode | Triggers | Workflow |
|------|----------|----------|
| **Vibe** (原型/试错) | "vibe", "prototype", "快速试错", "随便做个", "玩一下", throwaway experiment | Light path — skip planning ceremony, build fast, verify, iterate |
| **Engineering** (正式开发) | new feature, refactor, production code, 正式功能 | Full superpowers pipeline |
| **SDD** (规范驱动) | "spec", 规范, 需求文档, 多步骤大功能, team project | Spec-first: context + requirements → plan → tasks → TDD |
| **Debug** (调试) | bug, 报错, 行为异常, unexpected behavior, diagnose, 反馈回路 | systematic-debugging (Phase 0 反馈回路优先) |
| **Review** (审查) | review, 审查, 反馈, feedback, 双轴审查 | requesting / receiving-code-review (双轴并行) |
| **Quick Edit** (小改) | 1-2 line fix, 小修改, typo fix | Light TDD → verify |

## Mandatory Base

Load first, always:

- `using-superpowers` — skill system foundation. Invoke relevant skills BEFORE any response or action.
- 需求澄清：涉及需求澄清且无明确 spec 时，优先 `grilling`（一次一问，决策树收敛后再动手）。

## Context Engineering — check at session start

- **三层上下文**（v2.1）：`AGENTS.md`（指令/约定）+ `CONTEXT.md`（领域词汇表，由 `context-modeling` 维护）+ `docs/adr/`（架构决策记录）。
- Look for `AGENTS.md` / `CLAUDE.md` at repo root and nearest to files being edited.
- Missing + non-trivial project → propose creating `AGENTS.md` (`context-engineering` skill). Map-style: <200 lines, Setup Commands first, conventions, boundaries, links to `docs/*` for deep topics.
- 术语漂移/新架构决策 → 触发 `context-modeling`：维护 CONTEXT.md 词汇表 + docs/adr/，让测试名/接口名与领域语言一致。
- Why: AGENTS.md is the 2026 de-facto standard — read natively by Claude Code, Codex CLI, Cursor, Copilot, Gemini CLI, Aider, Devin, Amazon Q, Windsurf. Anthropic data: good context cuts wrong-pattern rewrites 40–60%.
- Priority: user instructions (AGENTS.md/CLAUDE.md/direct) > skills > default behavior.

## Scenario Router

### Path A — Engineering (Feature / Refactor)

```
brainstorming → grilling → writing-plans → test-driven-development → subagent-driven-development
```

- `brainstorming` — 发散探索方案：clarify requirements BEFORE coding (skip only if spec already clear)
- `grilling` — 收敛决策树：一次一问，每个分支解决后才进入计划；产出决策收敛记录
- `writing-plans` — break into 2-5 min tasks, save to `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`
- `test-driven-development` — RED-GREEN-REFACTOR, YAGNI, DRY；**写测试前先确认测试接缝(seam)**：在哪个公共接口测、不测哪些；避免 horizontal slicing / tautological / implementation-coupled 反模式（见 §PathA-TDD）
- `subagent-driven-development` — fresh subagent per task + two-stage review (spec compliance → code quality); use `executing-plans` (sequential) when harness lacks subagents

### Path B — Vibe / Prototype (NEW)

Use when user is exploring, prototyping, or explicitly wants speed over ceremony.

1. Announce "vibe mode: build first, refine after"
2. Skip brainstorming and writing-plans. Go straight to implementation; TDD only if repo has tests
3. Keep scope small, check in frequently, no long autonomous runs
4. Finish with `verification-before-completion`
5. If the idea survives prototyping and becomes production work → re-enter at Path A

### Path C — Debug / Fix

```
systematic-debugging → verification-before-completion
```

- `systematic-debugging` — 4-stage root cause analysis (no random guessing)；**Phase 0 反馈回路优先**：先建立 tight pass/fail 信号（failing test / curl / headless / trace replay / throwaway harness / fuzz / bisection / differential，最后才 HITL），无反馈回路前禁止盯着代码猜
- `verification-before-completion` — confirm fix BEFORE claiming done

### Path D — Code Review

```
requesting-code-review  OR  receiving-code-review
```

- Pick based on whether user is submitting or receiving feedback
- **双轴并行（v2.1）**：拆两个并行 subagent —— ① 标准轴：仓库编码标准 + Fowler 坏味道基线（Mysterious Name / Duplicated Code / Feature Envy / Data Clumps / Primitive Obsession / Repeated Switches…）；② Spec 轴：对照源 issue/spec/PRD 逐条验收。两轴互不污染上下文，报告并列呈现。
- **OCR 先行（open-code-review）**：进 Path D 时先跑 `ocr review --audience agent`（或 `ocr scan` 全文件/`ocr delegate preview` 委派）拿自动化行级审查结果，再喂给双轴 subagent 做筛选分级（High/Medium/Low 三档，丢弃 Low）。OCR 是"自动化引擎"，双轴是"流程纪律"，叠加使用。安装：`npm install -g @alibaba-group/open-code-review`；委派模式无需配置 LLM。见 `open-code-review` / `open-code-review-delegate` skill
- 规则：仓库文档标准优先于坏味道基线；坏味道是启发式标签非硬性违规；工具已强制的跳过。

### Path E — Spec-Driven Development (NEW, 2026 trend)

Use when ambiguity is costly, the feature is large/multi-step, or user asks for specs. See `sdd-workflow` skill for the full flow.

**v2.1 本地闭环（ticket 全部本地文件，不依赖 tracker）**：

```
to-spec → to-tickets → implement → triage(可选)
```

1. `to-spec` — 对话 → `docs/specs/YYYY-MM-DD-<feature>.md`：Problem Statement / Solution / User Stories(长列表) / Implementation Decisions / **Test Seams 预声明**
2. `to-tickets` — spec → `docs/tickets/YYYY-MM-DD-<feature>/NN-<slug>.md`：垂直切片 tracer-bullet ticket，每张声明阻塞边（前置 ticket 文件名）
3. `implement` — 逐张 ticket：确认 seam → `test-driven-development`（红绿循环）→ 定期 typecheck/单测 → 全量测试 → 双轴 `requesting-code-review` → 提交当前分支
4. `triage`（可选）— 批量 issue 消化：分类(bug/enhancement) → 验证 → 必要时 `grilling` → agent-ready brief

Reference tools (external, no install needed to follow the discipline): GitHub Spec Kit (~110k ⭐, `/speckit.specify → plan → tasks → implement`), OpenSpec (~52k ⭐, living spec), AWS Kiro (requirements/design/tasks docs, EARS notation).

> **T16 指针（v2.6.0 同步）**：MoE/国内模型场景或需要 CI 控制面/状态机/修复阶梯强化时，加载 **`user-vibe_coding-sdk-moe`**（v2.6.0）——spec-kit 深度利用（`specify init` + `spec-tasks-import.py`）、CI/部署状态机（task-state CI_QUEUED..ROLLBACK）、Failure Analyzer（ci-fail-analyze.py）、远程 CI 选择行（reusable workflows）。本主文件热路径不变。

### Path F — Quick Edit / Refactor (small)

```
test-driven-development (light) → verification-before-completion
```

- Skip planning; only touch what the task requires

## Always-On Tools

Load alongside any path above:

- `find-docs` — query current library/API docs (context7). Use whenever libraries are involved
- `context7-cli` — alternative doc lookup via CLI if MCP unavailable（MCP 失效时的备选通道）
- `codebase-memory-mcp` — codebase knowledge graph: architecture, locations, traces before changing code
- `graphify` — 代码知识图谱（60k+ ⭐, YC S26, Apache-2.0）。`/graphify .` 把整个代码库（代码/文档/PDF/图片/视频）映射为可查询知识图谱，输出 graph.html + GRAPH_REPORT.md + graph.json；每条边标注 EXTRACTED/INFERRED；`graphify query/path/explain` 查询代替 grep；MCP 提供 query_graph/get_node/get_neighbors/get_community/god_nodes/graph_stats/shortest_path/list_prs/get_pr_impact/triage_prs。安装：`uv tool install graphifyy`（CLI 在 ~/.local/bin）。与 codebase-memory-mcp 互补：前者偏全仓库理解+可视化+PR 分析，后者偏快速检索/trace
- `code-review-graph` — 代码智能图谱·审查工作流（28.2k ⭐, MIT, Python）。**MCP-first**：30 个 MCP 工具（build_or_update_graph_tool / get_review_context_tool / get_impact_radius_tool 爆炸半径 / query_graph_tool / refactor_tool / semantic_search_nodes_tool / cross_repo_search_tool 等），SQLite 持久化（.code-review-graph/graph.db）+ FTS5 混合搜索 + 可选 embedding；带 7 个 skill（build-graph / review-changes / review-pr / review-delta / explore-codebase / refactor-safely / debug-issue）。安装：`uv tool install code-review-graph`；`code-review-graph install` 自动配置平台。**图谱工具定位**：code-review-graph 偏"审"（审查/爆炸半径/重构安全），codebase-memory-mcp 偏"查"（极速检索/trace），graphify 偏"全仓库理解/可视化"——三者择需使用，避免重复建索引
- `context-modeling` — 维护 CONTEXT.md 领域词汇表 + docs/adr/ 决策记录（术语漂移时触发）
- `handoff` — 多会话长任务交接：压缩会话为交接文档（含 suggested skills、脱敏、引用工件）
- `agentmemory` [MCP] — cross-session persistent memory (25.7k ⭐). Auto-captures decisions, tradeoffs, bug fixes, conventions. Start `npx @agentmemory/agentmemory`, recall via `/recall` or `memory_recall`. R@5 95.2%, saves ~92% tokens vs static CLAUDE.md
- `agent-memory` [MCP alt, NEW] — single-binary Go memory, 14 MCP tools, zero deps, offline FTS5 (+optional local embeddings). `go install github.com/dklymentiev/agent-memory@latest` then `agent-memory mcp`. Pick for zero-infrastructure session memory with auto-capture hooks
- `using-git-worktrees` — isolate work when changes span multiple files
- `finishing-a-development-branch` — merge/PR decision when work is done
- `dispatching-parallel-agents` — when 2+ independent tasks can run concurrently
- `github` — gh CLI for issues, PRs, CI runs, code search (no repo switching needed)
- `xbrowser` — browser automation: web testing, scraping, form fills, screenshots (token-cheaper than raw Playwright)
- `find-skills` — discover & install more skills (skills.sh / `npx skills add owner/repo[@skill]`)
- `gh-project-investigation` — 调研外部 GitHub 项目（并行抓 README+repos API+releases API → trees API → 按需浅克隆；详见该 skill）
- `wb-cli` — WorkBuddy 伪 CLI 解释器（命令解析/路由/会话状态/输出契约）。当用户输入 `/命令` 时优先走该 skill，命令是下方六路径的别名层 + 看门狗（`/wd status|watch|kill|logs|register`）+ 集群编排（`/cluster run|status|collect|cancel`、`/agent ls|use|info`、`/squad`）；规范见 `~/.workbuddy/skills/wb-cli/`（commands.md + references/output-template.md）
- Deployment when done: `web-deploy-github` / `cloudstudio-deploy` / `github-pages-auto-deploy`

## External Tool Sources（v2.1.2）— 找不到工具时的回退渠道

当内置工具/skills 不足以完成任务（缺某个功能的参考实现、缺现成 agent/RAG 模板、缺对应 skill 时），**先检索外部工具源，热门高星优先**。选定后可浅克隆参考或按需摘取。

### 已收录工具源

| 源 | Stars | 内容 | 定位 |
|----|-------|------|------|
| **[Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps)** | 131.6k | 100+ AI Agents、Agent Skills、RAG Apps（Apache-2.0） | LLM/Agent/RAG 应用模板库 |
| **[K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)** | 33.2k | 158+ 科学 Agent Skills、100+ 科学数据库（MIT，各技能独立许可） | 科学/研究技能库（AI Scientist） |
| **[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)** | 85.8k | 24 个生产级工程技能 + 4 人格 + 7 检查清单（MIT） | 工程纪律技能包（SDLC 全周期） |
| **user-vibe_coding-sdk-moe**（本地技能，v2.6.0） | — | MoE 特化编程 SDK：英文思维链 / 路由矩阵 / token 闸门 / 状态机 / 修复阶梯 / CI 控制面（ref-01..24） | MoE/国内模型场景强化版（Path E 默认走 spec-kit） |

### awesome-llm-apps 使用速查

```bash
git clone --depth 1 https://github.com/Shubhamsaboo/awesome-llm-apps.git
```

顶层目录即分类索引，按需导航：

| 目录 | 内容 |
|------|------|
| `starter_ai_agents/`（16 个） | 单文件快速 agent，仅需 API key |
| `advanced_ai_agents/` | 生产级 agent：多 agent 团队 / agent_teams / 单 agent 应用 |
| `agent_skills/`（8 个） | 可直接安装的 coding agent skills |
| `always_on_agents/`（2 个） | 定时/后台常驻 agent |
| `mcp_ai_agents/`（6 个） | MCP 协议 agent（Browser/GitHub/Notion 等） |
| `rag_tutorials/`（24 个） | RAG 检索增强应用（CRAG/Agentic RAG/本地 RAG 等） |
| `voice_ai_agents/`（4 个） | 语音进-语音出 agent |
| `generative_ui_agents/`（8 个） | 生成式 UI / agentic 前端 |

**检索方式**：`gh search code --repo Shubhamsaboo/awesome-llm-apps <关键词>` 定位；或用 `gh api` 列目录。选定应用后读其 README → 按需复制参考代码（注意保持 Apache-2.0 署名）。

### scientific-agent-skills 使用速查

```bash
# 安装（Agent Skills 标准，宿主: Claude Code / Cursor / Codex / Gemini CLI / Antigravity）
npx skills add K-Dense-AI/scientific-agent-skills

# 或 gh CLI（v2.90.0+），可指定单技能 / 宿主 / 版本
gh skill install K-Dense-AI/scientific-agent-skills
gh skill install K-Dense-AI/scientific-agent-skills scanpy
gh skill install K-Dense-AI/scientific-agent-skills --pin v2.62.0

# 手动浅克隆（仅查看/摘取，仓库约 245MB，勿全量克隆进项目）
git clone --depth 1 --branch main https://github.com/K-Dense-AI/scientific-agent-skills.git /tmp/sas
```

**结构**：`skills/<skill-name>/SKILL.md`（YAML frontmatter + `metadata.version`）+ 可选 `scripts/` + `references/`，每个技能独立许可证。

**19 大领域**：生物信息与基因组学、化学信息与药物发现、蛋白质组与质谱、临床研究与证据工作流（PK/PD、ISO/ICH/USP/CLSI）、医疗 AI 与生物信号、医学影像与数字病理、ML/AI、材料与物理、工程与仿真、数据分析与可视化、地理空间与遥感、实验室自动化（Benchling/Opentrons/Ginkgo Cloud Lab）、科学传播（文献综述/论文/PPTX 海报）、多组学与系统生物学、蛋白质工程、研究方法论、法规与标准等。**100+ 数据库**：Database Lookup 统一访问 78 个公共库（PubChem/ChEMBL/UniProt/COSMIC/ClinicalTrials.gov/FRED/USPTO 等）+ DepMap/OneKGPd/Hugging Science/NCATS ARAX 等专项技能。

**检索方式**：`gh api repos/K-Dense-AI/scientific-agent-skills/contents/skills --jq '.[].name'` 列全部技能名；`gh api repos/K-Dense-AI/scientific-agent-skills/contents/skills/<name>/SKILL.md` 读某技能文档；或克隆后 grep `skills/<name>/SKILL.md`。

**注意事项**：① 仓库整体 MIT，但**每个技能有独立许可**，安装/复用前读其 `SKILL.md` 的 `license` 字段；② 工具链前提 Python 3.13+ 与 uv；③ 有 `scripts/` 的技能附带 `tests/`，CI 强制；④ 官方安全声明：技能可执行代码，建议按需安装而非一次全装，先本地扫描。

### addyosmani/agent-skills 使用速查

```bash
# 安装全部 24 个技能 / 浏览 / 按技能安装
npx skills add addyosmani/agent-skills
npx skills add addyosmani/agent-skills --list
npx skills add addyosmani/agent-skills --skill security-and-hardening

# Claude Code 插件方式（SSH 失败时用 HTTPS URL）
/plugin marketplace add https://github.com/addyosmani/agent-skills.git

# 浅克隆（仅 916KB，可全量）
git clone --depth 1 --branch main https://github.com/addyosmani/agent-skills.git /tmp/agsk
```

**SDK 空白技能（按需借鉴）**：`security-and-hardening`（OWASP/密钥/依赖审计）、`performance-optimization`（Core Web Vitals 测量优先）、`observability-and-instrumentation`（结构化日志/OTel/RED）、`api-and-interface-design`（Hyrum's Law 契约优先）、`frontend-ui-engineering`（WCAG 2.1 AA）、`doubt-driven-development`（高风险对抗性自审）、`deprecation-and-migration`（代码即负债）。

**可直接复用的资产**：`agents/` 4 个 Agent 人格定义（code-reviewer/test-engineer/security-auditor/web-performance-auditor）+ `references/` 7 个检查清单（definition-of-done / security-checklist / performance-checklist / accessibility-checklist / observability-checklist 等）。

**设计要点（可作 SDK 增强参考）**：每个 SKILL.md 含 `Process` 分步工作流 + `Rationalizations`（反合理化借口表）+ `Red Flags` + `Verification`（不可协商的证据退出标准）；渐进式披露——SKILL.md 为入口，参考资料按需加载。

**注意事项**：① 全量安装 24 个与本 SDK 已有技能大面积重复（TDD/context-engineering/spec-driven-development 等会撞名），**建议只按需借鉴空白技能或参考其 SKILL.md 结构**；② 单技能 npx 安装不会带上仓库级 `references/`（issue #361），依赖检查清单时需手动复制。

**热门高星优先原则**：多个候选时，优先选 README 置顶展示 / trendshift 推荐 / 近期更新频繁 / stars 更高的项目。

## Tool Routing（v2.1.1）— 模式 → 工具集 静态路由表

Mode Selection 确定后，**自动带上该模式对应的工具集**（下表）。映射是静态的（本表一次加载，约几十 token），执行时按需调用——**不动态列举全部工具**，无关工具不触发。

| Mode | 自动带上的工具（按优先级） | 用途 | 可用性探针 |
|------|--------------------------|------|-----------|
| **Review** | `ocr` CLI → `code-review-graph` MCP（get_review_context_tool / get_impact_radius_tool）→ `graphify` MCP（query_graph）→ `gh` CLI | 行级审查 + 爆炸半径 + 图谱上下文 + PR 数据 | `ocr --version` / 检查 MCP 工具是否在列 |
| **Debug** | `code-review-graph` MCP（debug-issue / query_graph_tool）→ `graphify` MCP（query_graph）→ `codebase-memory-mcp`（trace_path） | 图谱导航定位问题 + 反馈回路 | 同上 |
| **Engineering** | `codebase-memory-mcp`（search_graph / trace_path）→ `code-review-graph`（refactor_tool）→ `graphify`（query_graph）→ `find-docs` | 检索/trace + 重构安全 + 理解代码 + 查库文档 | 同上 |
| **SDD** | `find-docs` / `context7-cli` → `codebase-memory-mcp`（search_graph） | 查文档 + 检索 | 同上 |
| **Vibe** | `graphify`（快速理解代码库，轻量带） | 原型期不重度用工具 | 同上 |
| **Quick Edit** | 无（任务太小，直接改） | 改完验证即可 | 不探测 |
| **Security**（安全/逆向专项） | `reverse-skill-router` → 按需引用 `C:\Users\fu268\.local\share\reverse-skill\skills\<模块>\SKILL.md`（apk-reverse / js-reverse / ghidra-reverse / malware-analysis 等 40+） | APK/JS/二进制逆向、授权渗透、CTF、恶意软件分析 | 检查仓库目录是否存在 |

> **Security 模式注意**：仅处理**授权范围**内的安全/逆向任务。必须遵守 reverse-skill 授权门禁（precedent-auth.md → case-init/scope.md → 未授权禁止 ACT → Evidence→Finding→Path 证据链）。未确认授权时只做分析和报告，不执行攻击性操作。详见 `reverse-skill-router` skill。

### 可用性探针规则

1. **轻量探测**（每会话一次，非每次调用）：进入模式时检查路由表中的工具是否可用——CLI 用 `command -v <bin>`；MCP 检查对应 server 的工具是否已注册（WorkBuddy 连接器已"信任"才会在列表中）。
2. **自动降级**：探测不可用的工具**跳过**，用路由表中的下一顺位替代（如 graphify 不可用 → 用 code-review-graph；两者都不可用 → 用 codebase-memory-mcp 或纯读文件）。降级后**不阻塞任务**，在最终报告中注明"哪些工具不可用、用了什么替代"。
3. **不重复探测**：同一会话内已确认可用的工具直接复用；只有工具报错时才重新探测。
4. **token 原则**：工具调用以"最少必要"为准——先调用能给出最精确答案的工具（图谱查询 > grep 读文件）；一次调用能回答的问题不拆两次。

## Creating / Extending Skills

- Write a new skill → `writing-skills` (or `qclaw-skill-creator`); maintain this SDK the same way
- Installing 3rd-party skills → **security audit first**: Snyk found ~36% of third-party skills carry prompt-injection risk. Only install from official/trusted sources (anthropics/skills, vercel-labs, obra/superpowers, skills.sh top-ranked)

## Rules

1. **No code before plan** — EXCEPT Path B (vibe mode)
2. **No completion without verification** — verification-before-completion is mandatory
3. **Docs over memory** — when using any library/framework, prefer find-docs/context7 over training data
4. **Isolate work** — use git-worktrees for multi-file changes
5. **Context engineering first** — AGENTS.md + CONTEXT.md + docs/adr/ before coding; keep MCP set small (3–6 servers max); skills load lazily by description
6. **Environment conventions** — Python deps via uv; git push requires explicit user confirmation; reply in Chinese by default
7. **双层架构（v2.1）** — 用户调用技能负责编排（grilling/to-spec/to-tickets/implement/handoff/triage 等），模型调用技能承载纪律（tdd/debugging/review 等）；用户调用的技能不互相调用，避免误触发链。
8. **指针式增强维护（v2.1）** — 对现有第三方技能的增强只加一行 `> 增强：…见 user-vibe_coding-sdk §…` 引用，纪律正文放本 SDK 或独立技能；上游覆盖后重加引用行即可恢复。
9. **工具路由（v2.1.1）** — 进入模式后按 §Tool Routing 自动带上对应工具集；调用前轻量探测可用性（每会话一次）；不可用自动降级不阻塞；以"最少必要"为 token 原则，图谱查询优先于 grep 读文件。
