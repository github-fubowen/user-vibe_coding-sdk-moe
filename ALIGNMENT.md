# ALIGNMENT — Coding Agent OS → SDK 落地映射总表

> 吸收对象：`coding-agent-os-architecture.md`（29 节，5 支柱 / 12 组件）
> 吸收对象本体：`user-vibe_coding-sdk-moe`（v2.10.2）
> 三分类：**协议**（doc，判断纪律）· **脚本**（deterministic，零 LLM）· **排除**（指针引用，不落地）
> 逐节映射如下；实施细节见各 ref 与 SKILL.md。

| 架构节 | 内容 | 处置 | SDK 落地点 |
|---|---|---|---|
| §1 | Executive Summary（LLM 最贵最不可靠 → 少用） | 吸收 | SKILL.md §0 原则 1、§3 G-gates 全部 |
| §2 | Design Goals | 吸收 | SKILL.md 三大目标 |
| §3 | Design Principles | 吸收 | SKILL.md §0（确定性先行） |
| §4 | Global Architecture | 吸收 | 本表即映射 |
| §5 | Core Components | 吸收 | 见 §6-§19 各行 |
| §6 | Model-Level MoE Router | 吸收 | 静态矩阵（SKILL §4）+ **router-stats.py**（§6.2 两级：硬过滤留 agent，bandit 离线） |
| 6.1 | Expert taxonomy | 吸收 | ref-02 + golden-set v3 cell 标签（8 cell） |
| 6.2 | Two-stage routing | 吸收 | router-stats.py（stage 2）；stage 1 硬过滤 = agent 用 §4 矩阵 + toolstack.json |
| 6.3 | 为什么不用 RL | 吸收 | bandit（Beta 后验）即轻量选择，文档化 |
| 6.4 | Escalation 作路由特性 | 吸收 | **ref-22** L0-L5 阶梯 |
| 6.5 | Routing decision record | 脚本 | router-stats.py `routing_log` 表（record） |
| 6.6 | Hierarchical Model Escalation | 吸收 | ref-22（重试预算 2/2/2/1/1 + 熔断） |
| §7 | Context Engineering | 吸收 | **ref-21** + SKILL §7（稳定前缀）+ 检索 6 步 |
| §8 | Repository Intelligence | 排除（指针） | 复用 code-review-graph / codebase-memory-mcp（MCP 连接器，不本地实现） |
| §9 | Tool / MCP Router | 吸收 | **toolstack.json v2**（risk_tier/idempotent/timeout_ms/retryable + provider_health）+ probe-tools |
| §10 | Agent Orchestrator | 吸收 | **ref-20**（任务状态外置）+ SKILL §1 mode selector |
| §11 | Blackboard / State Machine | 吸收 | **ref-20** + **task-state.py**（转移表为数据） |
| 11.1 | Task State Machine | 脚本 | task-state.py（15 状态 / 转移集 / 终态） |
| 11.2 | Task State Schema | 脚本 | task-state.v1 JSON schema |
| 11.3 | Blackboard | 吸收 | ref-20 §5（5 条更新规则，写入靠 agent 纪律） |
| §12 | Verification Engine | 吸收 | **verify-runner.py v2.0**（9 层 cheapest-first 短路）+ golden-run + robustness-suite |
| §13 | Repair Engine | 吸收 | **ref-22**（补丁隔离/回滚走 git §10.7） |
| §14 | Memory System | 吸收 | 失败层（error-sig/case-search）+ 任务层（workspace 日志）+ **4 层 JSON**（repo-facts/conventions/solutions/preferences）；嵌入=指针 |
| §15 | Multi-Agent System | 吸收（协议行） | ref-20 §7 单代理默认 + 条件启用（T0/Review 双轴/L4 共识） |
| §16 | Cost / Token Optimization | 吸收 | §3 G-gates + token-meter（预算跟踪 T10）+ router-stats 指标（T13） |
| §17 | Security / Risk Engine | 吸收 | SKILL §10.9 风险分层表（低/中/高/不可逆 4 档）+ toolstack risk_tier |
| §18 | Observability | 吸收 | env-snapshot + task-state trace-export（JSON trace，替代 OTel） |
| §19 | Evaluation Framework | 吸收 | golden-run + golden-set v2/v3 + baselines + router-stats 校准 |
| §20 | Storage Architecture | 排除 | SQLite/JSON 即存储（router-stats.db / task JSON / memory JSON） |
| §21 | Deployment Architecture | 排除 | 技能层无部署；git 即分发 |
| §22 | Low-Resource Deployment | 吸收 | 全部脚本 stdlib 零依赖；SQLite 单文件 |
| §23 | Failure Analysis | 吸收 | robustness-suite（故障注入回归）+ error-sig 签名库 |
| §24 | Technology Stack | 排除（指针） | Python stdlib + git；无 Redis/Postgres/Firecracker |
| §25 | Recommended MVP | 吸收 | 本 SDK 即 MVP 形态（文档+脚本） |
| §26 | Phase 2 | 吸收 | v2.x 四阶段路线图（本表） |
| §27 | Phase 3 | 排除（指针） | 规模化组件（在线路由/观测平台）留未来 |
| §28 | Final Architecture | 吸收 | 28.3 诊断 schema（diagnostic.v1）· 28.4 状态机（ref-20）· 28.5 路由（router-stats）· 28.6 token（token-meter）· 28.7 工具路由（toolstack.json）· 28.8 失败恢复（ref-22）· 28.9 技术栈（排除）· 28.10 MVP 顺序（四阶段）· 28.11 风险（先验种子/冷启动）· 28.12 20/80（四高价值组件优先） |
| §29 | 每 token/美元吞吐 | 吸收 | 指标看板（cost per successful task 等），§8 每月回归 |

## 组件责任矩阵（§28.2 对照）

| 组件 | 架构职责 | SDK 承接者 | 类型 |
|---|---|---|---|
| Orchestrator | 状态/编排 | agent（SKILL §1 模式选择）+ task-state.py | 协议+脚本 |
| Context | 最小充分上下文 | ref-21 + SKILL §7 | 协议 |
| Router | 两级选择 | SKILL §4 + router-stats.py | 协议+脚本 |
| Verifier | 确定性验证 | verify-runner.py + golden-run + robustness-suite | 脚本 |
| Repair | 修复/升级 | ref-22 + ref-18 | 协议 |
| Memory | 分层记忆 | memory/ 4 层 + error-sig + case-search + task JSON | 数据+脚本 |
| Budget | 成本控制 | §3 闸门 + token-meter | 协议+脚本 |
| Risk | 风险分级 | §10.9 + toolstack risk_tier | 协议+数据 |
| Observability | 可观测 | env-snapshot + trace-export | 脚本 |
| Eval | 回归评估 | golden-run + 基线 + 校准 | 脚本+数据 |

## 排除总表（为什么不落地）

| 排除项 | 架构节 | 原因 |
|---|---|---|
| Redis/Postgres/pgvector | §20/24 | SQLite 单文件足够（技能层规模） |
| Firecracker/Docker 沙箱 | §24 | 本机环境即沙箱；高危动作人工门禁代替 |
| OTel 采集/仪表盘 | §18 | JSON trace（task-state trace-export）降级替代 |
| 在线路由服务/多租户 | §6/21 | bandit 离线反馈；模型选择权留用户 |
| 嵌入向量服务 | §8/14 | 结构化匹配优先；本地 embedding 资产可另接（指针） |
| 多代理常驻框架 | §15 | 单代理默认 + 按条件启用（ref-20 §7） |
| 持久化 repo map（tree-sitter 索引） | survey G1 | 按需 tree/glob + codebase-memory MCP 已覆盖；离线索引维护成本 > 收益（2026-09-01 D3=A 决策） |
| 上下文压缩服务（独立常驻） | survey G2 | 黑板压缩（ref-20 §5）+ ref-21 §6 压缩时机已覆盖技能层规模 |
| 离线 embeddings 语义检索 | survey G7 | 结构化匹配优先；本地 embedding 资产可另接（指针保留） |
| 高风险命令沙箱逃生通道 | survey G8 | §10.9 tier-4 人工门禁即闸门；双轨制徒增攻击面 |
| spec-kit 全量落地 | §25-26 | 指针引用 ref-08（specify CLI 按需 `uv tool run`） |
| Property-based testing 落地 | vk §B.12（2026-09-01 文档） | 协议化：纯函数 + 可推断不变量（round-trip/idempotence）才值得做；技能层脚本以确定性单例为主，收益/成本不匹配（T-28，ref-21 §6 附选择策略） |
| Mutation testing 落地 | vk §B.13（2026-09-01 文档） | 协议化：kill-rate 只对关键路径有信号；全量突变在 16GB 低配机上不可承受；留待 CI 有预算时按需（T-28） |
| 覆盖率驱动测试选择 | vk §B.5/ACI §8.3 完整形态 | T-22 只做约定映射（stdlib 零依赖）；coverage→test 二分图需插桩与持续维护，与"持久化 repo map（G1）"同类排除（2026-09-01 D2=A） |

## 未吸收项与原因

- **§26/§27 规模化阶段**：观测平台、多租户、自动化补丁服务 —— 超出技能层职责，留待真正服务化时再吸收（届时本表即迁移蓝图）。

---

## 09-01 两文档吸收映射（v2.9.0，T-30）

> 吸收对象：`verification-kernel-architecture.md`（验证与自愈内核，55KB）· `agentic-cicd-design.md`（Agent-Native CI/CD，80KB），2026-09-01 入库 `WorkBuddy/data/SDK_Reference/`（D 盘）。
> 两文档共同结论：**验证是产品不是步骤**（kernel）+ **确定性基础设施承重，LLM 不进信任边界**（CI/CD）。

### verification-kernel → SDK

| 节 | 内容 | 处置 | 落点 |
|---|---|---|---|
| B.3 | 12 阶段渐进验证（cheapest-first 短路） | 已吸收 70% | verify-runner 分层 + T-16 version-check 置 ci-smoke 第 0 步；Stage 6/7/8（module/integration/e2e）分层留 preset 自定义 |
| B.4 | Test Discovery（adapter 模型） | 排除 | 3 套随包预设即降级替代 |
| B.5 | 测试选择（changed→受影响测试） | **吸收（T-22）** | `verify-runner --changed` 约定映射；覆盖率驱动排除（见上表） |
| B.6 | 结构化验证事件 | 部分 | diagnostic.v1 有 step/exit_code/error_class/origin；per-test 字段（test_name/expected/actual）留 P3 |
| B.7 + H | 失败分类 + origin class | **吸收（T-19）** | ci-fail-analyze `origin` + ACTION_BY_ORIGIN |
| B.10 | Flaky 检测 + quarantine | **吸收（T-20）** | flaky-check.py（N≥5 + 变率门槛；隔离不删除） |
| B.11 | 回归测试双向校验 | **吸收（T-21）** | regression-guard.py（base FAIL + head PASS） |
| B.12/B.13 | Property-based / Mutation | 排除（协议化，T-28） | 见排除总表 |
| B.19 | 多代理省着用 | 已吸收 | ref-20 §7 单代理默认 |
| B.20 | 按复杂度路由 | 已吸收 | SKILL §4 分层矩阵 |
| B.21 | 修复/诊断/回归三重置信度 | **吸收（T-23，v2.10.0）** | `diff-risk --verify-confidence` 合成 `repair_confidence`（<0.7 强制人工）；回归置信度由 regression-guard 双向闸承当 |
| I | 修复预算 8 项 | **吸收 4/8（v2.10.0）** | 次数（task-state）+ files/lines/依赖变更（patch-gate，T-23）；runtime/tokens/commands/recursion 留 CI 预算域 |
| J | 修复上下文检索顺序 | 已吸收 | ref-21 检索 6 步 |

### agentic-cicd → SDK

| 节 | 内容 | 处置 | 落点 |
|---|---|---|---|
| §1 原则 1-5/7/8 | 推理/执行分离 · 结构化失败 · 状态机 · 上下文工程 · 凭据 JIT | 已吸收 | SKILL §1/§6/§7 · ref-20 · ref-21 · ref-24 |
| §1 原则 6 | 修复有界 | **已吸收（v2.10.0 补齐）** | ref-22 次数/振荡 + patch-gate 规模预算（T-23）+ repair_confidence<0.7 人工（B.21） |
| §1 原则 9 | 幂等性 | **吸收（T-26，v2.10.0）** | task-state `--idempotency-key`（重放 no-op 不耗预算）+ action-gate 消费 idempotent 元数据 |
| §8.3/8.4 | TIA + flaky 四分类 | **吸收（T-22/T-20）** | 见上表 |
| §15 | 策略引擎 + 策略版本化 | 部分 | preset 带 schema 版本；硬闸参数钉版本留 P3 |
| §16 | 升级包七字段 | **吸收（T-24，v2.10.0）** | `task-state escalation-pack`：attempted_fixes 聚合自事件台账；ref-22 L5 必附 |
| §3.2 | Agent Tool Gateway | **吸收（T-25，v2.10.0）· v2.10.1 修正** | `action-gate.py` 预执行门（AgentOS Top4 清偿）：存在性/风险分级/args 校验，tier≥4 须 --user-approved。**F-42 修正**：查表范围 = `sdk_tools` ∪ `local_tools`（原仅 `local_tools`，22 个自有脚本全被误判 DENY —— 门装了但没接上电路） |
| §29 | Golden Benchmark + 发布闸 | 部分 | golden-run `--record` 已有；跨版本对比报告留 P3 |
| §22-23/§26 | Postgres/NATS/Temporal/K8s/OPA | 排除 | 技能层无服务端 |
| §12 | SLSA 产物溯源 | 排除（指针） | 与 gh-workflow-check 相邻，暂不落地 |

---

## v2.10.1–v2.10.2 追加映射（2026-09-01 全面自检驱动）

> 来源：本轮 `验证报告-SDK-v2.10.1-全面自检与测试-2026-09-01.md`。
> 教训：**映射表记"吸收了什么"，但没记"吸收后是否真的通电"**——§3.2 记为「已吸收」，实际 22/22 自有脚本被拒。
> 故本表新增一列性质：**自检项**（能否被自动化验证，而非仅靠人工回忆）。

| 来源节 | 内容 | 处置 | 落点 | 自检项 |
|---|---|---|---|---|
| kernel §I | 修复预算（files/lines/依赖） | 已吸收（T-23） | patch-gate.py | ✅ robustness 4 例 |
| cicd §16 | 升级包七字段 | 已吸收（T-24） | task-state escalation-pack | ✅ robustness 3 例 |
| cicd §1-9 | 幂等键 | 已吸收（T-26） | task-state --idempotency-key | ✅ robustness 3 例 |
| cicd §3.2 | 动作预执行门 | **v2.10.1 修正** | action-gate（sdk_tools ∪ local_tools） | ✅ robustness 8 例（原 4 例只测 local_tools，正是盲区） |
| — | **工具栈漂移自检（新增）** | **v2.10.1 新增 · v2.10.2 补强** | `selfcheck-static.py`（frontmatter/refs/脚本/toolstack 四项） | ✅ robustness 4 例 + ci-smoke 第 2 步 + pre-commit 第 4 闸 |
| — | **sdk_tools 自动化巡检（新增）** | **v2.10.2 新增** | `toolstack-pipeline.py` Stage 3b：scripts/ 与 sdk_tools 差集 | ✅ 差集检出 + `--update` 自动登记（仅增不删） |
| — | 提交时刻结构闸（新增） | **v2.10.2 新增** | `git-pre-commit.py` 闸 4：任何 SDK 改动即跑 selfcheck-static | ✅ dry-run 正负两例验证 |

---

## agentos-architecture.md 吸收映射（v2.10.5 补记，F-54）

> 吸收对象：`agentos-architecture.md`（A-U 节，798 行）。盘点始于 v2.7.0 自查（§2.4：17 吸收 / 排除 / Top5 缺口），
> 缺口经 v2.8.0（T-07/08/09/13）与 v2.10.0（T-25）清偿，但映射表一直未入 ALIGNMENT（F-54：追溯断链）。
> 本节补齐——至此四份架构文档（coding-agent-os / verification-kernel / agentic-cicd / agentos）映射齐备。

| 节 | 内容 | 处置 | SDK 落地点 |
|---|---|---|---|
| A/B/C | Executive Summary / 心智模型 / 架构图 | 吸收/排除 | SKILL §0；B/C 为类比与图示，无落地物 |
| D | 分层架构 | 吸收 | SKILL §1 模式选择 + 协议/脚本分景 |
| E | 内核不变量 + 内核/用户态边界 | 吸收（协议） | 确定性脚本=内核（闸门），agent 判断=用户态（裁决）；§5.6 五态判定留 agent 即此边界 |
| F | Agent 进程模型（原语/状态/对比） | 吸收 | task-state.v1（15 态状态机）+ checkpoint/resume（v2.6.0） |
| G | 上下文/记忆架构 | 吸收 | ref-21（检索协议）+ ref-20（黑板）+ memory 4 层 JSON |
| H | 工具架构（H.1 契约 / H.2 MCP / H.3 发现与沙箱） | 吸收 | toolstack.json schema 3（risk_tier/idempotent/timeout_ms，T-11）+ probe-tools（发现）+ action-gate（执行前强制） |
| I/J | 运行时沙箱 / 调度器 | 排除 | 本机即沙箱 + tier-4 人工门禁；无常驻调度（宿主 automations 承担） |
| K | 多代理 | 吸收 | ref-20 §7 单代理默认 + 条件启用 |
| L | IPC / 代理通信 | 排除 | 黑板（ref-20 §5）+ 宿主消息机制替代 |
| M | 持久化 | 吸收 | SQLite（router-stats.db）+ task JSON + events.jsonl（T-10） |
| N | 安全模型（能力制 / N.2 策略示例） | 吸收 | §10.9 风险四档 + action-gate tier≥4 须 `--user-approved`（T-25，Top4 清偿；F-42 v2.10.1 修正查表范围） |
| O | 可观测 | 吸收（降级） | env-snapshot + trace-export JSON（OTel 排除，同 coding-agent-os §18） |
| P | 失败与恢复 | 吸收 | 五态验证（§5.6）+ CRASHED 可恢复态 + ref-22 阶梯 + error-sig/case-search |
| Q/R | 技术栈 / 仓库结构 | 排除 | stdlib-only 既定决策；技能层布局固定 |
| S | 核心数据结构 | 吸收 | task-state.v1 · diagnostic.v1（origin/recommended_action，T-19）· blackboard schema |
| T/U | 执行序列 / 安全序列 | 吸收 | ci-smoke cheapest-first 步序 + verify-runner 9 层 + action-gate 预执行序列 + pre-commit fail-closed |

### Top5 缺口清偿对账（v2.7.0 §2.4 → 现状）

| # | 缺口 | 清偿 |
|---|---|---|
| 1 | 置信度信号驱动自适应验证深度 | ✅ T-07（v2.8.0）`verify-runner --confidence` |
| 2 | 上下文溯源台账 + 过期驱逐 | ✅ T-13（v2.8.0）ref-21 §7 |
| 3 | 任务级显式完成条件 | ✅ T-08（v2.8.0）`--done-when`/`--done-evidence` |
| 4 | Action Validator 预执行门 | ✅ T-25（v2.10.0）action-gate |
| 5 | 故障分类扩展 | ✅ T-09（v2.8.0）taxonomy 5→8 类 |
