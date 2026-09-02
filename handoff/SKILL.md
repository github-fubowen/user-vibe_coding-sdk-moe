---
name: handoff
description: 把当前会话压缩成交接文档，供下一个 agent 继续。Use for long multi-session tasks or
  "交接给下一个 agent". 输出到 OS 临时目录。
agent_created: true
---

# Handoff — 会话交接

把当前会话压缩成一份交接文档，让全新 agent 能接手继续工作。保存到**操作系统临时目录**（不污染工作区）。

## 内容结构

```markdown
# Handoff — <任务名>

## 目标
<本次任务的最终目标>

## 当前状态
- 已完成：<按工件/文件列出>
- 进行中：<当前进行到哪一步>
- 未开始：<剩余工作>

## 关键上下文
<决策、约束、踩过的坑——只写对话中才有、别处查不到的>

## Suggested Skills
- <建议下一 agent 调用的技能，如 grilling / to-spec / test-driven-development …>
```

## 规则

1. **不重复已有工件**：specs/plans/ADRs/issues/commits/diffs 里已有的内容，用路径或 URL **引用**，不复制正文。
2. **脱敏**：API key、密码、PII 一律移除。
3. **suggested skills 必须有**：显式列出下一 agent 该调用的技能。
4. **接收参数**：若用户传了参数，视为"下一会话要聚焦什么"，据此裁剪文档。

## 输出位置

- macOS: `$TMPDIR` / Linux: `/tmp` / Windows: `%TEMP%`
- 文件名：`handoff-<timestamp>.md`
