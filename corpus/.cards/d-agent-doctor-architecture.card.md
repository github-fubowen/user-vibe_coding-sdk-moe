# agent-doctor-architecture · 摘要卡
- id: d-agent-doctor-architecture · type: architecture · bytes: 49,276 · sections: 43 · tokens: ~8,045
- source: architecture/agent-doctor-architecture.md · sha256: c52eea800178cb03 · status: absorbed
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Agent Doctor is a control-plane system that observes, diagnoses, and repairs modern AI agent ecosystems — the agents themselves, their MCP servers/tools/skills, their runtime environments, and the LLM APIs they depend on. It is not a single agent and not a wrapper around one model provider. It is a **hierarchical multi-agent system sitting on top of a statef…

## 高频术语（自动统计 Top-8 · 未校对）
`model`×111 · `agent`×59 · `string`×54 · `incident`×49 · `number`×47 · `doctor`×41 · `engine`×40 · `task`×36

## 一句话
Agent Doctor——模型无关的 Agent 生态"医院"控制面：分层多智能体系统，观测/诊断/修复 Agent 本体、MCP/工具/技能、运行环境与 LLM API 依赖。

## 章节地图（TOC 压缩，标 ★核心节）
- §Agent Doctor: Architecture of an Autonomous, Model-Agnostic AI Operations & Diagnosis Platform
- §Table of Contents
- §1. Executive Summary
- §2. Design Philosophy
- §3. Core Design Principles
- §4. Full System Architecture
- §5. Agent Hierarchy
- §6. Model-MOE Architecture
- §7. Dynamic Routing Algorithm
- §8. System World Model
- §9. Observability Layer
- §10. Diagnosis Engine
- §11. Hypothesis & Experiment Engine
- §12. Repair Engine
- §13. Verification Engine
- §14. Incident Memory
- §15. Adaptive Learning
- §16. Security Architecture
- §17. Failure Handling
- §18. Cost Optimization
- §19. Data Model
- §20. Internal Protocols & API Design
- §21. Technology Stack
- §22. Deployment Architecture

## 关键条款（≤8 条，每条 ≤2 行）
- §2-3 设计哲学与核心原则：诊断=假设→实验→验证闭环，规则匹配只是入口；模型无关、故障优先。
- §5-7 Agent 层级 + Model-MOE + 动态路由：按症状特征路由专科诊断 Agent（SDK 状态化路由来源）。
- §8 System World Model：环境与依赖链的内部状态表示，支撑根因定位。
- §10-13 诊断/假设实验/修复/验证四引擎：修复动作分级、验证闭环防回归。
- §14-15 Incident Memory + 自适应学习：事故记忆反哺诊断策略（SDK 五态生命周期来源）。
- §16-17 安全与失败处理：修复权限分层 + 失败降级路径。
- §9/§18 观测与成本：全链路追踪、按诊断深度控成本。

## 与 SDK 的关系
- 已吸收：ref-17（v2.10.0）· ALIGNMENT.md（五态/状态化路由/风险分层来源）· 票号：—
- 已排除：§21-22 技术栈/部署拓扑章节——SDK 单机场景不适用
- 未决：—

## 引用约定
注入时打 `<source doc="d-agent-doctor-architecture" section="§x.y">`；引用必须可回查到本节。
