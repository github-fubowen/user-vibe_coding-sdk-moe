---
name: context-engineering
description: Use when starting work in a project that lacks AGENTS.md / CLAUDE.md, or when the user asks to set up / improve agent context files, project conventions for AI agents, or onboarding context. Creates or updates map-style agent instruction files.
---

# Context Engineering — AGENTS.md Setup

> 增强：AGENTS.md+CONTEXT.md+docs/adr/ 三层见 user-vibe_coding-sdk §ContextEng

AGENTS.md is the 2026 de-facto standard for agent instructions (Linux Foundation, 60k+ repos). Read natively by Claude Code, Codex CLI, Cursor, GitHub Copilot, Gemini CLI, Aider, Devin, Amazon Q, Windsurf. It complements README.md (human-facing) with agent-facing operational context.

## When to Use

- Project has no AGENTS.md/CLAUDE.md and is non-trivial
- User asks to "让 AI 更懂这个项目", "优化 agent 上下文", "写 AGENTS.md", "setup project context"
- Conventions keep drifting / agents keep violating project rules

## Core Principle: Map, Not Manual

AGENTS.md is a **map** — tell the agent where knowledge lives, not everything. ~200 lines max. Deep topics live in `docs/*` and are linked one line per topic. This keeps the context window lean and current.

## Recommended Structure

```
# Project Name
- 2-3 sentences: what the codebase does, who uses it

## Tech Stack
- Languages/frameworks/libraries with version pins (Node 22, Python 3.13, pnpm 10)

## Setup Commands        ← highest-leverage section (agents waste tokens guessing this)
- Exact install / build / test / run commands

## Code Style
- Formatter, linter, naming, file organization

## Testing
- How to run tests, coverage expectations, test naming

## Architecture
- Key patterns, folder logic, module boundaries. Link: see docs/architecture.md

## PR & Commit Guidelines
- Branch naming, commit format, PR template

## Security
- Secrets handling, auth patterns, deps to avoid

## Boundaries
- ✅ Allowed without asking: read files, run lint/typecheck/single tests
- ⚠️ Ask first: install/remove packages, delete files, push/PR
- 🚫 Never: commit secrets, force-push, modify vendor/dist/build dirs

## Non-Obvious Patterns
- Counterintuitive decisions with mechanism explanations ← highest signal-to-noise
```

## Rules

1. **Map-style, not manual** — root file stays lean; link `docs/*` for deep topics
2. **Setup Commands first** — exact commands the agent can execute
3. **Boundaries section** — what agent may/may not do without asking
4. **Version-control it** — treat updates as code changes, review like code
5. **Monorepo** — one root AGENTS.md + one per package (nearest file wins)
6. **Symlink compatibility** — `ln -s AGENTS.md CLAUDE.md` (or copy) where CLAUDE.md is expected
7. **Draft, don't interrogate** — propose a first version from the codebase, let user correct

## Maintenance

- Check drift on each significant session; update when architecture/commands change
- AGENTS.md > skills > default behavior; explicit user instructions beat everything
