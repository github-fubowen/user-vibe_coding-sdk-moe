# ref-08 — Spec Kit Integration (GitHub SDD Toolkit)

> Load when: running a spec-driven workflow (Path E SDD) and the user wants to use GitHub's
> official spec-kit `specify` CLI; investigating/adding SDD tooling to a project.
> Facts verified by hands-on testing: 2026-08-16 (v0.16.4) + **2026-08-28 (v1.0.1, C2-4)**.

---

## 1. What it is

| Item | Value |
|------|-------|
| Repo | `github/spec-kit` (official GitHub org) |
| License / Stars | MIT · ~130K stars · 11.6K forks（复核 2026-08-18 = 129,902 / 11,630） |
| Language | Python 3.11+ (PyPI package `specify-cli`) |
| Positioning | "Define what to build before building it — with any AI coding agent" |
| Version checked | **1.0.1** (2026-08-28, weekly release cadence) |
| Docs | https://github.github.io/spec-kit/ |

Core idea: **executable specs** — a 7-step spec-driven pipeline (constitution → specify → clarify →
plan → tasks → analyze → implement → converge) executed by any AI coding agent via slash commands.
Extensible via Extensions (new capabilities), Presets (customize workflow), Bundles (role-packaged config).

---

## 2. Verified install & the ONE critical gotcha

### Persistent install (v2.6.0 C2-4 — approved, done 2026-08-28)

```bash
uv tool install specify-cli          # specify 1.0.1 — installed persistently
export PATH="$HOME/.local/bin:$PATH" # uv tool bin dir, if not on PATH
specify --version                    # specify 1.0.1
```
> ⚠️ `uv tool dir` 默认 C:（违反 D 盘策略）——需要时先 `UV_TOOL_DIR=<UV_TOOLS>`；
> 本机 2026-08-28 直接安装成功（uv 0.6.5 已配置 D 盘工具目录）。

### ⚠️ Non-TTY init crash (root-caused, silent exit 1)

`specify init` opens an **interactive arrow-key selector** for script type; in a piped/sandbox
(non-TTY) shell it fails **silently with exit 1** — no error message. Verified fixes (v1.0.1):

```bash
specify init <project> --non-interactive --script sh|ps|py
#        ^^^^^^^^^^^^^^ --non-interactive: never prompt, fail instead of hang (agent harness)
#        ^^^^^^^^^^^^^^ --script: 仅 sh / ps / py（无 bash！v1.0.1 实测）
#        --here 已在项目内时使用；--force 覆盖
```
> v1.0.1 实测：`--non-interactive` 缺一不可；`--script bash` 直接报 `Invalid script type 'bash'`。

---

## 3. Generated project structure (verified, v1.0.1, 2026-08-28)

```
.specify/
  integration.json                  installed integrations + settings (script type, separator)
  integrations/*.manifest.json      copilot / speckit manifests
  templates/                        spec · plan · tasks · checklist · constitution templates
  workflows/                        speckit workflow ("Full SDD Cycle": specify→plan→tasks→implement + review gates)
  memory/constitution.md            project governance principles
  scripts/sh|ps|py/                 helpers (check-prerequisites / create-new-feature / setup-plan / setup-tasks ...)
.github/skills/speckit-*.md/SKILL.md  10 agent skills: constitution · specify · clarify · plan
                                      tasks · analyze · checklist · implement · converge · taskstoissues
```

- **No git repo auto-initialized** — git discipline per ref-07 applies manually.
- 1.0.1 默认 `--integration copilot`（非交互默认值）；agent skills 落在 `.github/skills/`（SKILL.md 形态，最可移植）。

---

## 4. Workflow mapping → SDK Path E (SDD)

| SDK Path E stage | spec-kit command |
|------------------|------------------|
| to-spec | `/speckit.specify` (+ `/speckit.clarify` optional, before plan) |
| to-tickets | `/speckit.plan` → `/speckit.tasks` (+ `/speckit.analyze`, `/speckit.checklist` as quality gates) |
| implement | `/speckit.implement` |
| triage | `/speckit.converge` (diff code vs spec/plan/tasks → append remaining work) |
| governance | `/speckit.constitution` (project principles, run first) |

Manual mode (no agent integration): command files are plain Markdown with frontmatter
(`description`, `handoffs`) — read them as prompts and execute the steps yourself, or run the
bundled workflow: `specify workflow run speckit` (workflow registry at `.specify/workflows/`).

---

## 5. Integrations & WorkBuddy adaptation

| Path | How |
|------|-----|
| **CodeBuddy** (closest to WorkBuddy, verified) | `--integration codebuddy` → installs `.codebuddy/commands/speckit.*.md` |
| **Claude Code** | `--integration claude` — installs **skills** by default (SKILL.md-style, most portable) |
| 30+ others | copilot, codex, gemini, vibe (Mistral), cursor, windsurf, etc. |
| **BYO agent** | `--integration generic --integration-options="--commands-dir .myagent/commands/"` |
| **WorkBuddy** | no native integration. Options: (a) init with `codebuddy` and read command MDs into session; (b) generic + `--commands-dir`; (c) copy command files into a WorkBuddy skill as prompts |

Extensions / presets / bundles: `specify extension|preset|bundle <search|add|install|list|...>`
(community catalog, e.g. Jira, code review, V-Model testing, governance presets).

---

## 6. Sandbox / Windows risks (verified)

1. **uv tool dir defaults to C:** → use ephemeral `uv tool run` + `UV_CACHE_DIR=<UV_CACHE>`, or explicit `UV_TOOL_DIR` before persistent install. Never `uv tool install` silently.
2. **Non-TTY init crash** → always pass `--script ps|sh` (see §2). Other subcommands (`check`, `--version`, `--help`) work fine non-interactively.
3. Init writes only inside the project dir — no home-dir writes (verified).
4. Rich `Live` spinner on Windows PowerShell 5.1: upstream sets `transient=False` on win32 (handled).
5. Weekly release cadence → **pin versions** (`--from git+https://github.com/github/spec-kit.git@v0.16.4` or PyPI pin); re-verify before upgrades (SDK §8 golden-set regression applies to command-file prompt changes).

---

## 7. Quick reference (cheat line)

```bash
uv tool install specify-cli && export PATH="$HOME/.local/bin:$PATH"   # 持久化（C2-4 已批准）
specify check                                                        # 支持的 agent 集成
specify init <project> --non-interactive --script sh|ps|py            # 非 TTY 初始化（v1.0.1）
# then drive the SDD loop with .github/skills/speckit-* (or .specify/workflows/ registry)
# spec.md/tasks.md 落盘后：python scripts/spec-tasks-import.py --tasks tasks.md --tasks-dir <dir>
# 一致性校验：specify workflow run speckit 或 /speckit-analyze skill
```

---

## 8. v2.6.0 深度利用（C2-4，2026-08-28 批准：Path E 默认走 specify）

1. **Path E SDD 默认启用**：新 SDD 任务先 `specify init`（spec.md/tasks.md 由 `/speckit-specify` `/speckit-tasks` 落盘），再进本地实现环；`--script sh`（跨平台）。
2. **tasks ↔ task-state.v1 映射**：`scripts/spec-tasks-import.py --tasks tasks.md --tasks-dir <dir>`——解析 tasks.md 的 `- [ ]` 清单项（支持 `[P0-P3]` 优先级标注）→ 每个任务生成 task-state.v1 JSON（INIT 态，priority/acceptance 字段落位，与 C1-2 生产字段对齐）；stdlib 零 LLM 确定性。
3. **CI 一致性校验**：reusable python-ci 的 smoke-command 可扩展为 `specify workflow run speckit` 或 `/speckit-analyze`（跨工件一致性报告）；本地镜像基线仍以 ci-smoke 为准（§5 风险矩阵：CI 仅测试不发版）。
4. **版本 pin**：specify-cli=1.0.1（周更漂移 → 升级前 golden 前置回归，§8）。
