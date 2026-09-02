# ref-11 — UI/UX Pro Max (Design Intelligence Skill Suite) — pointer entry

> Load when: 设计/构建/审查/修复任何界面（页面、组件、设计系统、可访问性、交互、响应式、
> 排版、配色、图表、技术栈 UI 实现）；Vibe/Engineering 模式遇到 UI/UX 决策需要**数据依据**而非拍脑袋。
> Investigated 2026-08-17 (117.7K stars / 12.6K forks, MIT, daily commits — main @ a38d04c;
> 复核 2026-08-18 = 117,710 stars，HEAD 仍为 a38d04c 零漂移).

## 1. What it is

- nextlevelbuilder/ui-ux-pro-max-skill：给 AI 编程助手的 **UI/UX 设计智能**，核心是**离线可搜索数据引擎**
  （Python 3 标准库，零第三方依赖，无网络请求）：79 可搜索风格（50 活跃）、192 行业配色+推理规则、
  74 字体搭配、119 UX 指南、105 图标指南、17 GSAP 动效预设、25 图表类型、22 技术栈（React/Vue/Svelte/
  Flutter/SwiftUI/WPF/…）。
- 套件内含 **7 个子技能**：ui-ux-pro-max（主引擎）、brand、design、design-system、slides、ui-styling、
  banner-design；另有设计审计 stack（Playwright 截图 + 设计评审 agent）。
- 安装 CLI：`ui-ux-pro-max-cli`（`uipro`），支持 20+ 平台模板，**含 codebuddy**（`.codebuddy/skills/ui-ux-pro-max/SKILL.md`，WorkBuddy 同生态）。

## 2. Install & use (pointer — 未本地安装，按需拉取)

```bash
# 方式 A：CLI 一键安装（推荐，自动装到当前项目 .codebuddy/skills/）
npx ui-ux-pro-max-cli init --ai codebuddy        # WorkBuddy/CodeBuddy 生态
npx ui-ux-pro-max-cli init --ai claude           # 其他平台见 cli/assets/templates/platforms/

# 方式 B：手动拷贝（无需 npm）
git clone --depth 1 https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git
# 拷贝 .claude/skills/ui-ux-pro-max/ 到 skills 目录即可（SKILL.md + scripts/ + data/）
```

运行时调用（skill 内嵌约定）：

```bash
python "${SKILL_ROOT}/scripts/search.py" "<query>" --domain ux|style|color|typography|icons|gsap|chart
python "${SKILL_ROOT}/scripts/search.py" "<product> <industry> <keywords>" --design-system   # 整站设计系统
python "${SKILL_ROOT}/scripts/search.py" "<query>" --stack react                              # 技术栈实现
```

## 3. SDK 对接点

| 场景 | 用法 |
|------|------|
| Vibe 原型 / Engineering 正式 UI | 需要配色/字体/布局依据 → `search.py --design-system` 或 `--domain`，把结果注入上下文（G1 最小化：只注入命中行） |
| UI 审查（Review 模式补充） | `--domain ux` 查 119 条 UX 指南 + 反模式清单，作为审查 checklist |
| 移动/桌面跨端 | 22 stack CSV 直接给组件级实现片段（SwiftUI/WPF/Flutter 等） |
| 视觉方向一致化 | 产出存 `design-system/<project>/`（Master + Overrides 模式） |

## 4. Security audit (2026-08-17, 腾讯云鼎静态审计)

- **核心运行时（SKILL.md + scripts/search.py 等）：Benign（85 分）**——纯标准库、零依赖、
  无网络请求、无 eval/exec/subprocess、无敏感路径操作；`os.unlink`/`writeFileSync` 均为原子写入临时文件清理；
  SKILL.md 明令禁止 agent 运行 sudo/brew/apt/winget。
- **⚠️ Suspicious ×2（供应链提醒，均需用户显式操作才触发，非自动执行）**：
  1. `stack/scripts/setup.sh`：`npx --yes ui-ux-pro-max-cli init`（未锁版本）；
  2. `cli/src/commands/update.ts`：`npm install -g ui-ux-pro-max-cli@latest`（未锁版本）。
  建议：本地安装时 pin 版本或用 npm 锁文件；刷新类脚本（google-fonts/phosphor）只写官方上游，CI 只读权限。
- 无数据外送（无 smtp/webhook/post_data）、无 base64 载荷、无 curl|bash 链。

## 5. Risks (investigation notes)

- 数据随上游更新（每周一 CI 刷新 catalogs）——生产参考时以 clone 的固定 commit 为准；
- 安装包较大（~29M，含字体/图标/多平台副本）；仅指针集成不占本地空间；
- 免费版含全部核心能力；品牌/Logo/CIP 生成属付费高级版（repo 不 vendored）；
- 搜索结果是**推荐依据**，SKILL.md 自身声明不覆盖用户/仓库规则——与 SDK 质量闸门（引用溯源）一致。
