# ref-16 — Context7（upstash/context7）

> Load when: 需要最新库文档（避免训练数据过时）、管理 AI 编码技能（ctx7 skills）、配置 Context7 MCP；
> §6 SDD/Engineering 链路的 docs 检索环节；"context7"、"ctx7" 触发词。
> Added 2026-08-18（v1.9.5）。指针引用：CLI/MCP 按需 npx 运行，不 vendored。

## 1. 仓库事实（toolstack.json pin，2026-08-18 核对）

| 项 | 值 |
|----|----|
| repo | `upstash/context7`（**默认分支 = master**，非 main） |
| 描述 | Context7 Platform — Up-to-date code documentation for LLMs and AI code editors |
| 许可 | MIT |
| stars | 60,909 |
| pin | head `f3a818d`（2026-08-17T12:16:22Z）· release `@upstash/context7-mcp@4.0.2`（2026-08-11） |
| 上游漂移 | 由 ref-15 流水线自动核对（check: both） |

## 2. 是什么

Context7 提供**实时库文档**查询服务：把"某库某 API 怎么用"解析为当前版本文档片段，供 LLM / AI 编码
编辑器消费（消除训练数据截止导致的幻觉式 API 用法）。三个入口：

| 入口 | 命令/形态 | 用途 |
|------|-----------|------|
| CLI | `npx ctx7@latest docs <libraryId> <query>` | 终端取文档（无需安装，按需 npx） |
| 技能管理 | `npx ctx7@latest skills install /owner/repo` | 从 GitHub 仓库安装 AI 编码技能（registry 模式） |
| MCP | `@upstash/context7-mcp`（v4.0.2） | resolve-library-id + query-docs 双工具接入编辑器/Agent |

## 3. SDK 接入点（§6）

- **SDD**：`specify` CLI (ref-08) → find-docs / **context7-cli (ref-16)** → codebase-memory-mcp ——
  spec 编写阶段用 Context7 拉取目标库当前文档，避免按过时 API 写 spec。
- **Engineering**：codebase-memory-mcp → code-review-graph → graphify → find-docs · cli-hub ——
  find-docs 环节可换 context7-cli 获取最新 API 签名。
- 本机已有独立技能：`~/.workbuddy/skills/context7-cli`（ctx7 CLI 操作手册）与
  `~/.workbuddy/skills/context7-mcp`（MCP 工具调用流程）—— 使用细节直接读这两个技能，本 ref 只做指针。

## 4. 安全与隐私注意

- **不 vendored**：无本地代码落地，无依赖注入面；CLI/MCP 均按需 npx/远程服务。
- **隐私**：文档查询会把 query 文本发送至 context7.com —— 涉密代码/内部 API 名不要放进查询。
- **版本固定**：MCP 用 `@upstash/context7-mcp@4.0.2`（pinned，避免上游每周迭代漂移）；CLI 建议
  `ctx7@0.5.8+`。流水线定期核对，漂移见 toolstack.json `16-context7`。

## 5. 更新配方

- 例行巡检：`python scripts/toolstack-pipeline.py --update --commit`（ref-15）自动刷新 pin。
- 手动核对：`gh api repos/upstash/context7` + `gh api repos/upstash/context7/releases/latest`。
- 本地 skills（context7-cli / context7-mcp）为独立安装，升级按各自 SKILL.md 的 npm/CLI 指令，与本 ref 解耦。
