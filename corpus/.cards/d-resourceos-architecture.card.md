# ResourceOS-Architecture · 摘要卡
- id: d-resourceos-architecture · type: architecture · bytes: 125,131 · sections: 88 · tokens: ~19,327
- source: architecture/ResourceOS-Architecture.md · sha256: a519a4f12dcbf5d9 · status: absorbed
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
ResourceOS is the infrastructure layer that lets a coding agent operate over an unbounded population of skills, tools, MCP servers, agents, workflows, projects, references, memories, templates, scripts, artifacts, policies, prompts, and plugins — collectively **Resources** — without ever placing that population in the LLM's context window.

## 高频术语（自动统计 Top-8 · 未校对）
`resource`×193 · `resources`×106 · `capability`×92 · `text`×86 · `task`×82 · `tool`×79 · `project`×73 · `security`×70

## 一句话
ResourceOS——让编码 Agent 在 10³-10⁵ 规模技能/工具/MCP 资源上高效发现与安全激活的统一资源操作系统；核心赌注：能力发现是搜索引擎问题，不是 prompt 工程问题。

## 章节地图（TOC 压缩，标 ★核心节）
- §ResourceOS: A Unified Resource Operating System for Large-Scale Autonomous Coding Agents
- §1. Executive Summary
- §2. Problem Definition
- §3. Design Principles
- §4. System Architecture (Overview)
- §5. Resource Model — The Unified Abstraction
- §6. CapabilityOS
- §7. Resource Registry
- §8. Multi-Level Resource Loading
- §9. Hybrid Resource Retrieval
- §10. Resource Router
- §11. Hierarchical Tool Discovery
- §12. Skill Architecture
- §13. ProjectOS / Workspace Architecture
- §14. ContextOS
- §15. Memory Architecture
- §16. Reference / Knowledge Architecture
- §17. Resource Dependency Graph
- §18. Resource Reputation System
- §19. Resource Lifecycle
- §20. SecurityOS
- §21. Resource Conflict Resolution
- §22. Resource Composition
- §23. Failure Recovery

## 关键条款（≤8 条，每条 ≤2 行）
- §3 统一模型+特化运行时：一种 Resource 抽象、多类型 handler；身份便宜、内容昂贵。
- §6 CapabilityOS：身份→能力两级间接，资源涨 100× 而推理面不变。
- §7 Registry 只存元数据与引用，内容留文件系统（唯一例外：小而结构化的 Prompt/Policy 可内联）。
- §8 多级加载 L0-L3：L1 以上永不加载非候选资源——token 效率第一杠杆。
- §9 混合检索流水线：逐级廉价淘汰候选 + 负信号抑制热门但错误资源。
- §10 Router 动词分离 + output_ref 工件化：大结果不进上下文。
- §17-18 依赖图（类型化边/能力替换降级）+ 声誉系统（贝叶斯平滑成功率）。
- §27-29 低配实现：SQLite+FTS5+FAISS+文件系统；(type,lifecycle_state) 为最热索引。

## 与 SDK 的关系
- 已吸收：ref-25（v2.10.7-v2.10.10）· R-1..R-10 · ALIGNMENT.md#ResourceOS-Architecture.md-吸收映射（v2.10.7-补记，R-1）
- 已排除：§26 中型部署（Postgres/pgvector 多租户）与 §25 在线声誉学习的在线半——SDK 单机+静态路由阶段不适用
- 未决：SDK 语料池 L2（SQLite FTS5）落地时回查 §27-29 存储与索引设计

## 引用约定
注入时打 `<source doc="d-resourceos-architecture" section="§x.y">`；引用必须可回查到本节。
