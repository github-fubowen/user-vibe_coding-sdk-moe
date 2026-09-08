# chapter7 · 摘要卡
- id: d-aabook-en-ch07-evaluation · type: book · bytes: 130,551 · sections: 48 · tokens: ~25,439
- source: bojieli/ai-agent-book@006d2368 · sha256: d43ff90df895452e · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
The first six chapters laid out how to build a single Agent: its context, knowledge, tools, coding capabilities, and observation and action spaces. But completing a build does not mean the build is correct; only stable measurement can give subsequent model training and system evolution a reliable direction.

## 高频术语（自动统计 Top-8 · 未校对）
`evaluation`×167 · `model`×153 · `agent`×142 · `task`×99 · `user`×99 · `only`×76 · `system`×75 · `first`×75

## 一句话
第 7 章：Agent 评测——τ²-bench 任务解剖、指标定义、评测环境/数据集设计、LLM-as-a-Judge、统计显著性、可观测性与从外部评测到生产评测基建。

## 章节地图（TOC 压缩，标 ★核心节）
- §Evaluating Agents
- §Anatomy of an Evaluation Task: The telecom Domain of τ²-bench
- §Evaluation Metrics: Defining Success
- §The Evaluation Environment
- §Design of the Evaluation Dataset
- §Automated Evaluation Methods
- §Evaluation-Driven Model Selection
- §Statistical Significance of Evaluation Results
- §Agent Observability
- §From Benchmark Reports to System Improvements
- §From External Evaluation to Internal Evaluation: Evaluation Infrastructure for Production-Grade Agents
- §Simulation Environments: The Bridge from Evaluation to Post-Training
- §Chapter Summary
- §Thought Questions

## 关键条款（≤8 条，每条 ≤2 行）
- 评测任务解剖：τ²-bench telecom 域任务全拆解（Sierra 开源）。
- 指标：0.8 通过率本身无意义；警惕"技术奇观期"（受限条件下的能力天花板）。
- 评测环境五要素：可重复装置 = 环境 + 数据集 + 交互对端等。
- 确定性验证器只能判对错不能归因——LLM-as-a-Judge 的补位与盲区。
- 统计显著性：100 例 70% 的 95% CI ≈ ±9pp——73% vs 70% 是噪声。
- 评测驱动选型：吞吐 vs 延迟两族指标解耦（两阶段推理事实）。
- 可观测性：借用分布式系统概念，从日志/轨迹推断内部。
- 评测→训练桥梁：评测资产无缝转训练信号（衔接 Ch8/Ch9）。

## 与 SDK 的关系
- 已吸收：未吸收——SDK 验证报告/评审报告方法论（置信区间→落盘证据纪律）的出处互证
- 已排除：—
- 未决：—

## 引用约定
注入时打 `<source doc="d-aabook-en-ch07-evaluation" section="§x.y">`；引用必须可回查到本节。
