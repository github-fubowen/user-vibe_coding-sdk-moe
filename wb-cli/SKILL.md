---
name: wb-cli
description: WorkBuddy 伪 CLI 解释器。当用户输入以 / 开头的命令（/mode /status /vibe /eng /sdd /debug /review /quick /test /commit /graph /wd /agent /cluster /squad /help 等）时激活，负责命令解析、路由到对应 skill、读写会话状态文件 .workbuddy/cli/state.json。也适用于用户提到"伪 CLI""wb> 提示符""命令行体验""CLI 模式""终端式操作""看门狗""agent 集群"等场景。
---

# WorkBuddy 伪 CLI 解释器

把聊天输入翻译成可复现的命令流。三条职责：**命令解析与路由、会话状态读写、输出契约**。命令是 `/user-vibe_coding-sdk` 六路径的别名层，不复制工作流正文。

## 触发规则

1. 首 token 以 `/` 开头 → 进入命令模式，走下方路由总表
2. 无 `/` 前缀 → 自然语言，按 `state.json` 的 `mode` 默认工作流处理（mode 未设置则默认 `vibe`）
3. 未知命令 → 输出 `E1` + 建议最近命令 + 降级为自然语言执行
4. 参数缺失 → 输出 `E2` + 该命令 usage

## 命令路由总表（核心 16 命令）

| 命令 | 路由目标（skill） | 行为 |
|------|------------------|------|
| `/help [cmd]` | 本 skill `commands.md` | 输出命令用法 |
| `/status` | 读 `state.json` | 显示 cwd/mode/branch/ctx |
| `/mode <m>` | 写 `state.json` | 切换模式，重定向后续路由 |
| `/vibe <任务>` | user-vibe_coding-sdk Path B | 原型：直接实现→验证→迭代 |
| `/eng <任务>` | user-vibe_coding-sdk Path A | 正式：brainstorm→grill→plan→TDD→subagent |
| `/sdd <子命令>` | sdd-workflow（to-spec/to-tickets/implement/triage） | 规范驱动闭环 |
| `/debug <症状>` | systematic-debugging | Phase 0 反馈回路→根因→验证 |
| `/review <目标>` | requesting/receiving-code-review | OCR 先行→双轴并行审查 |
| `/quick <修改>` | user-vibe_coding-sdk Path F | 轻量 TDD→验证 |
| `/test [filter]` | TDD / 项目工具链 | 运行测试，报告结果 |
| `/commit` | git | 本地提交（**不 push**） |
| `/graph <query>` | graphify / code-review-graph / codebase-memory-mcp | 图谱查询 |
| `/wd <子命令>` | `wd.py`（看门狗 CLI） | 任务监控：status/watch/kill/logs/register |
| `/agent <op>` | 集群编排层 | 下位 agent 管理：ls/use/info |
| `/cluster <子命令>` | 集群编排层 | 集群作业：run/status/collect/cancel |
| `/squad <角色>` | 集群编排层 | 角色分工集群：--code/--review/--docs |

> 完整 44 条命令见 `commands.md`。子命令分发表见该文件 §SDD / §Review / §Git / §看门狗 / §集群。

## 会话状态读写规则

**位置**：`<cwd>/.workbuddy/cli/state.json`（唯一事实源）；`<cwd>/.workbuddy/memory/YYYY-MM-DD.md` 追加人读命令日志。

**schema**：

```json
{
  "cwd": "D:\\path\\to\\project",
  "mode": "sdd",
  "branch": "feature/x",
  "ctx": ["AGENTS.md", "CONTEXT.md"],
  "last_cmd": "/sdd spec 知识库导入",
  "updated_at": "2026-08-09T20:00:00+08:00"
}
```

**读写时机**：

- 命令执行前：读 `state.json` → 注入 mode/cwd/branch 上下文
- 命令执行后：写 `state.json` + 追加 memory 日志
- `branch` 每次执行前由 `git branch --show-current` 实测刷新，不信缓存
- 文件缺失 → 用上述 schema 初始化默认状态（mode 空 = vibe）
- 文件损坏 → `E3` + 重建默认状态，不阻塞任务

## 输出契约（要点）

每次命令响应遵循统一模板，详见 `references/output-template.md`：

1. **命令回显**：`wb /<cmd> <args>`
2. **状态行**：`mode · cwd · branch · 耗时`
3. **结论先行**：第一行即结果
4. **表格化**：清单/状态/对比一律 Markdown 表格
5. **下一步建议**：附可重放的下一命令

状态符号：`✓` 成功 / `⚠` 警告（降级）/ `✗` 失败 / `…` 进行中 / `↳` 子项。
错误码：`E0` 成功 / `E1` 未知命令 / `E2` 参数非法 / `E3` 状态损坏 / `E4` 工具不可用（降级替代）/ `E9` 用户中断。

## 安全边界

- `/push` 必须用户显式确认；`/commit` 默认执行但不推送
- 所有 git 写操作前先 `/status` 确认 branch，避免串分支
- 外部工具探测：CLI 用 `command -v <bin>`；不可用按 SDK §Tool Routing 降级链替代并标注
- `/wd kill` 带命令行特征校验（防 pid 复用误杀），非必要不 kill
- `/cluster run` 默认并发 ≤3、超时 600s、结果独立落盘 `.workbuddy/cluster/<job_id>/`；只读任务优先
- `/agent use` 切换下位时确认其 provider 已配置（先冒烟），避免硬跑失败

## Common Mistakes

- ❌ 把命令当自然语言自由发挥（应严格走路由表）
- ❌ 忘记写 `state.json`（命令执行后必须持久化）
- ❌ `branch` 用缓存的旧值（应 git 实测）
- ❌ 输出散文式长篇（应结论先行 + 表格）
- ❌ `/wd status` 忘了先 `watch` 触发一轮扫描（看门狗是惰性哨兵，扫描才更新状态）
- ❌ `/cluster run` 不写 `--agent`/`--n` 就并行（应显式声明并发与节点）
- ❌ 把 `/agent ls` 当查询天然可用（应先探测 provider，见 SDK §Tool Routing）
