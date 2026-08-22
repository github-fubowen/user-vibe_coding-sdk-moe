# ref-08 — Spec Kit Integration (GitHub SDD Toolkit)

> Load when: running a spec-driven workflow (Path E SDD) and the user wants to use GitHub's
> official spec-kit `specify` CLI; investigating/adding SDD tooling to a project.
> All facts below **verified by hands-on testing on 2026-08-16** (v0.16.4, Windows sandbox).

---

## 1. What it is

| Item | Value |
|------|-------|
| Repo | `github/spec-kit` (official GitHub org) |
| License / Stars | MIT · ~130K stars · 11.6K forks（复核 2026-08-18 = 129,902 / 11,630） |
| Language | Python 3.11+ (PyPI package `specify-cli`) |
| Positioning | "Define what to build before building it — with any AI coding agent" |
| Version checked | **v0.16.4** (2026-08-14, weekly release cadence) |
| Docs | https://github.github.io/spec-kit/ |

Core idea: **executable specs** — a 7-step spec-driven pipeline (constitution → specify → clarify →
plan → tasks → analyze → implement → converge) executed by any AI coding agent via slash commands.
Extensible via Extensions (new capabilities), Presets (customize workflow), Bundles (role-packaged config).

---

## 2. Verified install & the ONE critical gotcha

### Ephemeral run (recommended in this environment — no C: pollution)

```bash
export UV_CACHE_DIR="<UV_CACHE>"   # D-drive policy: never let uv cache hit C:
uv tool run --from specify-cli specify --version      # specify 0.16.4
uv tool run --from specify-cli specify check          # lists supported agents
```

### Persistent install (only with user approval — defaults to C:!)

```bash
uv tool dir   # ⚠️ default = C:\Users\...\AppData\Roaming\uv\tools → violates D-drive policy
# If approved: uv tool install specify-cli, or set UV_TOOL_DIR=<UV_TOOLS> first
```

### ⚠️ Non-TTY init crash (root-caused, silent exit 1)

`specify init` opens an **interactive arrow-key selector** for script type; in a piped/sandbox
(non-TTY) shell it fails **silently with exit 1** — no error message. Verified fix:

```bash
specify init --here --force --integration codebuddy --ignore-agent-tools --script ps
#                                                                    ^^^^^^^^^^ MUST pass
# --script ps (Windows) / --script sh (Linux/macOS); --ignore-agent-tools skips agent-binary check
```

---

## 3. Generated project structure (verified, codebuddy integration)

```
.codebuddy/commands/speckit.*.md    10 slash-command prompt files:
  constitution · specify · clarify · plan · tasks · analyze · checklist
  implement · converge · taskstoissues
.specify/
  integration.json                  installed integrations + settings (script type, separator)
  integrations/*.manifest.json      codebuddy / speckit manifests
  templates/                        spec · plan · tasks · checklist · constitution templates
  workflows/                        speckit workflow ("Full SDD Cycle": specify→plan→tasks→implement + review gates)
  memory/constitution.md            project governance principles
  scripts/                          powershell / sh helpers
```

- **No git repo auto-initialized** — git discipline per ref-07 applies manually.
- `.codebuddy/` may hold credentials → add to `.gitignore` (init itself warns about this).

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
UV_CACHE_DIR=<UV_CACHE> uv tool run --from specify-cli specify check
UV_CACHE_DIR=<UV_CACHE> uv tool run --from specify-cli specify init --here --force \
    --integration codebuddy --ignore-agent-tools --script ps
# then drive the SDD loop with /speckit.* commands (or read .codebuddy/commands/*.md as prompts)
# extensions/presets/bundles: specify extension|preset|bundle <sub>
```
