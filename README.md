# user-vibe_coding-sdk-moe

> MoE 特化编程技能 SDK（v1.16.0）——为 Mixture-of-Experts 系大模型（DeepSeek V4 / Qwen3.5-Max / Kimi K2 / GLM-4.6 / MiniMax M2 / Doubao / Hunyuan / Step）调优的编码工作流。

**设计依据**：5 份 CN MoE 调研报告（2026-08）。**三大目标，一套协议**：① 最大化输出质量 ② 最小化 token 消耗 ③ 强制英文思维链。

---

## ✨ 核心特性

- **⛔ 强制英文思维链**：`[GOAL]→[CONSTRAINTS]→[PLAN]→[EXECUTE]→[VERIFY]` 骨架填充式思考，零中文 token，首 token 必须是 `[`（语言镜像陷阱对抗）。
- **思考预算分级**：按任务 T0–T3 开关 thinking（默认 OFF，简单任务不付 5–20× 思维成本）。
- **MoE 路由矩阵**：T0–T4 模型分层（DeepSeek V4 → GLM-4.6 → V4-Flash → 本地模型），含厂商参数差异适配。
- **稳定前缀缓存**：固定指令前置、易变内容后置，命中 DeepSeek 等缓存可省 ~90% 成本。
- **Token 预算六大闸门**（G1–G6）：上下文最小化、渐进式披露、静态工具路由、max_tokens 余量、稳定前缀、廉价模型卸载。
- **输出质量闸门**：压制拟人化尾巴、引用溯源、交付前自检、确定性采样。
- **渐进式披露**：主文件 ~6KB + 19 个 references 按需加载。
- **Token 脚本化流水线**（ref-19，9 脚本全实现）：probe-tools（会话工具探测单次化）/ verify-runner（确定性验证闸）/ bump-version（版本 bump 单命令）/ golden-run（金标回归 1 命令化，结构性判分零 LLM）/ error-sig + case-search（Debug 零 LLM 首轮）/ env-snapshot（环境快照）/ review-prefilter（Review 关注包）/ token-meter（G4/G6 计量）。
- **Agent Doctor 控制面纪律吸收**（ref-17/18）：状态化路由（Pareto 硬过滤 + 强制 fallback_chain + cheap-first 级联）、Debug 诊断协议（确定性先行 → 假设-证据-实验环）、验证五态（UNKNOWN/REGRESSION 一等公民）、风险分层操作门（tier 0–4，tier 4 必人批）。
- **工具栈维护流水线**（ref-15）：`scripts/toolstack-pipeline.py` 六阶段自动化（probe→diff→report→update→commit→push-gate），gh api 上游核对 + SHA256 数据完整性 + push 显式确认门禁。
- **§10 Git 纪律**：本地 commit 默认 / push 必须显式确认 / Conventional Commits / 分支与 worktree 策略 / 技能自版本管理。

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
├── SKILL.md                     # 主文件（~24KB，协议全文，静态前缀）
├── CHANGELOG.md                 # 版本历史（渐进披露，不进热路径）
├── README.md                    # 本文件
├── scripts/                     # 维护工具
│   ├── toolstack-pipeline.py    # 工具栈流水线（ref-15，Python stdlib）
│   ├── probe-tools.py           # 会话级工具探测单次化（ref-19，--json）
│   ├── verify-runner.py         # 确定性验证闸（ref-19，test/lint/build）
│   ├── bump-version.py          # 版本 bump 单命令化（ref-19，永不 push）
│   ├── golden-run.py            # 金标回归 1 命令化（ref-19，结构性判分零 LLM）
│   ├── error-sig.py             # 错误签名库 add/match（ref-19，Debug 零 LLM 首轮）
│   ├── case-search.py           # 问题案例库检索（ref-19，轨迹复用）
│   ├── env-snapshot.py          # 环境快照一次成型（ref-19，PATH 有界）
│   ├── review-prefilter.py      # Review 预过滤精简关注包（ref-19）
│   ├── token-meter.py           # token 计量与指标表（ref-19，G4/G6）
│   ├── robustness-suite.py      # 鲁棒性回归套件 22 用例（ref-19，exit 0/2）
│   ├── data/                    # 种子数据（ref-19 §4.5）
│   │   ├── golden-set-v2.json   # 金标集 v2（20 条 CN 样本，推荐，LongCat 100%）
│   │   ├── golden-set-v1.json   # 金标集 v1（初版判分规则，已被 v2 取代）
│   │   ├── baseline-longcat-v2.json  # LongCat 基线 20/20（A/B 参照）
│   │   ├── baseline-longcat-v1.json  # LongCat 基线 18/20（历史）
│   │   └── error-signatures.json     # 已知错误签名 12 条
│   └── toolstack.json           # pin 单一事实源（机器可读写）
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
```

## 📌 版本与许可

- 版本：**v1.16.0**（changelog 见 `CHANGELOG.md`；每次编辑即提交，遵循自版本管理）
- ref-10（ARS-Codex）为 **CC BY-NC 4.0** 指针引用（不 vendored），其余内容可自由使用。
- 依赖：无第三方依赖；Python 环境可选（工具链建议 uv）。
