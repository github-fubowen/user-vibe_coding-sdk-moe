# ref-10 — Academic Research Skills (ARS-Codex) — lightweight pointer

> Load when: user runs academic/research workflows — systematic review, literature review,
> paper writing/review, experiment planning. Investigated 2026-08-16 (8,650 stars, v0.1.25, active; 复核 2026-08-18 = 8,759 stars, last push 08-14).

## 1. What it is

- Codex 原生「学术研究技能套件」（vendored 自 Imbad0202/academic-research-skills，跟踪上游 ARS v3.20.0）。
- **单技能路由器**（`skills/academic-research-suite/SKILL.md`）统一分派 5 个工作流，模拟 12 个 `ars-*` 别名（ars-plan/outline/summarize/review/…）——替代 Claude Code 多技能 symlink 方案，Windows 友好（实体副本，非 symlink）。

| 工作流 | 用途 |
|--------|------|
| deep-research | 研究问题细化、系统综述、Meta 分析、事实核查 |
| academic-paper | 论文大纲/草稿/摘要/引用格式/AI 披露 |
| academic-paper-reviewer | 稿件评审、模拟同行评审、编辑决策 |
| academic-pipeline | 端到端 研究→论文 流水线（含完整性门禁、评审、修订、终检） |
| experiment-agent | 代码实验规划、人类研究方案、统计解读、可复现性验证 |

## 2. Install & use

```bash
# A. Codex 插件（推荐）
codex plugin marketplace add Imbad0202/academic-research-skills-codex --ref main
codex plugin add ars-codex@ars-codex
# B. 直接装技能
python3 "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo Imbad0202/academic-research-skills-codex --ref main \
  --path skills/academic-research-suite --method git
# 使用：新开 Codex 会话后
# Use $academic-research-suite to build a systematic review protocol on <topic>
# 验证：/skills 应只出现一个 ARS 条目；质量门禁：python3 skills/academic-research-suite/codex/scripts/ars_codex_quality_gates.py all --json
```

## 3. SDK 对接点

- 需要系统综述/文献综述/论文流水线类任务时，把其工作流模板作为参考协议（SDD Path E 的 research 域变体）；
- 其「证据绑定评审/修订」「引用完整性门禁」「PDF 结构预检」「人类受试者权限边界」等契约设计，可借鉴到知识库/研究类项目（用户 KnowledgeOS/量化研究线的质量门禁参考）；
- 可选跨模型评审：`export ARS_CROSS_MODEL="gpt-5.5"`（需显式配置 + 用户同意，默认单运行时）。

## 4. Risks / notes (investigation)

- **许可证 CC BY-NC 4.0（非商业）**：只做指针引用，不 vendored 其内容到本 SDK；商业用途需单独评估；
- 依赖 Codex CLI/Desktop 运行时（OpenAI）；Claude 专属 hooks 仅溯源不执行；
- 上游周更（v3.18→v3.19→v3.20 月内多次）——使用时 pin release tag（当前 v0.1.25 = ARS v3.20.0）；
- 维护质量高：129/129 manifest + 46/46 adapter + 7/7 质量门禁通过，0 open issues。
