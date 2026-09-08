# chapter6 · 摘要卡
- id: d-aabook-en-ch06-interaction · type: book · bytes: 110,782 · sections: 40 · tokens: ~21,936
- source: bojieli/ai-agent-book@006d2368 · sha256: 79d59b6c29807b73 · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Chapter 1 made a claim: when the underlying model is fixed, the most effective system-engineering lever for improving an Agent's task performance is usually to redefine or expand its **observation space** and **action space**. Chapters 2 through 5 have been cashing that claim out—context engineering decides what goes into the observation, memory and knowledg…

## 高频术语（自动统计 Top-8 · 未校对）
`agent`×170 · `model`×161 · `user`×120 · `event`×95 · `task`×82 · `action`×78 · `tool`×78 · `only`×60

## 一句话
第 6 章：交互——沿"模态 × 时机"两轴扩展观测/行动空间：异步事件驱动、语音、Computer Use（GUI 自动化）与机器人操作。

## 章节地图（TOC 压缩，标 ★核心节）
- §Interaction: Expanding the Observation and Action Spaces
- §Two Axes: Modality and Timing
- §Async and Event-Driven: When the World Comes Looking for You
- §Voice: The Most Natural Human-Machine Interface
- §Computer Use: GUI Automation Agents
- §Robot Manipulation: Tidying a Desk with XLeRobot
- §Chapter Summary
- §Thought Questions

## 关键条款（≤8 条，每条 ≤2 行）
- 两轴框架：模态与时机是扩展观测/行动空间的两个方向。
- 异步事件驱动：走出轮式对话的第一步——"世界来找你"。
- 队列焦点问题：模型只关注最后事件 → Agent 状态条标记缓解。
- 语音：说比打字快约 4 倍；双向语音（对用户/替用户对外）模型设计。
- Computer Use：GUI 自动化的观测/动作空间设计（XLeRobot 实验链）。
- 四节共享一个控制骨架（章末总结）。

## 与 SDK 的关系
- 已吸收：未吸收——SDK 当前纯文本 CLI 场景，仅方法论登记
- 已排除：—
- 未决：SDK 定时自动化/事件驱动设计时回查 §Async and Event-Driven

## 引用约定
注入时打 `<source doc="d-aabook-en-ch06-interaction" section="§x.y">`；引用必须可回查到本节。
