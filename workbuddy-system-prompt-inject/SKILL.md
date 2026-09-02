---
name: workbuddy-system-prompt-inject
description: WorkBuddy 系统提示词注入工具（workbuddy-system-prompt-opt v0.2.0）的跨 session 调用入口。触发场景：用户提到"改 WorkBuddy 系统提示词"、"提示词注入"、"系统提示词优化"、"简单模式/高级模式解包"、"WorkBuddy 升级后提示词失效"、"极简模式"、"welcomemode/interactionmode"。覆盖简单模式五阶段（解包→收集→LLM改→注入→验证）与高级模式（Tier-1 缓存覆盖 / Tier-2 app.asar 重打包）的完整命令、核心结论与已知坑。
agent_created: true
---

# WorkBuddy 系统提示词注入（v0.2.0）

## 核心结论（2026-08-31 实测）

**改提示词不需要重打包 `app.asar`**：`cli/dist/codebuddy.js` 的 `resolvePluginInclude()` 按插件名解析 `{% include %}` 到该插件的**缓存目录**（`~/.workbuddy/plugins/cache/workbuddy-builtin/...`）。主模板和全部片段都活在插件缓存里 → **改缓存 = 改运行时提示词**。重打包只用于给界面加「极简模式」卡片这类 UI 级改动（Tier-2 可选能力，WorkBuddy 升级重打包后会消失）。

## 项目位置与入口

```bash
cd "D:/WorkBuddy/2026-07-20-09-30-16/workbuddy-system-prompt-opt"
uv run one-click-run.py          # 交互菜单：简单 [1]-[7] + 高级 [A] + 自检 [S]
uv run one-click-run.py easy unpack|collect|inject|verify|rollback [--apply] [--full]
uv run python -u tests/selftest.py    # 41 项自检
```

## 简单模式（推荐普通用户，五阶段）

| 阶段 | 命令 | 产物 |
|---|---|---|
| 1 解包 | `unpack` | `tmp_wb_asar/`（67 文件秒级，仅提示词部分；`--full` 全量） |
| 2 收集 | `collect` | `my_prompts/` 所见即所得：`1-主提示词`(3) / `2-交互模式片段`(24) / `3-公共片段`(2) / `4-应用内置模板-只读`(22) + `_原版快照/` + `_manifest.json` + 两份说明书 |
| 3 改 | 交给任意 LLM | LLM 自行扫描 `my_prompts/`，按「给AI的说明书.md」的 6 条硬约束改 |
| 4 注入 | `inject --apply` | 只写有差异文件，改动前自动备份到 `backup-easy/<ts>/`，跳过只读 |
| 5 验证/回滚 | `verify` / `rollback` | 与 `_原版快照` 差分校验：上游已有问题=警告，新引入=报错 |

## 高级模式

- **Tier-1**：直接覆盖插件缓存 `prompt.tpl`（3 主模板），部署后新建任务生效。
- **Tier-2**：`app.asar` 7 个声明式 patch + 注册 `welcomemode-minimal`（需 0.9GB 磁盘余量：原包+新包+备份）。

## 已知坑

- **WorkBuddy 升级**会 re-seed 插件缓存 + 覆盖 `app.asar` → 简单模式重跑「收集→注入」、Tier-2 需重打补丁。
- **验证用差分**：上游空文件 / 坏 include（如 MoE 模板引用已删片段）/ 缓存版本落后应用包（`collect` 会提示 `--source asar` 同步）都不算用户错误。
- **生效前提**：完全退出 WorkBuddy 后重启，新建任务才看到改动。
- 本机环境：D 盘满 + Defender 实时扫描时**删除文件约 0.4s/个、写入 0.01s/个** → 批量清理用覆盖而非删除。
- git 仓库推送到本地裸仓库 `D:/git-backup/workbuddy-system-prompt-opt.git`（origin），push 前需用户确认。
