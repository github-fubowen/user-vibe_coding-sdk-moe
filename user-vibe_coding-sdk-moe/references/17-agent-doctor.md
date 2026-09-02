# ref-17 — Agent Doctor：控制面纪律吸收记录

> **性质**：设计原则来源（指针引用）。源文档为本机文件，非可更新 Git 仓库。
> **源**：`<DOCS>/agent-doctor-architecture.md`（*Agent Doctor: Architecture of an Autonomous, Model-Agnostic AI Operations & Diagnosis Platform*，26 章，2026-08 用户提供）
> **吸收判定**：仅吸收"可编码为 prompt/流程纪律"的部分；软件系统级组件（graph DB、bandit 数学、多 agent 编排）明确排除。

---

## 1. 一句话背景

Agent Doctor 是一个 **AI Ops 控制平面**架构：把每个 LLM 视为带能力/成本/延迟/可靠性画像的异构专家，用 **Observe → Detect → Diagnose → Hypothesize → Experiment → Plan → Execute → Verify → Recover → Learn** 闭环做自治诊断与修复，并在"诊断（便宜、可并行）"与"行动（昂贵、需门禁）"之间划硬信任边界。

## 2. 吸收映射（本 SDK 已落地）

| 概念（源文档章节） | 落地形态 | 落点 |
|---|---|---|
| Model-MOE Router（§6-7） | 路由前 Pareto 硬过滤清单 + 每次路由必带 `fallback_chain` | SKILL.md §4 |
| 混合诊断：规则先行、LLM 后置（§10） | Debug 模式"确定性先行"阶段 | ref-18 |
| Hypothesis / Evidence / Experiment（§10-11） | Debug 假设协议：证据链 + 预期观察 + 推荐实验 | ref-18 |
| 验证五态（§13） | SUCCESS / PARTIAL / FAILED / REGRESSION / UNKNOWN 判定 | SKILL.md §5.6 + ref-18 |
| 风险分层 tier 0-4 + can_act（§16.1） | 操作策略门（写操作 2 级 / 破坏性 3 级 / 不可逆 4 级必人批） | SKILL.md §10.9 |
| Early exit / cheap-first 级联（§18） | 置信度达标即停；本地模型先分类/过滤再升级 | §4 路由规则 + G6 |

## 3. 吸收为启发式（月度巡检级）

- **ModelProfile 经验回写（§7.4）**：会话统计（mode/model/任务类/成败/耗时）→ 月度人工审阅反哺路由矩阵。轻量实现见 ref-15 流水线扩展思路（`scripts/` 下 JSON 统计），未单独建脚本。
- **Incident Memory 轨迹复用（§14）**：问题案例库（症状→假设→实验→修复→验证轨迹），相似故障先查库再诊断。案例格式见 ref-18 §5。
- **降级链分层（§17）**：provider 故障 → 同厂换模型 → 本地模型 → 缓存轨迹复用 → 纯规则确定性规程。每层仅在前一层确认不可用时激活。

## 4. 明确排除（软件系统组件，不落地）

| 组件 | 排除理由 |
|---|---|
| World Model 图数据库（§8） | 依赖关系图对 prompt-SDK 过重；现有 code-review-graph MCP 已覆盖影响半径查询 |
| Thompson Sampling / Pareto 数学实现（§7.2） | 单会话单模型场景无状态累积条件；仅保留"过滤+降级链"启发式 |
| 16 专家多 agent 编排（§5） | SDK 是单 agent 协议；模式选择器（§1）已承担"专家选择"职能 |
| 跨模型辩论（§6.4） | 高不确定任务可选"双模型交叉验证"技巧，但不作默认流程 |
| EIG / 贝叶斯更新数学（§11） | 保留"廉价+可逆+高信息量"实验选择启发式，去掉公式 |

## 5. 更新配方

源文档为本地单文件，无上游版本管理。以下情况手工同步：

1. 源文档更新（用户替换 `<DOCS>/agent-doctor-architecture.md`）→ 对照 §2/§3 映射表核对是否有新可吸收概念。
2. 每次 SDK 大版本修订时复核 §4 排除项是否仍成立。
3. 本文件为设计依据记录，不参与工具栈巡检（ref-15 不覆盖）。
