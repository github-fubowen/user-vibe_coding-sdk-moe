# wb-cli 命令参考表（完整 44 条）

> 来源：`workbuddy-pseudo-cli-design.md` §4 + `workbuddy-cli-cluster-design.md` §5 + `watchdog-cli-design.md` §7。语法：`wb> /command [subcommand] [--flag value] [args...]`

## 会话控制（7）

| 命令 | 别名 | 作用 | 路由 |
|------|------|------|------|
| `/help [cmd]` | `/h` | 命令帮助 | 本表 |
| `/status` | `/st` | 显示会话状态（cwd/mode/branch/ctx） | 读 state.json |
| `/mode <m>` | — | 切换模式：vibe/eng/sdd/debug/review/quick | 写 state.json |
| `/clear` | — | 清空当前会话上下文（保留状态文件） | memory 清理 |
| `/exit` | — | 结束会话，写 /handoff 摘要 | handoff |
| `/which <cmd>` | — | 查看命令路由到哪个 skill | 本表 |
| `/replay <n>` | — | 重放最近 n 条命令序列 | memory 日志 |

## SDK 六路径（6 主命令）

| 命令 | SDK Path | 工作流 | 典型场景 |
|------|----------|--------|----------|
| `/vibe <任务>` | Path B | 直接实现 → 验证 → 迭代 | 原型、试错、快速验证 |
| `/eng <任务>` | Path A | brainstorm→grill→plan→TDD→subagent | 正式功能、重构 |
| `/sdd <任务>` | Path E | spec→tickets→implement→triage | 大功能、多步骤、团队 |
| `/debug <症状>` | Path C | Phase 0 反馈回路→根因→验证 | bug、行为异常 |
| `/review <目标>` | Path D | OCR→双轴并行审查 | PR、变更审查 |
| `/quick <修改>` | Path F | 轻量 TDD→验证 | 1-2 行小改、typo |

### SDD 子命令（4）

| 命令 | 作用 | 产出 |
|------|------|------|
| `/sdd spec "<主题>"` | 对话→规范文档 | `docs/specs/YYYY-MM-DD-<主题>.md` |
| `/sdd tickets` | 规范→ticket 切片 | `docs/tickets/YYYY-MM-DD-<主题>/NN-*.md` |
| `/sdd implement [NN-]` | 逐张实现（红绿循环） | 代码 + 测试 |
| `/sdd triage <file>` | 批量 issue 分类 | 分类清单 + agent-ready brief |

### Review 子命令（3）

| 命令 | 作用 |
|------|------|
| `/review pr` | 审查 PR/分支 diff（知识图谱上下文） |
| `/review delta` | 只审最近 commit 起的变更 |
| `/review changes` | 审未提交工作区变更 |

## 工程辅助（7）

| 命令 | 作用 | 路由 | 注意 |
|------|------|------|------|
| `/plan "<任务>"` | 写实施计划 | writing-plans | 产出 docs/superpowers/plans/ |
| `/test [filter]` | 运行测试 | TDD / 工具链 | 可接 pytest/uv run |
| `/commit` | 本地提交 | git | **默认执行，不 push** |
| `/push` | 推送远程 | git | **必须用户显式确认** |
| `/diff` | 查看未提交变更 | git | 支持 `/diff staged` |
| `/branch <op>` | 分支操作（list/new/switch） | git | — |
| `/worktree` | git worktree 隔离 | using-git-worktrees | 多文件改动时 |

## 知识检索（5）

| 命令 | 作用 | 路由 |
|------|------|------|
| `/graph <query>` | 代码图谱查询 | graphify / code-review-graph / codebase-memory-mcp |
| `/docs <库名>` | 查库文档 | find-docs / context7 |
| `/search <关键词>` | 代码/内容搜索 | Grep / 图谱 |
| `/context` | 查看/更新 AGENTS.md/CONTEXT.md | context-engineering / context-modeling |
| `/memory` | 查看/写入记忆文件 | memory 系统 |

## 工具类（5）

| 命令 | 作用 | 路由 |
|------|------|------|
| `/run <shell>` | 执行 shell 命令 | Bash/PowerShell |
| `/browser <url>` | 浏览器自动化 | xbrowser |
| `/mcp <server> <tool>` | MCP 工具调用 | MCP 连接器 |
| `/skill <name>` | 显式加载 skill | Skill 系统 |
| `/handoff` | 会话交接文档 | handoff |

## 看门狗（5）— 任务监控与死锁处置

> 后端：`wd.py`（纯文件协议，状态落盘 `.workbuddy/watchdog/registry.json` + `alerts/`）。看门狗是**惰性哨兵**：`/wd status` 前先 `/wd watch` 触发一轮扫描才更新状态。

| 命令 | 作用 | 注意 |
|------|------|------|
| `/wd status` | 状态面板（任务/状态/pid/心跳）+ 未处理告警 | 先 `watch` 再 `status` |
| `/wd watch` | 触发一轮扫描（依赖→存活→心跳→分级处置→槽位调度） | 支持 `--once`（单轮）/ 默认循环 |
| `/wd kill <id>` | 杀任务进程树 | 带 cmdline 校验防 pid 复用误杀 |
| `/wd logs <id> [--tail N]` | 智能解码日志（utf-8/gbk 回退） | 多 agent 混用编码必备 |
| `/wd register --id X --cmd "..." [--log P] [--retries N]` | 注册任务 | 配合 `/wd start <id>` |

> 分级处置：L1 心跳超时→suspect 告警；L2 超时→自动 kill；L3 自动重启（有 retries）；L4 重试耗尽→failed critical。进程退出时有产出→done，无产出→killed。

## 集群（5）— 多 agent 并行编排

> 后端：集群编排层（Bash 派生下位，任务落盘 `.workbuddy/cluster/<job_id>/subtasks/NN.{prompt,log,md}` + `job.json`）。默认并发 ≤3、超时 600s、只读任务优先。

| 命令 | 作用 | 典型用法 |
|------|------|----------|
| `/cluster run "<任务>" [--split] [--n 3] [--agent <name>]` | fan-out 并行分裂 | `/cluster run "拆3模块" --split --n 3 --agent opencode` |
| `/cluster status` | 集群作业进度 | 读 job.json + 子任务状态 |
| `/cluster collect` | 聚合结果 → summary.md 对比表 | 读全部 subtasks/NN.md |
| `/cluster cancel <job_id>` | 取消作业 | kill 未完成任务 |
| `/squad --code <a> --review <b> --docs <c>` | 角色分工集群 | `/squad --code opencode --review ocr --docs hermes` |

### /agent 子命令（3）

| 命令 | 作用 | 注意 |
|------|------|------|
| `/agent ls` | 列出可用下位（codebuddy/opencode/hermes/ocr） | 先探测 provider 可用性 |
| `/agent use <name>` | 切换默认下位 agent | 切换前冒烟测试 |
| `/agent info <name>` | 显示 agent 能力/模型/headless 入口 | — |

> 集群安全红线：`--safe-mode`/只读 agent 优先；git worktree 隔离；超时 kill；`/push` 仍须显式确认。

## 速查卡（日常循环）

```
wb> /mode sdd          # 进入规范驱动模式
wb> /sdd spec "主题"   # 写规范
wb> /sdd tickets       # 拆 tickets
wb> /sdd implement     # 逐张实现
wb> /test              # 全量测试
wb> /review            # 双轴审查
wb> /commit            # 本地提交（不 push）
wb> /status            # 看状态
wb> /handoff           # 交接
```

## 速查卡（集群/看门狗）

```
wb> /wd register --id j1 --cmd "node .../codebuddy -p \"$(cat 01.prompt)\"" --log 01.log
wb> /wd watch          # 触发扫描调度
wb> /wd status         # 看任务面板
wb> /cluster run "并行分析 3 份文档" --split --n 3 --agent codebuddy
wb> /cluster status    # 作业进度
wb> /cluster collect   # 聚合 → summary.md
wb> /wd kill j1        # 卡死处置（带 cmdline 校验）
```
