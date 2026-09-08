# chapter10 · 摘要卡
- id: d-aabook-en-ch10-multi-agent · type: book · bytes: 122,060 · sections: 34 · tokens: ~23,345
- source: bojieli/ai-agent-book@006d2368 · sha256: 3a16eadf315e80d7 · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
The first nine chapters focused on a single Agent: first building its context, knowledge, tools, and interaction capabilities, then using evaluation, post-training, and continual evolution to improve it over time. This chapter advances the question from “How do we build and improve one Agent?” to “How do we organize multiple Agents?”—so that division of labo…

## 高频术语（自动统计 Top-8 · 未校对）
`agent`×402 · `agents`×207 · `system`×95 · `context`×77 · `manager`×77 · `multi`×67 · `shared`×66 · `only`×62

## 一句话
第 10 章：多 Agent 协作——共享/隔离上下文 × 对等/管理者/去中心拓扑的分类框架、"多 Agent 何时真优于单 Agent"判据与特有失败模式。

## 章节地图（TOC 压缩，标 ★核心节）
- §Multi-Agent Collaboration
- §A Classification Framework for Multi-Agent Collaboration
- §When Is Multi-Agent Truly Better Than a Single Agent?
- §Multi-Agent Collaboration with Shared Context
- §Multi-Agent Collaboration Without Shared Context
- §Failure Modes of Multi-Agent Collaboration
- §Agent Society
- §Chapter Summary
- §Thought Questions

## 关键条款（≤8 条，每条 ≤2 行）
- 分类框架：共享/隔离上下文 + 对等/管理者/去中心拓扑两维定架构。
- 何时真需要多 Agent：协作模式是否引入单 Agent 不可得的新信息（表 10-1）。
- 共享上下文：阶段 Agent 继承完整上下文——细节保留但有框架传染（framing inheritance）风险。
- 隔离上下文：通信机制类比进程间通信（IPC）。
- 失败模式：《Why Do Multi-Agent LLM Systems Fail?》——简单修复收益有限（ChatDev 仅 +15.6%）。
- 默认单 Agent：多 Agent 是例外，须证明总成本下降（与 AgentOS §15 呼应）。

## 与 SDK 的关系
- 已吸收：未吸收——SDK 单 Agent 纪律的理论支撑（SendMessage/team 仅按需启用）
- 已排除：—
- 未决：—

## 引用约定
注入时打 `<source doc="d-aabook-en-ch10-multi-agent" section="§x.y">`；引用必须可回查到本节。
