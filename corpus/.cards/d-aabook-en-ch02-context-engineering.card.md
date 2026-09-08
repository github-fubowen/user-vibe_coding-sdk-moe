# chapter2 · 摘要卡
- id: d-aabook-en-ch02-context-engineering · type: book · bytes: 146,315 · sections: 41 · tokens: ~28,312
- source: bojieli/ai-agent-book@006d2368 · sha256: 8492b59ea07d01be · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Chapter 1 compared context to an Agent's "eyes": an Agent can make decisions only from the information it sees. The design and management of context is called **Context Engineering**. Context is all the information the AI actually "sees" whenever you interact with it. It includes not only the conversation history, but also developer-written rules of behavior…

## 高频术语（自动统计 Top-8 · 未校对）
`model`×228 · `agent`×227 · `context`×224 · `tool`×186 · `information`×119 · `cache`×108 · `content`×105 · `system`×97

## 一句话
第 2 章：上下文工程——上下文是 Agent 能力的天花板；KV cache 友好设计、系统提示、Skills 动态加载、Agent 状态条与压缩策略。

## 章节地图（TOC 压缩，标 ★核心节）
- §Context Engineering
- §Context: The Ceiling of Agent Capability
- §How Agents Call LLMs: The API-Level Context Structure
- §KV Cache-Friendly Context Design
- §Prompt Engineering: Optimizing the System Prompt
- §Dynamic Prompts and Agent Skills
- §Agent Status Bar: Managing Trajectories with Meta-Information
- §Context Compression Strategies
- §Chapter Summary
- §Thought Questions

## 关键条款（≤8 条，每条 ≤2 行）
- 上下文=天花板：Agent 只能基于所见决策；基准分高≠业务好。
- KV Cache 友好设计：稳定前缀降本（生产事故案例：消息列表顺序抖动致缓存全失效）。
- 系统提示 litmus test：写给"完全陌生的高能力新员工"的操作手册。
- 动态提示与 Agent Skills：不一次装全部知识，按需加载（SDK 渐进式披露理论出处）。
- Agent 状态条：用元信息管理长轨迹、防状态漂移。
- 上下文压缩的三种动因决定策略设计（§Context Compression Strategies）。

## 与 SDK 的关系
- 已吸收：未吸收——SDK 稳定前缀缓存/渐进式披露（moe 核心 MoE-4/5）的理论出处互证
- 已排除：—
- 未决：—

## 引用约定
注入时打 `<source doc="d-aabook-en-ch02-context-engineering" section="§x.y">`；引用必须可回查到本节。
