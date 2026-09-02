---
name: context-modeling
description: 维护项目领域模型：CONTEXT.md 词汇表 + docs/adr/ 决策记录。Use when terms drift, a new architecture decision lands, or a project needs a ubiquitous language.
agent_created: true
---

# Context Modeling — 领域模型维护

Actively build and sharpen the project's domain model. 这是"主动纪律"：术语一定型就写入，挑战术语准确性，用边界场景压力测试词汇表。

> 注意：仅仅是"读取 CONTEXT.md 取词汇"不是本技能——那是一次性习惯，任何技能都能做。本技能只在**改变模型**时触发。

## 文件结构

单上下文仓库（最常见）：

```
/
├── CONTEXT.md              ← 领域词汇表 + 核心概念
├── docs/
│   └── adr/                ← 架构决策记录
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

多上下文仓库：根目录放 `CONTEXT-MAP.md`，指向每个上下文所在位置。

## 职责

1. **维护 CONTEXT.md 词汇表**
   - 术语一旦在讨论/设计中定型，立即写入
   - 对照词汇表**挑战术语**：这个词准确吗？有无歧义？有没有更好的词？
   - 用边界场景压力测试：造边缘用例，发现词汇表盲区即补充

2. **记录架构决策到 docs/adr/**
   - 每个重要决策一条 ADR：`NNNN-<title>.md`，含背景、决策、后果
   - 写下的那一刻就落盘，不拖延

3. **让词汇成为共享语言**
   - 测试名、接口名、变量名与 CONTEXT.md 词汇一致
   - 新代码/重构遵循词汇表，减少"同一个东西多个叫法"的漂移

## 触发时机

- 术语在会话中反复出现且叫法不一致
- 新架构决策产生（技术选型、模块边界、数据模型变化）
- 用户要求"建立项目通用语言" / "pin down domain terminology"
