# ALIGNMENT — Coding Agent OS → SDK 落地映射总表

> 吸收对象：`coding-agent-os-architecture.md`（29 节，5 支柱 / 12 组件）
> 吸收对象本体：`user-vibe_coding-sdk-moe`（v2.10.12）
> 本戳受 `version-check.py` 版本戳一致性闸校验（T-511/F-60，七戳含本文件头部）：错戳 exit 2，缺戳仅 warning。
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
| B.6 | 结构化验证事件 | **吸收（v2.10.6）** | ci-fail-analyze `--results-json` 注入 per-test 字段（test_name/expected/actual + per_test_summary/failing_tests）；畸形输入干净 exit 2 |
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
| §15 | 策略引擎 + 策略版本化 | **吸收（v2.10.6）** | patch-gate / action-gate `POLICY_VERSION=gate-policy.v1` + `--policy-version` 校验（不匹配 exit 2）；preset schema 版本已有 |
| §16 | 升级包七字段 | **吸收（T-24，v2.10.0）** | `task-state escalation-pack`：attempted_fixes 聚合自事件台账；ref-22 L5 必附 |
| §3.2 | Agent Tool Gateway | **吸收（T-25，v2.10.0）· v2.10.1 修正** | `action-gate.py` 预执行门（AgentOS Top4 清偿）：存在性/风险分级/args 校验，tier≥4 须 --user-approved。**F-42 修正**：查表范围 = `sdk_tools` ∪ `local_tools`（原仅 `local_tools`，22 个自有脚本全被误判 DENY —— 门装了但没接上电路） |
| §29 | Golden Benchmark + 发布闸 | **吸收（v2.10.6）** | golden-run `--compare old,new` 跨版本对比报告（golden-compare.v1：REGRESSION/FIXED/STABLE/CHRONIC 转移 + token/latency delta；有回归 exit 2 = 发布闸）；`--record` 已有 |
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

---

## ResourceOS-Architecture.md 吸收映射（v2.10.7 补记，R-1）

> 吸收对象：`ResourceOS-Architecture.md`（40 节，125KB，2026-09-03 入库 `WorkBuddy/data/SDK_Reference/`（D 盘））。
> **定位裁决**：架构对齐参考，**不是待实现蓝图**。SDK 资源总量约 50 个（29 脚本 + 23 refs + 少量外部工具），
> 比其 minimal tier 适用下限（10³）低两个数量级 —— 按其自身 **§34「scale-driven, not preference-driven」**
> 与 **§39「Over-engineering for scale not yet needed」** 两条元原则，设施层（存储/检索/服务化）整层排除，
> 吸收走"概念 → 数据字段 → 轻量脚本"三档递减。至此五份架构文档映射齐备（第五份）。
> 明细指针见 `references/25-resourceos.md`（ref-25）。

| 节 | 内容 | 处置 | SDK 落地点 |
|---|---|---|---|
| §1–2 | 执行摘要 / 问题定义 | 吸收（理念） | 静态路由 + 渐进披露已是同一赌注；无新动作 |
| §3 | 11 条设计原则 | 吸收（9/11 已有） | 新采纳 2 条：原则 2「身份便宜/内容贵」→ 工具 `health` 字段（R-4）；原则 8「声誉靠赢得」→ EMA 成功率（R-8） |
| §4 | 系统总览架构图 | 排除 | SDK 无 Kernel/Router 分层必要；本表留指针 |
| §5 | 统一资源模型（16 类 envelope） | 部分吸收 | `toolstack.json` 即简化 envelope；补 capabilities/fallback/health/last_checked → R-3/R-4；16 类分类不引入（脚本+文档两类足够） |
| §6 | CapabilityOS（能力词表/图/别名） | **吸收（最小化）** | 按 mode+group 路由，缺能力层。引入扁平词表 + `capability_vocab` 顶层注册（不建图、不建 closure table）→ R-3 |
| §7 | Registry（元数据/内容分离） | 部分吸收 | `toolstack-pipeline` 已是注册流水线；缺 last_checked/health/内容 hash → R-3/R-4；hash 校验并入现有巡检，不建后台任务 |
| §8 | L0–L4 多级加载 | **已吸收** | G2 渐进披露 = 同构（SKILL 主文件 ≈ L1 索引，refs ≈ L3，脚本执行 ≈ L4）；§9 引用表即"何时加载"清单 |
| §9 | 13 步混合检索 | 部分吸收（仅协议层） | ref-21 六步检索协议已覆盖语义层；不建 BM25/向量/RRF（50 资源无需）；采纳其**置信阈值语义**（自动选 / 呈现 top-K / 回退）进 §6 表述 → R-6 |
| §10 | Router 七动词 | 部分吸收 | action-gate ≈ activate/execute 前置检查；probe-tools ≈ 可用性面；补 **resolve**（依赖可用性预检，纯规划无副作用）→ R-5；不建独立 API |
| §11 | 层级工具发现（family→category→operation） | **已吸收** | §6 静态路由表 + toolstack `group` 字段即两级发现；29 脚本规模下"静态注入优于动态发现"（§35 权衡表支持现状） |
| §12 | Skill 架构（manifest / SKILL.md 分离） | **吸收（校准）** | 机器可读/LLM 可读分离已成立；**尺寸预算**（目标 500–2K token vs 实测 ≈12K）→ R-2，为评审 F-61 提供外部背书 |
| §13 | ProjectOS（工作区/隔离/动态激活） | **已吸收** | `task-workspace.py` per-task worktree 隔离即同构最小形态 |
| §14 | ContextOS（预算分配/装配/压缩） | **吸收（协议层）** | G1-G6 是闸门不是分配器；引入**分类预算表 + reasoning 硬底线**协议 → R-6；不做自动再分配（§14.4 降级为人工纪律） |
| §15 | MemoryOS 八层记忆 | 已吸收（宿主分担） | SDK 4 层 JSON + 宿主三层记忆；episodic→semantic 离线提升排除（宿主记忆已管） |
| §16 | Reference/Knowledge 架构 | **已吸收** | refs 渐进披露 + 指针式外链（ref-10/12/13/14 不 vendored）即其 ingestion 最小形态 |
| §17 | 依赖图（5 类边/拓扑解析/回退替换） | **吸收（最小化）** | 脚本间顺序依赖（version-check→…、ci-smoke 步骤序）现为硬编码 —— 与评审 E-4 同根。manifest 化 → R-5；不建 closure table |
| §18 | 声誉系统（贝叶斯平滑/反流行/新鲜度） | 部分吸收 | router-stats bandit（Thompson）已具探索项；golden cell 即 context-bucketing；**缺 EMA 成功率与 freshness decay** → R-8；负信号存储暂缓（样本量不足） |
| §19 | 生命周期状态机（7 态/健康检查） | 部分吸收 | task-state 15 态是任务级；**工具级无健康态**。引入 active/degraded/unavailable 三态（非全 7 态）→ R-4 |
| §20 | SecurityOS（模型外执行/信任分级/凭据卫生） | **已吸收** | action-gate risk tier 0-4 + tier-4 结构性人审 + privacy-scan + secrets 不进上下文，逐条对账通过；沙箱容器排除（宿主沙箱已管） |
| §21 | 冲突解决（重复检测/优先级阶梯） | 部分吸收 | 优先级阶梯（高层只能收紧不能放权）与闸门语义一致；**缺重复登记检测**（Stage 3b 仅增不删）→ R-9 |
| §22 | 组合（Composer / 工作流资源化） | 部分吸收 | ci-smoke 步骤序即最常见组合的固化形态 → R-5 将其数据化（≈ Workflow 资源化的最小等价物）；完整 Composer 排除 |
| §23 | 失败恢复（重试预算/熔断/单调递减） | **已吸收** | ref-22 L0-L5 + max_repair_attempts=3 + 振荡检测 + flaky-check 前置判别全部对齐；optional+fallback 结构化声明并入 R-3 |
| §24 | 可观测（trace 全链重建 / wasted-token） | 部分吸收 | events.jsonl + trace-export + env-snapshot 已有；**缺跨脚本统一 trace_id** → R-10；wasted-token 指标暂缓（需先有 R-7 分类观测） |
| §25 | 自改进（在线有界 / 离线门禁分离） | **已吸收** | bandit 仅为建议 + 结构变更走 golden 回归，正是 §25.1 的 online/offline 分离；无需新动作 |
| §26–27 | 存储架构 / minimal tier（SQLite+FTS5+FAISS） | **排除** | §34 scale-driven：50 资源 ≪ 10³ 阈值；SQLite 单文件（router-stats.db）已是等价物 |
| §28 | HTTP API 层 | 排除 | CLI 即接口（§28 API 与现有脚本 CLI 一一对应，无需服务化） |
| §29 | 数据库 Schema（17 表） | 参考 | R-3 扩字段时参照其唯一约束（UNIQUE(name,version)）与索引设计 |
| §30 | 目录结构 | **已吸收** | kernel/registry/router 分层不适用，但 scripts/references/presets/data 布局与其精神一致 |
| §31 | 端到端执行示例（全链 10–20K token） | 参考 | 全链 token 基准并入 R-6 预算表作参考锚点 |
| §32 | Token 优化（7 类成本/8 技术/阶段预算表） | 部分吸收 | G-gates 已覆盖渐进披露/缓存/分层；**§32.3 阶段预算表**并入 R-6；token-meter 增分类观测 → R-7 |
| §33 | 规模目标（10²–10⁶ 延迟表） | 排除 | 规模不匹配，整体不适用 |
| §34 | 技术选型（scale-driven 元原则） | **吸收** | 作为本表处置依据写入表头 |
| §35 | 11 条架构权衡表 | **吸收** | 「静态注入 vs 动态发现」「SQLite vs PostgreSQL」「文件系统 vs 对象存储」三条直接支持排除决策，见本附录 |
| §36–37 | NFR / 17 条验收标准 | 部分吸收 | 可测项转化：尺寸预算（R-2）、审计可重建（R-10）；延迟/规模/多租户类排除 |
| §38 | 六阶段路线图 | 参考 | 重排为 P0/P1/P2 批次，不按周执行 |
| §39 | 8 条风险（含过度工程） | **吸收** | 「过度工程」列为本线元原则；其余 7 条逐条对账进计划风险矩阵 |
| §40 | 最终架构图 | 参考 | 本表 + ref-25 留指针 |

**处置统计**：已吸收 12 节 · 部分吸收 16 节 · 新吸收 5 节 · 排除 7 节 · 参考 4 节（按主处置计）。

### 差距与票号（G- 系列 → R- 票）

| 差距 | 内容 | 合并 | 票 |
|---|---|---|---|
| G-1 | 热路径尺寸无预算闸（38.4KB ≈ 12K token，超 §12.1 目标 5–6 倍） | **F-61** | R-2 → 并入 `sdd-sdk-improve-v2.11` Epic E（v2.12.0），本线不重复立项 |
| G-2 | 无能力层（capability） | E-5 部分 | R-3（P1） |
| G-3 | 工具无健康态与生命周期 | — | R-3 + R-4（P1） |
| G-4 | 步骤序/依赖硬编码（ci-smoke 七步写死） | **E-4** | R-5（P1） |
| G-5 | 上下文预算只有闸门没有预算表 | — | R-6（P1）+ R-7 度量面（P2） |
| G-6 | 声誉数据缺时间维度 | — | R-8（P2） |
| G-7 | 注册无查重 | F-63 相关 | R-9（P2） |
| G-8 | 追溯链缺统一 trace_id | — | R-10（P2） |

### 附录：§35 三条权衡表对排除决策的支持

| §35 权衡 | ResourceOS 倾向 | SDK 裁决 |
|---|---|---|
| 静态注入 vs 动态发现 | 大规模→动态发现 | 29 脚本 → **静态注入**（§6 表 + toolstack group）胜出，与其"小规模静态更优"一致 |
| SQLite vs PostgreSQL | 规模驱动 | 50 资源 + 单文件 → **SQLite**（router-stats.db）足够，不引入服务化 DB |
| 文件系统 vs 对象存储 | 规模驱动 | refs / scripts / data 全部 **文件系统**，与 §30 目录精神一致 |

### 批次与版本（2026-09-03 执行时修正）

| 批次 | 票 | 版本 | 状态 |
|---|---|---|---|
| **P0** | R-1 映射表 + ref-25 指针 | **v2.10.7** | ✅ 已落地 |
| **P1** | R-3 schema 4 · R-4 健康态 · R-5 manifest 化 + resolve · R-6 预算表 | **v2.10.8** | ✅ 已落地 |
| P2 | R-7 分类观测 · R-8 EMA/freshness · R-9 查重 · R-10 trace_id | **v2.10.9** | ✅ 已落地 |

> **版本号裁决**：原计划本线占用 v2.14.0+，但 v2.11.0–v2.13.1 已被 `sdd-sdk-improve-v2.11` 清偿包预订。
> `version-check`（T-16）强制 CHANGELOG 条目**严格递减**，若本轮直接跳至 v2.14.0，清偿包后续 v2.11.0 条目插到顶部即判失序 → exit 2。
> 故 **P0（纯文档）+ P1（数据字段 / 脚本能力，无行为破坏）两轮均按 §10 规则 8 豁免边界只做 patch 递增**
> （v2.10.6 → v2.10.7 → v2.10.8），不占用中间号段；**v2.14.0 留给 P2**，待清偿包 v2.13.1 收官后启用。
> R-2（= F-61）已并入清偿包 Epic E，本线只贡献规范引用（§12.1 尺寸预算依据）与验收口径，不动工。
