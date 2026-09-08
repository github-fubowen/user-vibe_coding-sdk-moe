# user-vibe_coding-sdk-moe

> MoE 特化编程技能 SDK（v2.11.3）——为 Mixture-of-Experts 系大模型（DeepSeek V4 / Qwen3.5-Max / Kimi K2 / GLM-4.6 / MiniMax M2 / Doubao / Hunyuan / Step）调优的编码工作流。

**设计依据**：5 份 CN MoE 调研报告（2026-08）+ 2 份 Coding Agent 架构/技术栈调研（2026-08-30，AgentOS / 主流 Harness 技术栈）。**三大目标，一套协议**：① 最大化输出质量 ② 最小化 token 消耗 ③ 强制英文思维链。

---

## ✨ 核心特性

- **⛔ 强制英文思维链**：`[GOAL]→[CONSTRAINTS]→[PLAN]→[EXECUTE]→[VERIFY]` 骨架填充式思考，零中文 token，首 token 必须是 `[`（语言镜像陷阱对抗）。
- **思考预算分级**：按任务 T0–T3 开关 thinking（默认 OFF，简单任务不付 5–20× 思维成本）。
- **MoE 路由矩阵**：T0–T4 模型分层（DeepSeek V4 → GLM-4.6 → V4-Flash → 本地模型），含厂商参数差异适配。
- **稳定前缀缓存**：固定指令前置、易变内容后置，命中 DeepSeek 等缓存可省 ~90% 成本。
- **Token 预算六大闸门**（G1–G6）：上下文最小化、渐进式披露、静态工具路由、max_tokens 余量、稳定前缀、廉价模型卸载。
- **输出质量闸门**：压制拟人化尾巴、引用溯源、交付前自检、确定性采样。
- **渐进式披露**：主文件 ~36KB + 23 个 references 按需加载。
- **Token 脚本化流水线**（ref-19，9 脚本全实现）：probe-tools（会话工具探测单次化）/ verify-runner（确定性验证闸）/ bump-version（版本 bump 单命令）/ golden-run（金标回归 1 命令化，结构性判分零 LLM）/ error-sig + case-search（Debug 零 LLM 首轮）/ env-snapshot（环境快照）/ review-prefilter（Review 关注包）/ token-meter（G4/G6 计量）。
- **Agent Doctor 控制面纪律吸收**（ref-17/18）：状态化路由（Pareto 硬过滤 + 强制 fallback_chain + cheap-first 级联）、Debug 诊断协议（确定性先行 → 假设-证据-实验环）、验证五态（UNKNOWN/REGRESSION 一等公民）、风险分层操作门（tier 0–4，tier 4 必人批）。
- **工具栈维护流水线**（ref-15）：`scripts/toolstack-pipeline.py` 七阶段自动化（probe→diff→data SHA256→**sdk_tools 差集**→report→update→commit→push-gate），gh api 上游核对 + SHA256 数据完整性 + push 显式确认门禁；`--update` 自动登记新脚本（仅增不删）。
- **§10 Git 纪律**：本地 commit 默认 / push 必须显式确认 / Conventional Commits / 分支与 worktree 策略 / 技能自版本管理。
- **流水线自动化门禁**（ref-23）：pre-commit 钩子（`install-hooks.py` 安装，改脚本跑 robustness 子集 + 新文件过 privacy，fail-closed）+ `ci-smoke.py` 定时冒烟（全量回归栈，`--report` 存档）+ 月检/周度调度自动化。
- **四条脚本化硬闸**（v2.7.0，此前只有协议文本）：① **修复预算** `max_repair_attempts=3` 超限拒绝转移 ② **振荡检测** 同一转移 >3 次拒绝 ③ **Diff Risk Scoring** `>0.7` → exit 2 转人工 ④ **DAG 依赖**未完成禁止开工。硬闸 = 脚本拒绝，不靠 agent 自觉。
- **学习闭环可信化**（v2.7.0）：基础设施失败（空响应/超时/5xx）记 `infra_fail` **不进能力后验**；校准改为「先验快照 vs 事后观测」（旧实现恒等于 0，闸门永不触发）；路由库可 `rebuild` 回溯修复。

## ⚡ 一键部署（任何 Agent 均可）

```bash
# Windows (PowerShell)
.\install.ps1

# macOS / Linux
bash install.sh
```

脚本会把本技能复制到 `~/.workbuddy/skills/user-vibe_coding-sdk-moe/`，随后在任意 WorkBuddy/CodeBuddy 会话中通过 `/user-vibe_coding-sdk-moe` 或自然语言触发（"start coding" / "写代码" / "开发模式" 等）。

> 无本地脚本环境时，手动把 `user-vibe_coding-sdk-moe/` 整个目录放入 `~/.workbuddy/skills/` 即可。

## 🧭 模式路由

| Mode | 触发词 | 工作流 | Thinking |
|------|--------|--------|----------|
| **Vibe** | prototype / 快速试错 | Build → verify → iterate | OFF |
| **Engineering** | 正式功能 / feature | Plan → TDD → review | ON (medium) |
| **SDD** | spec / 规范 | to-spec → to-tickets → implement | ON (high) |
| **Debug** | bug / 报错 | 反馈环 → 根因 → 修复 | ON (medium) |
| **Review** | review / 审查 | OCR → 双轴 subagent | ON (low) |
| **Quick Edit** | 1-2 行小修 | Light TDD → verify | OFF |

## 📁 结构

```
user-vibe_coding-sdk-moe/
├── SKILL.md                     # 主文件（~36KB，实测 36,950B 2026-09-03，协议全文，静态前缀）
├── CHANGELOG.md                 # 版本历史·近期（渐进披露，不进热路径）
├── CHANGELOG-archive.md         # 版本历史·归档（v1.x 时代等 >30 天条目，F-62 策略）
├── ALIGNMENT.md                 # Coding Agent OS → SDK 落地映射总表（29 节，v2.4.0）
├── ENGINEERING.md               # 工程手册（架构/组件/数据流/门禁/操作规程，v2.7.0）
├── README.md                    # 本文件
├── .github/                     # 远程执行引擎（v2.6.0，C2-1/2/3）
│   ├── workflows/ci.yml         # 主 CI（push/PR + workflow_dispatch 三输入）
│   ├── workflows/example-consumer.yml  # reusable 消费方示例
│   └── reusable/                # python-ci / node-ci / docker-build 三件套
├── scripts/                     # 维护工具
│   ├── toolstack-pipeline.py    # 工具栈流水线（ref-15，Python stdlib）
│   ├── probe-tools.py           # 会话级工具探测单次化（ref-19，--json）
│   ├── task-state.py           # 任务状态机持久化（ref-20，状态外置/转移表/黑板 + CI/部署态）
│   ├── task-workspace.py        # per-task 独立工作区 + worktree（ref-20/C1-1，fail-closed）
│   ├── router-stats.py         # 离线路由反馈+校准（ref-20/ref-22，Beta 后验/Thompson/零 LLM）
│   ├── verify-runner.py        # 确定性验证闸（ref-19，分层 cheapest-first + diagnostic.v1）
│   ├── ci-fail-analyze.py       # CI 失败日志→diagnostic.v1（C1-4，五类正则，零 LLM）
│   ├── bump-version.py         # 版本 bump 单命令化（ref-19，永不 push）
│   ├── golden-run.py            # 金标回归 1 命令化（ref-19，结构性判分零 LLM）
│   ├── spec-tasks-import.py     # spec-kit tasks.md→task-state.v1（C2-4，stdlib）
│   ├── error-sig.py             # 错误签名库 add/match（ref-19，Debug 零 LLM 首轮）
│   ├── case-search.py           # 问题案例库检索（ref-19，轨迹复用）
│   ├── env-snapshot.py          # 环境快照一次成型（ref-19，PATH 有界）
│   ├── review-prefilter.py      # Review 预过滤精简关注包（ref-19）
│   ├── token-meter.py           # token 计量与指标表（ref-19，G4/G6；传 --budget 超限 → exit 2，F-50）
│   ├── diff-risk.py             # 补丁风险确定性评分（ref-22 §8，>0.7 → exit 2 人工，fail-closed）
│   ├── robustness-suite.py      # 鲁棒性回归套件（ref-19，--only/--json/--timing/--quick；用例数以 --json 的 total 为准，不写死——F-64）
│   ├── cases/                   # 声明式用例 manifest（v2.10.12 F-59 Phase 1：eval/gates/router/release/pipeline 五域 JSON，schema robustness-cases.v1）
│   ├── gh-workflow-check.py     # .github 结构校验（C2-3，dispatch 契约 + reusable-only）
│   ├── privacy-scan.py          # 隐私泄漏扫描（ref-23，fail-closed）
│   ├── git-pre-commit.py        # 提交前门禁（ref-23，robustness 子集 + data + privacy + v2.10.2 selfcheck 闸，fail-closed）
│   ├── install-hooks.py         # pre-commit 钩子安装/卸载（ref-23，幂等）
│   ├── ci-smoke.py              # 定时冒烟（ref-23，全量回归栈 + --report 存档）
│   ├── version-check.py         # 版本串 + CHANGELOG 顺序闸（T-16，ci-smoke 第 0 步）
│   ├── selfcheck-static.py      # 静态结构自检（v2.10.2，frontmatter/refs/脚本/toolstack 双向，ci-smoke 第 2 步 + pre-commit 第 4 闸）
│   ├── flaky-check.py           # flaky 前置判别（T-20，N≥5 混合结果→QUARANTINE）
│   ├── regression-guard.py      # 回归测试双向闸（T-21，base 须 FAIL / head 须 PASS）
│   ├── patch-gate.py            # 补丁规模预算闸（T-23，files≤5/lines≤300/deps≤1）
│   ├── mutation-audit.py        # 门禁变异测试审计（v2.10.4：把闸改成恒放行，看有没有用例变红）
│   ├── action-gate.py           # 动作预执行门（T-25，toolstack 风险分级，tier≥4 须人工）
│   ├── toolstack.json           # 工具栈 manifest（sdk_tools 29 / local_tools 8 / refs 8 / sdk_tools_exempt）
│   ├── data/                    # 种子数据（ref-19 §4.5）
│   │   ├── golden-set-v3.json   # 金标集 v3（32 样本 / 8 cell 标签，**推荐**，离线 32/32）
│   │   ├── baseline-golden-v3-offline.json  # v3 离线基线（A/B 参照）
│   │   ├── baseline-golden-v3-online.json   # v3 在线基线（auto/best-coding，C0-5）
│   │   ├── golden-set-v2.json   # 金标集 v2（20 条 CN 样本，LongCat 100%）
│   │   ├── golden-set-v1.json   # 金标集 v1（初版判分规则，已被 v2 取代）
│   │   ├── baseline-longcat-v2.json  # LongCat 基线 20/20（A/B 参照）
│   │   ├── baseline-longcat-v1.json  # LongCat 基线 18/20（历史）
│   │   └── error-signatures.json     # 已知错误签名 12 条
│   │   └── memory/                   # 分层记忆（ref-20/ref-21，coding-agent-os §14 吸收）
│   │       ├── repo-facts.json       # 仓库事实层
│   │       ├── conventions.json      # 约定层
│   │       ├── solutions.json        # 成功方案层
│   │       └── preferences.json      # 偏好层
│   │   └── router-stats.db           # 路由反馈带（runtime 生成，.gitignore 排除）
│   ├── presets/                 # 随包验证阶梯（v2.7.0，T-07）
│   │   ├── verify.python.json   # format→lint→typecheck→test→security（缺工具 allow_missing 跳过）
│   │   ├── verify.node.json     # lint→typecheck→test→build→audit
│   │   └── verify.docs.json     # Markdown 相对链接可达性 + UTF-8（零依赖）
│   └── toolstack.json           # pin 单一事实源（schema 3，含 29 个自有脚本的工具元数据）
├── .workbuddy/debug-cases/      # 问题案例库（ref-18 §5，4 个真实 incident）
└── references/                  # 渐进式披露（按需加载）
    ├── 01-thinking-protocols.md # CoT 变体与反啰嗦
    ├── 02-routing-matrix.md     # 模型路由 / 采样参数
    ├── 03-prompt-templates.md   # 可复制提示词模板
    ├── 04-cache-strategy.md     # 缓存命中策略
    ├── 05-eval-loop.md          # 金标集 / 回归
    ├── 06-token-budget.md       # token 预算测算
    ├── 07-git-workflow.md       # Git 纪律细则
    ├── 08-spec-kit.md           # GitHub spec-kit 集成
    ├── 09-cli-anything.md       # CLI-Anything 轻量条目
    ├── 10-academic-research-skills.md  # ARS-Codex 指针引用
    ├── 11-ui-ux-pro-max.md     # UI/UX Pro Max 指针引用
    ├── 12 (外部指针)           # public-apis — 公共 API 离线检索（../public-apis/SKILL.md）
    ├── 13-strix.md             # Strix AI 渗透测试指针引用
    ├── 14-cybersecurity-skills.md  # Anthropic Cybersecurity Skills 本地库+路由器
    └── 15-toolstack-pipeline.md    # 工具栈维护流水线（probe→diff→report→update→commit→push-gate）
    └── 16-context7.md              # Context7 — 实时库文档查询 / ctx7 技能管理 / MCP（upstash/context7）
    └── 17-agent-doctor.md          # Agent Doctor 架构吸收记录（AI Ops 控制面纪律，本地文档指针）
    └── 18-debug-diagnosis.md       # Debug 诊断协议（确定性先行→假设环→验证五态→案例库）
    └── 19-token-scripts.md         # Token 脚本化流水线（9 脚本全实现，ref-19）
    └── 20-task-state-machine.md    # 任务状态机+黑板协议（coding-agent-os §10-11 吸收，ref-20）
    └── 21-context-engineering.md   # 上下文工程检索协议（coding-agent-os §7 吸收，ref-21）
    └── 22-repair-escalation.md     # 修复升级阶梯 L0-L5（coding-agent-os §6.6/§13 吸收，ref-22）
    └── 23-pipeline-automation.md   # 流水线自动化与门禁（pre-commit/ci-smoke/调度，ref-23）
    └── 24-gh-security.md           # 远程执行引擎安全设计（installation token 最小权限，ref-24）
```

## 📌 版本与许可

- 版本：**v2.11.3**（changelog 见 `CHANGELOG.md`；每次编辑即提交，遵循自版本管理）
- ref-10（ARS-Codex）为 **CC BY-NC 4.0** 指针引用（不 vendored），其余内容可自由使用。
- 依赖：无第三方依赖；Python 环境可选（工具链建议 uv）。
