# self_evolving_agentos_architecture · 摘要卡
- id: d-self-evolving-agentos-architecture · type: architecture · bytes: 63,020 · sections: 55 · tokens: ~10,046
- source: architecture/self_evolving_agentos_architecture.md · sha256: b5ba142c8edbdc8a · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Most "self-improving agent" projects are really just an LLM in a `while True` loop that occasionally rewrites its own prompt and calls that "learning." This produces systems that are unstable, unfalsifiable, and undebuggable — the agent's word is the only evidence that anything got better.

## 高频术语（自动统计 Top-8 · 未校对）
`policy`×62 · `agent`×59 · `evolution`×55 · `candidate`×54 · `task`×52 · `skill`×43 · `evaluation`×42 · `postgres`×42

## 一句话
Self-Evolving AgentOS——把自改进做成受治理的子系统而非 while True 改 prompt：16 个显式进化目标、封闭算子集、假设-信用分配-谱系与安全自改分级。

## 章节地图（TOC 压缩，标 ★核心节）
- §Self-Evolving AgentOS — Reference Architecture
- §0. Executive Summary
- §1. Core Design Philosophy
- §2. Evolutionary Targets
- §3. AgentOS as an Operating System
- §4. RLM / Programmatic Control Plane
- §5. Recursive Agent Fabric
- §6. Memory OS
- §7. Skill OS
- §8. Experience Ledger
- §9. Evaluation OS
- §10. Evolution Engine — Lifecycle State Machine
- §11. Evolution Operators (explicit, closed set — no free-form rewriting)
- §12. Hypothesis System
- §13. Evolution Credit Assignment
- §14. Evolution Memory & Lineage
- §15. Safe Self-Modification
- §16. Evolution Autonomy Levels
- §17. Long-Running Agent Runtime
- §18. Scheduler & Resource OS
- §19. Model Router
- §20. Software Factory Integration
- §21. Failure-Driven Evolution
- §22. Knowledge & Retrieval Evolution

## 关键条款（≤8 条，每条 ≤2 行）
- §0-1 立场："反思并重写 prompt"只是假设生成器；自改进=治理子系统，内核 Capability API 版本化。
- §2 16 个显式进化目标共享统一生命周期：Version→Sandbox→Evaluate→Policy Gate→Canary→Promote/Rollback。
- §4 RLM 控制面：模型只拿一个持久沙箱 REPL 内核，而非 30 个平铺工具。
- §10-11 进化引擎：Learning 与执行结构分离（离线零权限）；算子封闭集，禁止自由改写。
- §12-14 假设系统 + 信用分配（N+2 重放，仅捆绑晋升）+ 谱系图（可答"为何存在"）。
- §15-16 安全自改：风险分级是策略配置；不变量由内核强制，非约定。
- §26 事件驱动：一切变更因事件而生，决策树可审计。

## 与 SDK 的关系
- 已吸收：未吸收——治理型自改进参考，与 SDK toolstack-pipeline 六阶段版本漂移维护同构
- 已排除：分布式事件总线（NATS/Kafka）——单机不适用
- 未决：SDK 自动化批次升级（P0/P1/P2）设计时回查 §10-12 生命周期

## 引用约定
注入时打 `<source doc="d-self-evolving-agentos-architecture" section="§x.y">`；引用必须可回查到本节。
