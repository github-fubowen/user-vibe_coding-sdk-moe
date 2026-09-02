---
name: to-tickets
description: 把 spec/计划拆成垂直切片 ticket，每张声明阻塞边。Use when a spec is ready and the
  user says "拆成任务". 本地文件即 tracker。
agent_created: true
---

# To Tickets — 拆 ticket

把 spec/计划/当前对话拆成一组 **tracer-bullet 垂直切片 ticket**，每张声明阻塞它的前置 ticket。本地 markdown 文件即 tracker，不依赖 GitHub/Linear。

## 流程

1. **收集上下文**：从对话/传入的 spec 路径出发。若传入 spec，读取全文。
2. **探索代码库**（可选）：理解当前状态；ticket 标题与描述用项目领域词汇（CONTEXT.md），尊重 ADR。
3. **寻找预重构机会**：`Make the change easy, then make the easy change.` 先让变更变容易，再去做容易的变更。
4. **起草垂直切片**：把工作拆成 tracer bullet ticket——
   - 每张 ticket 是一个**垂直切片**：端到端可独立实现+测试，而非水平分层
   - 每张 ticket 声明**阻塞边**（前置 ticket 文件名）
   - 每张 ticket 可由一个 subagent 在 2-5 分钟内完成

## 产出目录

```
docs/tickets/YYYY-MM-DD-<feature>/
├── 01-<slug>.md      ← 无前置依赖
├── 02-<slug>.md      ← 阻塞于 01-<slug>
└── 03-<slug>.md      ← 阻塞于 02-<slug>
```

## Ticket 模板

```markdown
## Title
<动词开头的简短标题>

## Blocked By
- <前置 ticket 文件名>（无则写"无"）

## 目标
<用户可观察的成果>

## 实现要点
<技术方向，用领域词汇>

## 验证
<如何验证完成——测试/手动检查>
```

## 原则

- 垂直切片：一个用户可见行为一个 ticket，不做"先写全部测试再写全部实现"的水平切片
- 用领域词汇，尊重 ADR
- 每张 ticket 可独立实现 + 独立测试
