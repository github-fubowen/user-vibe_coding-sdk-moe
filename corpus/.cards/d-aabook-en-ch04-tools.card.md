# chapter4 · 摘要卡
- id: d-aabook-en-ch04-tools · type: book · bytes: 83,893 · sections: 20 · tokens: ~16,320
- source: bojieli/ai-agent-book@006d2368 · sha256: be1ce66c065e11d7 · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
In the sci-fi film *Her*, the AI assistant Samantha can proactively organize emails, identify emotionally complex messages and suggest refined replies, represent the protagonist in publishing matters, and seamlessly switch between different communication channels. Her intelligence is compelling because she possesses powerful **tools**—the “hands, feet, and s…

## 高频术语（自动统计 Top-8 · 未校对）
`tool`×207 · `tools`×154 · `agent`×134 · `model`×80 · `mcp`×72 · `only`×50 · `file`×44 · `skills`×42

## 一句话
第 4 章：工具——五类工具（感知/执行/协作/事件触发/用户通信）× 通用设计原则 × MCP/Skill 双生态 × 工具过多时的分层组织与主动发现。

## 章节地图（TOC 压缩，标 ★核心节）
- §Tools
- §Tool Classification
- §Universal Principles of Tool Design
- §Tool Ecosystem: MCP and Skill Hubs
- §What to Do When There Are Too Many Tools: Hierarchical Organization and Proactive Tool Discovery
- §Perception Tools
- §Execution Tools
- §Collaboration Tools
- §Chapter Summary
- §Thought Questions

## 关键条款（≤8 条，每条 ≤2 行）
- 五类工具按调用方向与作用目标分类（表 4-1）。
- 通用设计原则：拒绝"每个 API 包一个工具"的细粒度包装；能力形式倾向通用端。
- MCP 客户-服务器架构：工具定义与 Agent 框架解耦（生态双通道之一）。
- 工具过多三层解法：分层组织按需加载 → 主动发现 → 逐级更按需（§What to Do When There Are Too Many Tools）。
- 感知工具：返回信息远超可处理量，需裁剪与分页设计。
- 执行工具：可昂贵失败——安全机制分层设计。
- 协作工具：子 Agent 设计哲学——超出能力边界才委托。
- 标准化代价：MCP 解耦但也让复杂交互模式变难（思考题）。

## 与 SDK 的关系
- 已吸收：未吸收——SDK 静态工具路由/probe-tools.py 的领域理论出处互证
- 已排除：—
- 未决：—

## 引用约定
注入时打 `<source doc="d-aabook-en-ch04-tools" section="§x.y">`；引用必须可回查到本节。
