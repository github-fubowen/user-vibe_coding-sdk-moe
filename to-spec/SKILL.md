---
name: to-spec
description: 把当前对话综合成 spec 文档。Use when starting spec-driven development, or
  "把这个讨论写成 spec". 不访谈用户，只综合已讨论内容。
agent_created: true
---

# To Spec — 对话转规格

把当前会话上下文与代码库理解综合成一份 spec（即 PRD）。**不访谈用户**——只综合已经讨论过的内容。

## 流程

1. **探索代码库**（如果还没做过）：理解当前状态；spec 全程使用项目领域词汇表（见 CONTEXT.md），尊重相关 ADR。
2. **预声明测试接缝（seams）**：先草拟测试将在哪个公共接口上测。优先已有 seam，用尽可能高的 seam；理想数量是 1 个。与用户确认这些 seams 是否符合预期。
3. **写 spec**，按下方模板，产出到 `docs/specs/YYYY-MM-DD-<feature>.md`。

## Spec 模板

```markdown
## Problem Statement
用户面临的问题（从用户视角描述）。

## Solution
问题的解决方案（从用户视角描述）。

## User Stories
1. As an <actor>, I want a <feature>, so that <benefit>
（极长的编号列表，覆盖功能的所有方面）

## Implementation Decisions
- 将构建/修改的模块
- 模块的接口
- 开发者的技术澄清
- 架构决策

## Test Seams
- 测试将在哪些公共接口上进行
- 明确不测哪些位置
```

## 原则

- 不访谈用户（与 grilling 互补：grilling 用于尚未讨论清楚时）
- 用项目领域词汇，尊重 ADR
- 测试接缝预声明后必须先与用户确认
