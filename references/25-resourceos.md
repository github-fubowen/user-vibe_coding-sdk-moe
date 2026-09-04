# ref-25 — ResourceOS：统一资源操作系统（架构对齐参考）

> **性质**：架构对齐参考（指针引用）。源文档为本机文件，非可更新 Git 仓库。
> **源**：`<DOCS>/ResourceOS-Architecture.md`（*ResourceOS — 统一资源操作系统参考架构*，40 节，125KB，2026-09-03 用户提供）
> **吸收判定**：定位为"对齐参考"而非"待实现蓝图"。SDK 资源总量约 50 个（29 脚本 + 23 refs + 少量外部工具），比其 minimal tier 适用下限（10³）低两个数量级 —— 按其自身 §34「scale-driven, not preference-driven」与 §39「Over-engineering for scale not yet needed」两条元原则，**存储/检索/服务化设施整层排除**。

---

## 1. 一句话背景

ResourceOS 把 Skill / Tool / Memory / Reference / Workflow 统一抽象为 **Resource envelope**，以 Registry（元数据与内容分离）+ L0-L4 多级加载 + 混合检索 + Router 七动词 + 依赖图 + 声誉系统 + 生命周期状态机 + SecurityOS 构成一套资源操作系统，目标规模 10²–10⁶ 资源。

**与 SDK 的规模差**：SDK 约 50 资源 → 位于其 §33 规模表最左端之外。因此本轮吸收只取**概念层与数据字段层**，不取设施层。

---

## 2. 采纳条款索引（只列本轮真正落地或改变判断的条款）

| 条款 | 内容 | SDK 落地形态 | 票 |
|---|---|---|---|
| §5 / §7 | 统一资源模型 + Registry 元数据/内容分离 | `toolstack.json` 即简化 envelope：补 `capabilities` / `fallback` / `health` / `last_checked`（schema 3→4） | R-3 |
| §6 | CapabilityOS 能力词表 | 扁平能力词表（顶层 `capability_vocab` 注册 + 新词人工确认，**不建图、不建 closure table**） | R-3 |
| §9 | 混合检索的**置信阈值语义**（自动选 / 呈现 top-K / 回退） | 进 §6 表述；BM25 / 向量 / RRF 设施不引入 | R-6 |
| §10 | Router 七动词之 `resolve`（纯规划、无副作用的依赖预检） | `action-gate` 增 `resolve` 子命令，输出 可执行/降级/阻断 三态 | R-5 |
| §12.1 | SKILL.md 尺寸预算 500–2,000 token | **✅ 已落地** —— 外部背书促成了 F-61 / 清偿包 Epic E（T-541 尺寸闸 + T-542 流水账下沉）：`selfcheck-static` 增 warn >40,000 B / fail >45,000 B 闸（`--max-skill-bytes` 可覆盖），§5.6 闸门流水账下沉 refs，**SKILL.md 39,916B → 36,948B**，清偿包 S-4 判据（≤37,000B）达标。见下方 §7 |
| §14.3 + §32.3 | ContextOS 分类预算表 + 阶段预算 | SKILL §7 增六类软上限 + reasoning 硬底线协议行 | R-6 |
| §17 | 依赖图（顺序依赖数据化） | `ci-smoke` 七步 → `scripts/data/ci-steps.json` manifest；版本/步骤依赖可查 | R-5 |
| §18 | 声誉系统 EMA 成功率 + freshness decay | `router-stats` recommend 增 `confidence`；低样本 → `insufficient` → 回退静态矩阵 | R-8 |
| §19 | 生命周期健康态（三态子集） | 工具级 `active` / `degraded` / `unavailable`；连续 2 次探测失败降级、4 次置不可用 | R-4 |
| §21.1 | 冲突解决：重复检测标记进评审队列 | `toolstack-pipeline` 登记前 Jaccard ≥0.7 查重 warn，**不自动合并** | R-9 |
| §22 | 组合：最常见组合固化 | `ci-steps.json` 即 Workflow 资源化的最小等价物；完整 Composer 排除 | R-5 |
| §24.2 | 可观测：trace 全链重建 | `trace_id` 贯穿 task-state / events.jsonl / trace-export | R-10 |
| §34 / §35 | 技术选型元原则 + 11 条权衡表 | 写入 ALIGNMENT 映射表头与附录，作为本轮所有排除决策的依据 | R-1 |

---

## 3. 明确排除（含依据）

| 排除项 | 依据节 | 理由 |
|---|---|---|
| 向量检索 / FAISS / FTS5 / RRF 混合检索设施 | §9 / §26-27 | 50 资源；§34 规模驱动原则直接否决 |
| 注册中心 HTTP API 服务 | §28 | CLI 即接口（§28 API 与现有脚本 CLI 一一对应），服务化只增运维面 |
| Policy Engine 独立组件 | §20 | `action-gate`（risk_tier 0-4 + tier-4 结构性人审）已覆盖等价面 |
| 7 态完整生命周期 / 容器沙箱 / 异常检测 | §19 / §20.3 | 三态 health 够用；沙箱由宿主管；异常检测 ≈ `ci-fail-analyze` 现状 |
| 完整 Composer / Workflow 资源化 | §22 | 单代理场景，`ci-steps.json` + `task-state` DAG 已覆盖 |
| MemoryOS consolidation（episodic→semantic 离线提升） | §15 | 宿主记忆层已管；SDK 4 层 JSON 保持薄 |
| 10⁴–10⁶ 规模目标 / 多租户 / 分布式拓扑 | §33 / §36 | 规模不匹配 |
| reputation 负信号存储 | §9.2 | 样本量不足以区分"拒绝"与"噪声"；EMA 落地后再评估 |

---

## 4. 与既有架构吸收的关系

ResourceOS 是本 SDK 吸收的第 5 份外部架构规范（前四份：coding-agent-os / verification-kernel / agentic-cicd / agentos，映射见 `ALIGNMENT.md`）。

**互补而非重叠**：前四份提供的是「判断与验证纪律」（状态机 / 五态 / 门禁 / 修复阶梯），ResourceOS 提供的是「资源与调度的元数据面」（能力词表 / 健康态 / 依赖图 / 声誉时间维度 / trace 主键）—— 后者正是 2026-09-03 可维护性评审中「数据面缺失」类缺陷（G-2/G-3/G-6/G-7/G-8）的对应面。

**与 L0-L4 的对应**：本 SDK 的 G2 渐进披露与其 §8 同构（SKILL 主文件 ≈ L1 索引，refs ≈ L3，脚本执行 ≈ L4）；§9 引用表即"何时加载"清单，无需另建加载器。

---

## 5. 批次与版本

| 批次 | 票 | 状态 | 版本 |
|---|---|---|---|
| P0 | R-1 映射表 + 本 ref 指针 | ✅ 已落地 | v2.10.7 |
| **P1** | **R-3 schema 4 · R-4 健康态 · R-5 manifest 化 + resolve · R-6 预算表** | **✅ 已落地** | **v2.10.8** |
| **P2** | **R-7 分类观测 · R-8 EMA/freshness · R-9 查重 · R-10 trace_id** | **✅ 已落地** | **v2.10.9** |

> **版本号裁决（2026-09-03 执行时修正）**：原计划本线占用 v2.14.0+（P0）/ v2.15.0（P1）/ v2.16.0（P2），
> 但 v2.11.0–v2.13.1 已被 `sdd-sdk-improve-v2.11` 清偿包预订。`version-check`（T-16）强制 CHANGELOG
> 条目**严格递减**，若本线按原号段发版，清偿包后续的 v2.11.0 条目插到顶部即判失序 → exit 2。
> 故 P0/P1 两轮按 §10 规则 8 的豁免边界处理（P0 纯文档；P1 数据字段 + 脚本能力，**patch 递增**），
> 只消耗 v2.10.7 / v2.10.8 两个 patch 号，**不占用中间号段**；**v2.14.0 留给 P2**，待清偿包 v2.13.1 收官后启用。

---

## 6. P2 落地形态速查（R-7..R-10）+ 尺寸闸收口

| 票 | 落点 | 入口 |
|---|---|---|
| **R-2 / F-61 / Epic E**（尺寸闸） | `selfcheck-static` 增 SKILL.md 尺寸闸（warn >40,000 B / fail >45,000 B，`--max-skill-bytes` 覆盖 warn）+ **S-4 advisory**（>37,000 B 出 note）；§5.6 闸门流水账下沉 refs | **已落地**（v2.10.10）：**SKILL.md 39,916B → 36,948B**（-2,968B）；清偿包 S-4 判据（≤37,000B）**达标**；输出 `skill_size` 段可读剩余余量 |
| **R-8** | `router-stats` EMA 成功率（半衰期 30 次调用）× freshness decay（exp(-0.05 × 天)，≈13.9 天半衰期）→ `confidence`；与 Thompson 排名**并列**输出，不改排名 | `recommend --json` 的 `reputation` 段；低样本 `insufficient` + `fallback_to_static`（**bandit 仍只是建议**）；三阈值 `--ema-half-life` / `--freshness-decay` / `--min-sample` 可调 |
| **R-9** | `toolstack-pipeline` 登记前查重：name 通道用**重叠系数**（`x-alt` ⊃ `x`），desc 通道用 Jaccard（note+group+category+capabilities） | 任一 ≥0.7 → `suspect-duplicate`；`--update` **扣住不登记**，人工确认后 `--allow-duplicate`；`--dup-threshold` / `--scripts-dir` 可调 |
| **R-7** | `token-meter` 分类观测（system/task/refs/memory/results，与 SKILL §7 逐行对齐）+ 落 `router-stats.db` 的 `context_budget_log` | `--category-budget` 传软上限超限**只提示不拦截**；漏标/未知落 `unclassified` 不丢弃；`--db` 显式才写库 |
| **R-10** | `task-state` trace_id（ULID 风格 26 字符）贯穿 task JSON 头 / 每条 transition 事件 / events.jsonl | `init --trace-id` 可外部指定；`trace-export --trace <id>` 跨任务重建（trace.v1）；转移输出回传 trace_id |
| R-4 | `probe-tools --write-back`：health/last_checked 原子回写，连败 2→degraded、4→unavailable，成功即回 active 并清零 | `action-gate --resolve` 三态；`ci-smoke` 报告 `tool_health` 概览 |
| R-5 | `scripts/data/ci-steps.json`（七步清单 + tier + skip_flag + `@data`/`@sdk` 占位符）；`ci-smoke` 退化为薄 runner | 加第 8 步 = 改 JSON；`action-gate --resolve` 报 ci-smoke 前置步骤 |
| R-6 | SKILL §7 分类预算表（五类软上限）+ reasoning 硬底线 | 压缩规则明细见 ref-21 §3.1 |
