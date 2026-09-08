# chapter3 · 摘要卡
- id: d-aabook-en-ch03-memory-knowledge · type: book · bytes: 118,993 · sections: 29 · tokens: ~22,971
- source: bojieli/ai-agent-book@006d2368 · sha256: 7f442e8f9536188f · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
The previous chapter addressed context management within a single interaction. This chapter tackles a more difficult problem: how to enable an Agent to remember users and retain knowledge even after a conversation ends.

## 高频术语（自动统计 Top-8 · 未校对）
`memory`×160 · `knowledge`×152 · `retrieval`×152 · `user`×122 · `information`×83 · `context`×82 · `agent`×76 · `text`×71

## 一句话
第 3 章：用户记忆与知识库——双尺度持久记忆（个人 User Memory / 共享 RAG 知识库）与六个主题的知识组织检索进阶。

## 章节地图（TOC 压缩，标 ★核心节）
- §User Memory and Knowledge Base
- §User Memory System
- §RAG Basics: Building an Agent's Knowledge Acquisition Pipeline
- §Beyond Flat Text: Knowledge Organization and Retrieval
- §Chapter Summary
- §Thought Questions

## 关键条款（≤8 条，每条 ≤2 行）
- 双尺度：User Memory（个体个性化）vs 共享知识库（RAG）。
- RAG 基础：retriever + generator 两段式与稠密/稀疏/混合检索。
- 六主题：结构化索引等六个角度组织超越平铺文本的知识检索。
- Contextual Retrieval 的边界：chunk 加原文上下文，但原文本身烂则失效（思考题）。

## 与 SDK 的关系
- 已吸收：未吸收——与 KnowledgeOS 记忆分层（三层 memory）及 RAG 设计互证
- 已排除：—
- 未决：KnowledgeOS 检索升级时回查"六主题"（图/结构化/混合检索）

## 引用约定
注入时打 `<source doc="d-aabook-en-ch03-memory-knowledge" section="§x.y">`；引用必须可回查到本节。
