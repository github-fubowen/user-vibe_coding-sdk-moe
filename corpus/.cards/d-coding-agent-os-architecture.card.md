# coding-agent-os-architecture · 摘要卡
- id: d-coding-agent-os-architecture · type: architecture · bytes: 60,676 · sections: 51 · tokens: ~10,730
- source: architecture/coding-agent-os-architecture.md · sha256: f4198650f34c7678 · status: absorbed
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
This document specifies a production architecture for a Coding Agent OS: a system that autonomously understands, plans, implements, verifies, and repairs software changes using a heterogeneous pool of API-based LLMs (Claude, GPT, Gemini, DeepSeek, Qwen, etc.), routed and orchestrated like a Mixture-of-Experts operating at the *service* level rather than insi…

## 高频术语（自动统计 Top-8 · 未校对）
`model`×134 · `task`×97 · `context`×53 · `memory`×53 · `router`×53 · `tool`×47 · `repair`×45 · `state`×45

## 一句话
Coding Agent OS——软件工厂形态的编码 Agent 参考架构：任务状态机、修复升级阶梯、上下文工程与成本闸门的控制面设计。

## 章节地图（TOC 压缩，标 ★核心节）
- §Coding Agent OS — Production Architecture
- §1. Executive Summary
- §2. Design Goals
- §3. Design Principles
- §4. Global Architecture
- §5. Core Components
- §6. Model-Level MoE Router
- §6.1 Expert taxonomy (concrete, not abstract)
- §6.2 Routing is two-stage, not one formula
- §6.3 Why not learned RL / full policy learning
- §6.4 Escalation and consensus as router features, not separate systems
- §6.5 Routing decision record
- §6.6 Hierarchical Model Escalation
- §7. Context Engineering
- §8. Repository Intelligence
- §9. Tool / MCP Router
- §10. Agent Orchestrator
- §11. Blackboard / State Machine
- §11.1 Task State Machine
- §11.2 Task State Schema
- §11.3 Blackboard
- §12. Verification Engine
- §13. Repair Engine
- §14. Memory System

## 关键条款（≤8 条，每条 ≤2 行）
- 任务状态机：VERIFY/REVERIFY 可回环 DIAGNOSE 的 DAG（带修复预算），非线性链。
- 修复升级阶梯：验证失败按阶梯升级处理，非盲目重试。
- 上下文工程：最小充分上下文 + 严格选择算法（§7）。
- 成本/预算闸门：超预算任务转 ESCALATED 而非静默降级。
- 记忆分层：失败复用结构化匹配优先（§14）。

## 与 SDK 的关系
- 已吸收：ref-20/ref-22（v2.10.0）· T-19..T-26 · ALIGNMENT.md（任务状态机/修复升级阶梯来源）
- 已排除：—
- 未决：—

## 引用约定
注入时打 `<source doc="d-coding-agent-os-architecture" section="§x.y">`；引用必须可回查到本节。
