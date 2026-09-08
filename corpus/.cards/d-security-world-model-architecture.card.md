# security-world-model-architecture · 摘要卡
- id: d-security-world-model-architecture · type: architecture · bytes: 72,068 · sections: 55 · tokens: ~11,064
- source: architecture/security-world-model-architecture.md · sha256: 2daca6c13480441e · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Most "cybersecurity RAG" systems fail for the same reason: they treat security knowledge as unstructured prose to be chunked and embedded, which destroys the one thing that makes security knowledge useful — its *relational and causal structure*. A CVE means nothing without the CWE it instantiates, the product/version it affects, the technique it enables, the…

## 高频术语（自动统计 Top-8 · 未校对）
`graph`×64 · `knowledge`×56 · `path`×52 · `agent`×49 · `evidence`×48 · `confidence`×44 · `security`×44 · `attack`×43

## 一句话
Security World Model——把防御安全知识建成"结构优先"的图本体（攻防双向图 + 证据/置信/时间三模型），支撑自主防御 Agent 的精确查询与可审计推理。

## 章节地图（TOC 压缩，标 ★核心节）
- §The Security World Model
- §Architecture for a Cybersecurity Knowledge System Powering an Autonomous Defensive Security Agent
- §1. Executive Summary
- §2. Design Principles
- §3. System Architecture (Layered View)
- §4. Security Ontology
- §5. Entity Model — Concrete Node Examples
- §6. Relation Model
- §7. Attack Knowledge Model
- §8. Defensive Knowledge Model
- §9. Attack-Defense Graph
- §10. Attack Path Model
- §11. Evidence Model & Provenance
- §12. Knowledge Confidence Model
- §13. Temporal Knowledge Model
- §14. Knowledge Ingestion Pipeline
- §15. Knowledge Extraction Pipeline
- §16. Security Knowledge Compiler
- §17. Hybrid Retrieval Architecture
- §18. Security Knowledge Query Language (SKQL)
- §19. Agent Architecture
- §20. Red Team Architecture
- §21. Blue Team Architecture
- §22. Detection Knowledge Graph

## 关键条款（≤8 条，每条 ≤2 行）
- §2 结构优先于相似度：图为底座，向量/关键词只是检索加速器；证据强制（无 Source/Evidence/Confidence 不入图）。
- §4-6 六域本体 + 类型化有向证据边的关系模型。
- §9-10 攻防双向图 + 攻击路径模型：图遍历直接回答，不用 LLM 推理。
- §12-13 置信分解与多跳传播（连乘）+ 双时间线查询模式。
- §16-17 知识编译器：文本→图事实如编译般可复现可调试；安全查询多为精确匹配，纯向量被否决。
- §18 SKQL：小型 DSL 确定性编译到图/向量/SQL。
- §27-28 权限架构：LLM 只发结构化 Intent、永不持凭据；注入防御靠结构化信任层级执行。
- §22 检测知识图谱：Sigma/YARA/SPL 等规则作结构化子类型，覆盖率用图查询计算。

## 与 SDK 的关系
- 已吸收：未吸收——领域专用（防御安全）；结构优先/证据闸门/置信传播方法论与 ref-25 检索分层互证
- 已排除：—
- 未决：SDK 若推进安全审计线（ref-13 Strix / ref-14）时的检索分层参考

## 引用约定
注入时打 `<source doc="d-security-world-model-architecture" section="§x.y">`；引用必须可回查到本节。
