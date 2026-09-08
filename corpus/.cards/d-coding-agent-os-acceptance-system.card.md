# coding-agent-os-acceptance-system · 摘要卡
- id: d-coding-agent-os-acceptance-system · type: architecture · bytes: 134,621 · sections: 165 · tokens: ~20,042
- source: architecture/coding-agent-os-acceptance-system.md · sha256: 8c67d5fc3f33f786 · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Most "coding agent benchmarks" answer a narrow question: *does this model produce a patch that passes some tests?* That is a code-quality measurement, not an operating-system acceptance test. An **Agent OS** is a system that is trusted to autonomously carry a real engineering task — from an ambiguous requirement to a deployed, monitored, rollback-safe change…

## 高频术语（自动统计 Top-8 · 未校对）
`agent`×176 · `task`×176 · `oracle`×98 · `test`×75 · `evaluation`×70 · `tool`×67 · `failure`×59 · `acceptance`×58

## 一句话
AOS 验收与评测系统——对"Coding Agent OS"本身做独立对抗评测的 Evaluation OS：形式化实验元组、分层 oracle、隐藏测试、故障注入、自治度评测与安全红队。

## 章节地图（TOC 压缩，标 ★核心节）
- §Coding Agent OS Acceptance & Evaluation System (AOS)
- §0. Table of Contents
- §1. Executive Summary
- §2. Design Principles & Formalization
- §3. High-Level Architecture
- §4. Evaluation Pipeline (Data & Control Flow)
- §5. Task Model
- §6. Environment Model
- §7. Agent Runner
- §8. Event/Trace Architecture
- §9. Oracle Architecture
- §10. Hidden Test Architecture
- §11. Fault Injection / Chaos Engine
- §12. Autonomy Evaluation
- §13. Context / Memory Evaluation
- §14. Tool System Evaluation
- §15. Git / Workspace Integrity
- §16. Security Red Team
- §17. Multi-Agent Evaluation
- §18. CI/CD Evaluation
- §19. Performance Evaluation
- §20. Scoring Model
- §21. Acceptance Gates
- §22. Regression System

## 关键条款（≤8 条，每条 ≤2 行）
- §1-2 立场：验收需独立对抗+统计严格的评测 OS，不是跑测脚本；实验 E 定义为元组。
- §5-6 任务/环境模型：每 task_type ≥3 复杂度档（L3/L4 强制）；EnvironmentSnapshot merkle env_hash 保证可复现。
- §9-10 分层 oracle（无单一 LLM-judge 可单独闸门）+ 隐藏测试完整性连续审计。
- §11 故障注入按事件流条件触发（非墙钟），对 Agent 行为可复现。
- §12-13 自治度：能从仓库取到的答案不许问人；10K-10M+ LOC 分层基准防聚合分掩盖短板。
- §15 工作区完整性硬闸门：DataLoss=0、RepositoryCorruption=0。
- §20-22 评分（几何均值惩罚短板）+ 验收闸门：安全回归一票否决。
- §24 验收契约：签名不可变工件，hash 不符拒绝执行。

## 与 SDK 的关系
- 已吸收：未吸收——评测方法论参考；分层 oracle/硬闸门思想已体现在 SDK gate enforcement（四门必绿）
- 已排除：ClickHouse/红队基建——单机不适用
- 未决：SDK golden baselines 扩容时回查 §5/§13 的分层基准设计

## 引用约定
注入时打 `<source doc="d-coding-agent-os-acceptance-system" section="§x.y">`；引用必须可回查到本节。
