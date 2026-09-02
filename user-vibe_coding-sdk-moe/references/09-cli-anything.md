# ref-09 — CLI-Anything (Agent-Native Software CLIs) — lightweight entry

> Load when: user wants an agent to drive real desktop software (GIMP/Blender/LibreOffice/
> FreeCAD…) without UI automation, or asks "让 AI 直接用这个软件". Investigated 2026-08-16 (47.7K stars, Apache-2.0, Python 3.10+, daily commits; 复核 2026-08-18 = 47,726).

## 1. What it is

- HKUDS 开源框架：把**任何有源码的软件自动生成 Click CLI**，让 AI agent 通过 `which` 发现、
  `--help` 探能力、`--json` 拿结构化结果——替代脆弱的 UI 自动化与缩水的 API 封装。
- 每条生成 CLI 自动附带 **SKILL.md**（可 `npx skills add HKUDS/CLI-Anything` 安装元技能）；
  2,461 测试全过（arXiv:2606.03854）；官方 CLI-Hub 注册表：https://clianything.cc/

## 2. Install & use (verified README, not locally installed — 轻量接入)

```bash
pip install cli-anything-hub          # 包管理器（先装这个）
cli-hub search gimp                   # 搜注册表
cli-hub install gimp                  # 装现成 CLI（依赖上游应用已装）
cli-anything-gimp --json layer add -n "Background" --color "#1a1a2e"   # agent 调用
cli-anything-gimp                     # 有状态 REPL（交互）
```

生成新 CLI（需 Claude Code 插件流程）: `/plugin marketplace add HKUDS/CLI-Anything` → `/plugin install cli-anything` → `/cli-anything ./gimp`；`--integration generic` 思路可类比接入其他 agent。

## 3. SDK 对接点

| 场景 | 用法 |
|------|------|
| Vibe/Engineering 需调真实软件 | `cli-hub install <app>` → 按 `--help`/`--json` 调用 |
| 复用其 SKILL.md 生态 | 参考其 skills 目录结构，与 WorkBuddy SKILL.md 体系互鉴 |
| 给自有软件做 Agent 化 | 跑其 7 阶段流水线（analyze→design→implement Click CLI→test→docs） |

## 4. Risks (investigation notes)

- **依赖前沿模型**才能可靠生成 CLI（README：Claude Opus 4.6 / GPT-5.4 级）——T2/廉价模型不可用；
- Windows 需 Git for Windows（bash/cygpath）或 WSL，否则 `cygpath: command not found`；
- 上游目标软件必须已安装；CLI 生成后需 `pip install -e .` 入 PATH；
- 47K stars / 90 open issues / 日更——生产使用前 pin 版本或 clone 固定 commit。
