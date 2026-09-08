# agent-rag-architecture · 摘要卡
- id: d-agent-rag-architecture · type: architecture · bytes: 71,528 · sections: 70 · tokens: ~10,779
- source: architecture/agent-rag-architecture.md · sha256: cbb668b4681b7d14 · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Conventional RAG treats retrieval as a stateless function: `embed(query) → top_k(vector_db) → stuff_context(llm)`. This fails inside an autonomous agent because the agent's information need is dynamic, multi-hop, contradictory-prone, cost-constrained, and evolves as the agent reasons. This document specifies **Agent RAG** — a retrieval subsystem that is itse…

## 高频术语（自动统计 Top-8 · 未校对）
`retrieval`×97 · `query`×86 · `evidence`×58 · `task`×53 · `graph`×51 · `budget`×44 · `llm`×43 · `source`×38

## 一句话
Agentic RAG——把检索从无状态函数升级为 AgentOS 内的一等服务：任务级检索规划、多路融合、五级证据闸门与"任务结果即标签"的自改进闭环。

## 章节地图（TOC 压缩，标 ★核心节）
- §Agentic RAG Subsystem for a Self-Improving AgentOS
- §1. Executive Summary
- §2. Design Principles
- §3. Complete Architecture
- §4. Component Architecture
- §5. Retrieval Source Architecture
- §6. Agentic Retrieval
- §7. Query Planning
- §8. Retrieval Router
- §9. Retrieval Fusion
- §10. Reranking
- §11. Context Engineering
- §12. Knowledge Representation
- §13. Graph + Vector + Lexical RAG
- §14. Trust, Verification & Evidence
- §15. Self-Correcting Retrieval
- §16. Self-Improving RAG
- §17. Anti-Patterns
- §18. Performance / Cost Optimization
- §19. Security
- §20. Observability
- §21. Evaluation
- §22. Recommended Production Tech Stack
- §23. API Specification

## 关键条款（≤8 条，每条 ≤2 行）
- §1 反模式：embed→top_k→stuff 在自主 Agent 内必败；检索须成为一等子系统。
- §5 RetrieverRegistry：检索器自注册能力/成本画像，供路由前置决策。
- §6-8 Agentic 检索（先分类信息需求）+ 查询规划 DAG + RetrievalPlan（含 budget_share）。
- §9-10 多路融合（默认先验+学习调权）与多级重排：候选量每级降 10-50×、单条成本升 10-100×，总成本近似持平。
- §12 知识表示：SQL 行为权威身份/权限/生命周期，其余索引皆派生可重建。
- §14 证据五闸门：Retrieved→Relevant→Trusted→Verified→Consistent 全过才入上下文。
- §15-16 自纠正+自改进：任务结果即标签，免人工标注；costBudget 前置拒绝。
- §19 权限 AND 链先于融合过滤候选。

## 与 SDK 的关系
- 已吸收：未吸收——与 KnowledgeOS RAG 线直接相关（检索规划/五闸门/派生索引）；SDK 侧仅登记
- 已排除：—
- 未决：KnowledgeOS 检索层升级（混合检索/重排）时回查 §6-§16

## 引用约定
注入时打 `<source doc="d-agent-rag-architecture" section="§x.y">`；引用必须可回查到本节。
