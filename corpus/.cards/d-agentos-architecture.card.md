# agentos-architecture · 摘要卡
- id: d-agentos-architecture · type: architecture · bytes: 65,811 · sections: 46 · tokens: ~9,651
- source: architecture/agentos-architecture.md · sha256: 68bb309b834f4c1c · status: absorbed
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
AgentOS is not a prompt-orchestration framework. It is an operating system whose "processes" are LLM-driven agents, whose "memory hierarchy" is a managed context engine, whose "syscalls" are tools, and whose "compiler/debugger" is an independent verification engine that never trusts a model's self-report of success.

## 高频术语（自动统计 Top-8 · 未校对）
`agent`×86 · `context`×76 · `tool`×74 · `kernel`×67 · `model`×56 · `process`×51 · `state`×47 · `task`×47

## 一句话
AgentOS——把编码 Agent 做成操作系统：Model Router 分级升级、最小充分上下文、任务状态机 DAG、十层验证引擎与分层记忆的完整控制面。

## 章节地图（TOC 压缩，标 ★核心节）
- §AgentOS: A Coding Agent Operating System
- §A. Executive Summary
- §B. Mental Model
- §C. Full Architecture Diagram
- §D. Layered Architecture
- §E. Kernel Architecture
- §F. Agent Process Model
- §G. Context / Memory Architecture
- §H. Tool Architecture
- §I. Runtime / Sandbox Architecture
- §J. Scheduler Architecture
- §K. Multi-Agent Architecture
- §L. IPC / Agent Communication
- §M. Persistence Architecture
- §N. Security Model
- §O. Observability
- §P. Failure and Recovery Model
- §Q. Technology Stack
- §R. Repository Structure
- §S. Core Data Structures
- §T. Execution Sequence
- §U. Security Sequence
- §V. Multi-Agent Sequence
- §W. Performance Model

## 关键条款（≤8 条，每条 ≤2 行）
- §6.1-6.3 Model Router：规则硬过滤（安全/资格）→上下文 bandit 软选（质量/成本）→确定性升级；显式拒绝 RL 全策略路由。
- §6.5-6.6 路由决策记录可回放；失败后候选集上移一类即升级。
- §7 最小充分上下文：按调用现配，不长跑 transcript；严格选择算法。
- §8 Repository Intelligence：SEARCH→LOCATE→READ 纪律，禁止"全读喂 LLM"。
- §9 Tool/MCP Router：模型见能力不见工具，选中后再由 Capability Router 解析。
- §10-13 Orchestrator 独占状态写入；任务状态机 DAG 带回边；验证十层最廉价优先短路。
- §14 分层记忆：拒绝"全塞一个向量库"，失败复用先结构化匹配。
- §15-17 单 Agent 默认（子 Agent 须证明总成本下降）；预算超限转 ESCALATED 非静默降级；风险分层沙箱。

## 与 SDK 的关系
- 已吸收：ref-20/ref-22（v2.10.5）· F-54 · ALIGNMENT.md#agentos-architecture.md-吸收映射（v2.10.5-补记，F-54）
- 已排除：§18 OTel 全家桶与 §20 多租户存储——单机不适用
- 未决：—

## 引用约定
注入时打 `<source doc="d-agentos-architecture" section="§x.y">`；引用必须可回查到本节。
