# GPT-当前主流agent技术栈 · 摘要卡
- id: d-gpt-agent · type: survey · bytes: 41,161 · sections: 39 · tokens: ~4,696
- source: survey/GPT-当前主流agent技术栈.md · sha256: d8efade4ab73bd2b · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
OpenHands 当前对这一层次划分就是类似这个思路。

## 高频术语（自动统计 Top-8 · 未校对）
`agent`×126 · `text`×102 · `github`×65 · `harness`×38 · `gemini`×38 · `main`×35 · `source`×33 · `chatgpt`×32

## 一句话
2025-26 主流编码 Agent Harness 横评（Codex/Claude Code/Gemini CLI/OpenHands/Cline/Roo/Goose/Aider/SWE-agent/Cursor）：架构分型、上下文与工具策略对比、"MCP 即工具总线"趋势。

## 章节地图（TOC 压缩，标 ★核心节）
- §1. 先定义：Coding Agent Harness 到底是什么
- §2. 当前主流 Coding Agent Harness 第一梯队
- §3. Codex：目前非常值得研究的 Harness
- §4. Claude Code：非常强的“工具 + Hooks + Skills + Subagents”体系
- §5. Gemini CLI：非常典型的现代开源 Harness
- §6. Gemini CLI 的 Context Engineering 很值得研究
- §7. Gemini CLI 的 Sandbox 也很典型
- §8. OpenHands：最值得研究的开源 Agent Harness 之一
- §OpenHands Runtime
- §9. Cline：非常典型的 IDE Agent Harness
- §10. Roo Code：特别值得研究它的 Mode / Tool Permission
- §11. Goose：目前非常典型的“通用 Agent Runtime”
- §12. Goose 的 Recipe 很值得借鉴
- §13. Aider：虽然老一些，但很多底层设计非常优秀
- §Aider 的 Edit Harness
- §14. SWE-agent：从“Agent Computer Interface”角度非常重要
- §15. Cursor：目前商业 Coding Harness 的另一种路线
- §16. 一个非常重要的技术趋势：MCP 正在变成“Tool Bus”
- §17. MCP 还不是完整的 Agent Protocol
- §18. 当前主流 Harness 技术栈可以总结成这一张表
- §19. 目前最重要的架构趋势，其实不是“Multi-Agent”
- §20. 真正现代的 Coding Agent Harness
- §21. 如果你准备自己做 Coding Agent，我最推荐的技术组合
- §22. 如果从“工程成熟度”评价，我会这样排

## 关键条款（≤8 条，每条 ≤2 行）
- Harness 分型：CLI 型 / IDE 型 / 云型三类架构取舍。
- 上下文管理：各 harness 的压缩/状态维护/记忆策略差异。
- 工具生态：MCP 作为工具总线成为跨 harness 事实趋势。
- 权限模型：自动批准层级与沙箱策略对比。
- 评测口径：SWE-bench 类基准与真实任务之间的差距。

## 与 SDK 的关系
- 已吸收：未吸收——竞品/生态横评，用于 cross-check SDK harness 设计决策
- 已排除：—
- 未决：MCP 工具总线形态与 SDK probe-tools/toolstack 路线的适配点

## 引用约定
注入时打 `<source doc="d-gpt-agent" section="§x.y">`；引用必须可回查到本节。
