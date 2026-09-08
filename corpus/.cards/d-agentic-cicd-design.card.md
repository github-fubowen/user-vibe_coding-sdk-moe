# agentic-cicd-design · 摘要卡
- id: d-agentic-cicd-design · type: design · bytes: 80,116 · sections: 51 · tokens: ~12,396
- source: design/agentic-cicd-design.md · sha256: 8f7a52cfb98fc187 · status: absorbed
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
This document specifies an autonomous CI/CD platform in which an AI coding agent acts as the software engineer, and deterministic infrastructure acts as the compiler, test runner, sandbox, policy enforcer, and safety net. The central architectural principle:

## 高频术语（自动统计 Top-8 · 未校对）
`agent`×137 · `test`×83 · `failure`×65 · `tests`×60 · `policy`×47 · `pipeline`×43 · `execution`×38 · `state`×38

## 一句话
Agentic CI/CD 设计：把 CI 从脚本流水线升级为 Agent 化控制面——Temporal 编排、OPA 策略门禁、Firecracker 沙箱、Git 唯一事实源与失败知识库。

## 章节地图（TOC 压缩，标 ★核心节）
- §Autonomous Agent-Native CI/CD Pipeline — Engineering Design Document
- §0. Executive Summary
- §1. Design Principles
- §2. Reference Architecture
- §3. Agent Architecture
- §4. Pipeline Orchestration
- §5. Git-Native Workflow
- §6. Ephemeral Execution & Sandbox Architecture
- §7. Build System
- §8. Testing Architecture
- §9. Failure Intelligence & Automated Repair
- §10. Security Architecture
- §11. CI/CD Integration & Event-Driven Architecture
- §12. Artifact Management & Supply Chain Security
- §13. Deployment & Progressive Delivery
- §14. Observability Architecture
- §15. Policy Engine
- §16. Human-in-the-Loop
- §17. Context Engineering
- §18. Agent Memory & Failure Knowledge Base
- §19. Cost Optimization & Model Routing
- §20. Reliability, Idempotency & Recovery
- §21. Non-Functional Requirements Summary
- §22. Data Model / Database Schema

## 关键条款（≤8 条，每条 ≤2 行）
- Git State Manager：git 为唯一事实源的状态管理，任务状态可回放。
- Temporal 工作流编排：长任务可恢复/可重试/可观测。
- OPA 策略门禁：机器可读策略做发布闸门，非 LLM 裁决。
- Firecracker microVM：任务级强隔离沙箱。
- Failure Knowledge Base：失败案例结构化入库 + 混合检索复用。
- 控制面/数据面分离：Agent 提议、控制面裁决执行。

## 与 SDK 的关系
- 已吸收：ref-24（v2.9.0）· C1-6 · ALIGNMENT.md#agentic-cicd-→-SDK
- 已排除：多租户与云侧扩缩容细节——单机 SDK 场景不适用
- 未决：—

## 引用约定
注入时打 `<source doc="d-agentic-cicd-design" section="§x.y">`；引用必须可回查到本节。
