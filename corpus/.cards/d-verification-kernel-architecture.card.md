# verification-kernel-architecture · 摘要卡
- id: d-verification-kernel-architecture · type: architecture · bytes: 55,941 · sections: 39 · tokens: ~9,205
- source: architecture/verification-kernel-architecture.md · sha256: 717cf1528318bde5 · status: absorbed
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
The system in this document is **not** a coding assistant. It is a **Verification Kernel**: an independent, deterministic-first control plane that sits between a Coding Agent and a codebase, and whose sole job is to answer one question with authority — *"Is this change actually correct, safe, and non-regressive?"*

## 高频术语（自动统计 Top-8 · 未校对）
`test`×88 · `failure`×82 · `string`×79 · `patch`×64 · `stage`×43 · `regression`×42 · `agent`×40 · `repair`×38

## 一句话
Verification Kernel——独立于编码 Agent 的确定性优先验证控制面：写补丁的模型不再自裁对错，验证/诊断/修复/回归由独立内核驱动。

## 章节地图（TOC 压缩，标 ★核心节）
- §Verification & Self-Healing Kernel
- §A. Executive Architecture
- §B. Detailed Architecture
- §C. Component Diagram
- §D. Data Flow: Code → Test → Failure → Diagnosis → Patch → Regression
- §E. State Machine
- §F. Data Schemas (TypeScript)
- §G. Tool Adapter Interface
- §H. Failure Taxonomy
- §I. Repair Policy
- §J. Token Optimization
- §K. Security Model
- §L. Technology Stack
- §M. MVP Architecture
- §N. Production Architecture
- §O. Example Execution — Five Scenarios
- §End-to-End Trace — "Add password reset functionality"
- §P. Implementation Roadmap

## 关键条款（≤8 条，每条 ≤2 行）
- §A-B 独立控制面：写与验分离，规避自评三类失效（重读自己的坏代码找认同等）。
- §E 状态机：终态 SUCCESS/ROLLED_BACK/ESCALATED/BLOCKED/TIMEOUT/BUDGET_EXCEEDED。
- §F-G 统一适配器接口（五方法）：Jest/Ruff/Pyright/CargoTest/Semgrep/Playwright/GH-Actions 同构接入。
- §H 失败分类学：叶子分类 + origin class（Code/Test/Environment/Infrastructure/Dependency/Flaky/Unknown）。
- §I 修复策略：预算制 + 决策表，防无限循环。
- §J Token 优化：Context Builder 构造最小诊断上下文，严格检索顺序。
- §K 安全模型：Agent 输出（代码/命令/测试）视为不可信输入。

## 与 SDK 的关系
- 已吸收：ref-19/ref-22（v2.9.0）· T-07..T-26 · ALIGNMENT.md#verification-kernel-→-SDK
- 已排除：§L 技术栈中的 Temporal/Redis——SDK 采用最小栈
- 未决：—

## 引用约定
注入时打 `<source doc="d-verification-kernel-architecture" section="§x.y">`；引用必须可回查到本节。
