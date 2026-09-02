---
name: sdd-workflow
description: Use when the user asks for spec-driven development, "写规格/规范", "spec first", requirements-first workflow, or when building a large/multi-step feature where ambiguity is costly and the user wants a specification before code. Routes through clarify → specify → plan → tasks → implement → verify.
---

# Spec-Driven Development (SDD) Workflow

> 增强：ticket 本地化流程(to-spec/to-tickets/implement)见 user-vibe_coding-sdk §PathE-SDD

The 2026 successor to unstructured vibe coding: the spec is the source of truth, code is the derived artifact. Early adopters report 3-10x higher first-pass success on non-trivial tasks. Use only when ambiguity is costly — skip for tiny fixes and throwaway experiments (see "When NOT to use").

## When to Use

- Large feature, shared schema change, multi-team dependency, payments/security-adjacent work
- User says "规范驱动", "先写规格", "spec-driven", "需求文档"
- Previous vibe-coding attempts drifted or hallucinated interfaces

## When NOT to Use

- 1-2 line fixes, CSS patches, one-off scripts, throwaway experiments → prompt directly or use quick-edit path

## Workflow

### Phase 1 — Clarify
Surface assumptions and edge cases BEFORE writing anything. Ask the spec-kit-style questions: behavior on failure, edge inputs, deleted resources, timeouts, concurrency. This is the phase most people skip and later regret.

### Phase 2 — Specify
Write `docs/specs/YYYY-MM-DD-<feature>.md`:

```markdown
# <Feature> Spec
## Goal
- what the feature must do, success metrics
## Requirements
- user stories + acceptance criteria (GIVEN/WHEN/THEN or EARS: WHEN [condition] THE SYSTEM SHALL [behavior])
## Design
- architecture, data model, API contracts
## Tasks
- ordered implementation steps, each implementable + testable in isolation
```

### Phase 3 — Plan
Use `writing-plans`: decompose tasks TDD-style. Each task = code + test + acceptance criteria. The more concrete, the fewer wrong assumptions.

### Phase 4 — Implement
TDD + `subagent-driven-development`, one task at a time. Never let the implementer grade its own work.

### Phase 5 — Verify Against Spec
- Independent verifier checks output against acceptance criteria
- **Spec is source of truth**: if code diverges, code is regenerated — not the spec
- Disagreements are resolved by re-reading the spec, not by guessing

## Reference Tooling (external, 2026)

- **GitHub Spec Kit** (~110k ⭐, MIT, 30+ agent integrations): `/speckit.constitution → specify → clarify → plan → tasks → implement → analyze`. Install by copying `.github/instructions/` into the project; agent-agnostic
- **OpenSpec** (~52k ⭐): living-spec for brownfield; proposal → apply → archive state machine, `openspec validate --strict`
- **AWS Kiro**: spec-native IDE; auto-generates requirements.md / design.md / tasks.md with EARS notation
- **BMAD-METHOD** (~47k ⭐): 12+ role-specialized agents (analyst, PM, architect, dev, QA, scrum)

## Rules

1. **Clarify before specify** — unanswered edge cases are bugs waiting to happen
2. **Acceptance criteria are testable** — no "should work", only GIVEN/WHEN/THEN
3. **Spec wins** — drift is fixed in code, not by editing the spec retroactively
4. **Separate implementer from verifier** — no self-grading
5. **Heavy only where warranted** — match ceremony to cost of ambiguity
