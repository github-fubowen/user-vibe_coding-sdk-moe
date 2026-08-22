---
name: user-vibe_coding-sdk-moe
description: >
  MoE-optimized coding skill SDK (v1.16.0). USE when the user starts a coding session,
  says "start coding" / "coding mode" / "vibe coding" / "开发模式" / "写代码" /
  or asks to begin any write/debug/review/refactor task. Maximizes Mixture-of-Experts
  model output quality via MANDATORY ENGLISH COT (thinking chain), per-task thinking
  budget control, model routing matrix, stable-prefix caching, and token-budget
  gates — while cutting token consumption 30-60% vs default prompting.
  Route to the right path: Vibe / Engineering / SDD / Debug / Review / Quick-Edit.
---

# user-vibe_coding-sdk-moe v1.16.0 — MoE-Optimized Coding SDK

> **What this is**: A coding SDK tuned for MoE-family models (DeepSeek V4/Qwen3.5-Max/Kimi K2/GLM-4.6/MiniMax M2/Doubao/Hunyuan/Step).
> **Design basis**: 5 research reports (2026-08): CN MoE architecture survey, MoE capability-maximization handbook, LLM DIY tuning handbook, LLM power-user handbook, GitHub MoE ecosystem survey.
> **Three goals, one protocol**: (1) Maximize output quality, (2) Minimize token consumption, (3) Mandatory English thinking chain.
>
> **版本历史**：完整 changelog 见 `CHANGELOG.md`（渐进披露，不进热路径）。

> **v1.0 差异（vs user-vibe_coding-sdk v2.1）**: 强制英文思维链协议 · 思考预算按任务分级 · MoE 路由矩阵 · 稳定前缀缓存硬规则 · token 预算闸门 · 质量闸门（压制拟人化尾巴/引用溯源/自检/Reflection）· 渐进式披露结构（主文件 + 6 references 按需加载）。

---

## ⛔ LANGUAGE RULES — read FIRST, obey at EVERY step (non-negotiable)

> **THINKING = ENGLISH ONLY. ALWAYS. NO EXCEPTIONS. ZERO CJK TOKENS inside any thinking chain.**
>
> 1. **Independence rule**: thinking language and output language are TWO separate channels.
>    - OUTPUT → follows the user (Chinese by default). THINKING → ALWAYS English.
>    - Even when the user writes Chinese, the task is CN-domain, or the deliverable is Chinese — thinking stays English.
> 2. **First-token hook (mechanically checkable)**: the FIRST token of every thinking block MUST be `[` — the opening of `[GOAL]`.
>    - If your first thought is Chinese prose (e.g. "用户要求…让我先…"), you have ALREADY violated this rule. Restart the chain.
> 3. **Visible thinking**: this host (WorkBuddy) renders the deep-thought chain to the user — thinking is NOT invisible here.
>    → Apply the same strictness to thinking as to output: a Chinese thinking chain is a visible defect.
> 4. **Banned in thinking (hard violations — see corrected pairs)**:
>    ❌ `用户要求使用该技能来安装项目…首先我需要调用工具…让我先加载技能`
>    ✅ `[GOAL] Execute install+test for the requested project using this SDK.`
>    ❌ `让我先…` / `好的，我们…` / `首先，我需要…` / `接下来…`
>    ✅ `[PLAN] Step 1: …` / `[EXECUTE] …` / `[VERIFY] …` (English skeleton, no narration)
> 5. **CJK scan before finishing ANY thinking block**: if any Chinese character appears in thinking, rewrite that block in English immediately. Do not carry it forward.

---

## 0. Core MoE Principles — read once, obey always

1. **Thinking is a paid option, not a model trait.** MoE models expose thinking ON/OFF (DeepSeek thinking mode, Qwen `/think` `/no_think`, Hunyuan deep-think). Simple tasks with thinking ON cost 5–20× more tokens AND drop accuracy (overthinking). **Default OFF, enable per task tier** (§2).
2. **Thinking tokens eat `max_tokens`.** Reasoning tokens count toward output budget on most APIs. Undersized `max_tokens` = truncated answer. **Measure the distribution first, then set `max_tokens = thinking + answer`** (ref-06).
3. **Stable prefix = money + quality.** MoE providers offer prompt caching (DeepSeek ~1/10 price on hit). Cache hits require **byte-identical prefixes**. Fixed instructions first, volatile content last (ref-04).
4. **Context is a pool, not a dumpster.** MoE models handle 256K–1M context, but attention dilutes mid-context. Inject task-relevant material, never everything (§7).
5. **You cannot control expert routing.** Router is token-level, training-side. Your levers are only: what you input, how you sample, which thinking budget. Don't chase "expert activation" myths — chase structured prompts.
6. **Pin versions, regression-test on change.** CN MoE models iterate weekly. Use dated version IDs (`deepseek-v4-pro-0813`), not semantic aliases. Golden set regression before every config change (ref-05).

---

## 1. Mode Selection — pick ONE first (decides workflow + thinking budget)

| Mode | Triggers | Workflow | Thinking budget | Sampling |
|------|----------|----------|-----------------|----------|
| **Vibe** (prototype) | "vibe", prototype, 快速试错, throwaway | Build fast → verify → iterate; skip planning ceremony | OFF (or low) | temp 0.5–0.7 |
| **Engineering** (feature/refactor) | new feature, production code, 正式功能 | Plan → TDD → subagents → review | ON (medium) | temp 0.2 |
| **SDD** (spec-driven) | "spec", 规范, multi-step feature, team project | to-spec → to-tickets → implement → triage | ON (high for design, medium for impl) | temp 0.2 |
| **Debug** (fix) | bug, 报错, unexpected behavior | Deterministic-first (§2, ref-18) → hypothesis loop (ref-18) → fix → verify (五态 §5.6) | ON (medium) | temp 0 |
| **Review** (review) | review, 审查, feedback | OCR first → dual-axis subagents (standard + spec) | ON (low–medium) | temp 0.2 |
| **Quick Edit** (small fix) | 1-2 line fix, typo | Light TDD → verify | OFF | temp 0 |

**Routing rules**:
- 需求澄清且无明确 spec → `grilling`（一次一问，决策树收敛）before ANY path.
- Path A Engineering: `brainstorming → grilling → writing-plans → test-driven-development → subagent-driven-development`.
- Path E SDD (local loop): `to-spec → to-tickets → implement → triage(可选)` — spec-kit 集成见 ref-08（`specify` CLI；非 TTY 环境 init 必须 `--script ps|sh`）。
- Load skills lazily by description — never bulk-load. **MCP set: 3–6 servers max.**

---

## 2. Mandatory Thinking Protocol — ENGLISH CoT (core differentiator)

> **THINK IN ENGLISH. ALWAYS. NO EXCEPTIONS.** See the ⛔ LANGUAGE RULES banner at the top — it overrides everything below on language questions.
> Rationale: (a) English reasoning tokens are denser — structured markers (`GOAL/CONSTRAINTS/PLAN/VERIFY`) cost near-zero; (b) reasoning-model training corpora are English-dominated, so English CoT tracks the model's strongest reasoning path; (c) structured thinking cuts thinking-token spend 30–60% vs rambling self-talk (proven in DIY tuning handbook §2.2, §8.1).
>
> **Language mirror trap (root cause of CN leakage)**: CN MoE models mirror the user's input language inside their own reasoning. Chinese user input + Chinese priming in the SDK doc = Chinese thinking chain. Counter-measures (ALL mandatory):
> 1. First token of every thinking block MUST be `[` (`[GOAL]`). Chinese prose as an opener = instant violation → restart.
> 2. Thinking is a SEPARATE channel from output: output follows the user (CN default), thinking is ALWAYS English.
> 3. In WorkBuddy the deep-thought chain is user-visible → treat thinking language with the same strictness as output.
> 4. Before closing ANY thinking block, scan for CJK characters; rewrite the block in English if any appear.

### 2.1 Thinking skeleton — fill this template, not free-form thought

Before ANY non-trivial output, think in this exact skeleton (in English):

```
[GOAL]   Restate the objective in one sentence. What must be true at the end?
[CONSTRAINTS] List hard constraints: inputs, forbidden moves, format, boundaries.
[PLAN]   Break into steps. Each step does ONE thing. No premature conclusions.
[EXECUTE] Do the work step by step. Invoke tools when precision beats guessing.
[VERIFY] Check: did every step satisfy every constraint? Recompute if needed.
         If contradiction found → backtrack to PLAN, not forward.
```

Rules:
- **No self-talk, no "Let me..." rambling.** Thinking is a skeleton fill, not a diary.
- **ZERO CJK in thinking.** Chinese characters, Chinese sentence patterns, and CN filler words are banned inside the skeleton. If you catch yourself thinking in Chinese, restart that block with `[GOAL]` in English. (Language mirror trap — see §2 note.)
- **First token must be `[`.** The chain opens with `[GOAL]`, never with Chinese prose.
- **Dead-end rule**: never retry the same path twice. Switch strategy and state why.
- **Verification is mandatory before final answer**: checklist in §5.3.
- **Thinking stays invisible.** Reasoning NEVER appears in the final output.

### 2.2 Thinking budget by task tier

| Tier | Task examples | Thinking | Budget |
|------|---------------|----------|--------|
| T0 | Complex math, multi-step reasoning, algorithm design, architecture | **ON** | high / give headroom |
| T1 | Code gen, debugging, structured reports, long writing | ON | medium–high (writing: low–medium to prevent over-polish) |
| T2 | Classification, extraction, translation, formatting | **OFF** (explicit `/no_think`) | 0 |
| T3 | Real-time chat, streaming | OFF | 0 (latency first) |

**Overthinking check**: if thinking tokens > 70% of total output AND accuracy didn't improve → cut budget (ref-06).

### 2.3 Few-shot thinking demo (structure, not content)

```
User: A train 300m long passes through a 900m tunnel at 72 km/h. How many seconds?
Think:
[GOAL] Time for train to fully clear the tunnel.
[CONSTRAINTS] Full pass = front enters until rear exits; distance = 300+900 = 1200m.
[PLAN] 1) convert km/h→m/s  2) t = distance/speed
[EXECUTE] 72 km/h = 20 m/s. t = 1200/20 = 60 s.
[VERIFY] Units consistent (s), logic complete. Answer: 60 seconds.
```

---

## 3. Token Budget Gates — apply before every session/task

| Gate | Rule |
|------|------|
| **G1 Context minimalism** | Load only what the task needs: relevant skill description, relevant files, relevant docs. Never "full repo" context. |
| **G2 Progressive disclosure** | This SKILL.md is the entry (~6KB). Load `references/*` only when a section is needed — NEVER the whole set. |
| **G3 Static tool routing** | §6 maps mode → toolset ONCE (static, ~0 extra tokens). Probe availability once per session; degrade silently. |
| **G4 max_tokens headroom** | Measure thinking-token distribution on first run (ref-06), then set `max_tokens = thinking + expected answer × 1.5`. |
| **G5 Stable prefix** | System prompt + fixed task instructions FIRST (cacheable), volatile content (user input, retrieved chunks) LAST (§7). |
| **G6 Cheap-model offload** | T2/T3 bulk work → V4-Flash / local Qwen3-A3B / local embedding. T0/T1 high-value → flagship (ref-02). |

Token math (ref-06):
```
task_cost = (in_tokens×in_price + out_tokens×out_price + think_tokens×think_price)
            × (1 − cache_hit_rate × cache_discount)
```

---

## 4. Model Routing — MoE-native tier matrix (summary; full table in ref-02)

| Tier | Tasks | Primary | Alt | Thinking | temp |
|------|-------|---------|-----|----------|------|
| **T0** | High-intelligence reasoning, code, agent brain, long-form writing | DeepSeek V4 (1.6T/49B, 1M ctx) | Qwen3.5-Max (397B/17B, 1M), Kimi K2 (1.04T/32.6B, agent-native) | ON | 0.2 |
| **T1** | Summarize, translate, structured extraction, routine writing | GLM-4.6 (400B/45B) | Doubao-1.5-pro, MiniMax M2 (complex multi-hop) | OFF–medium | 0.2–0.3 |
| **T2** | Classification, tags, formatting, simple QA, chat | DeepSeek V4-Flash (284B/13B) | Qwen3 series, Doubao light | OFF | 0 (classify) / 0.7 (chat) |
| **T3** | Private data, batch embedding, offline, free | Local Qwen3-30B-A3B (3B active) | Local MiniLM embedding | — | 0 |
| **T4** | Edge / end-cloud | Step-3.5 Flash (1960B/110B) | Qwen3-30B-A3B | — | — |

Routing rules:
- **Task tier is a declaration, not a default** — every task states its tier; gateway routes + auto-degrades (T0 down → T1 backup).
- **Pareto hard-filter first (ref-17)**: before selecting, drop any model that violates a hard constraint (context window < task need, provider unavailable, over budget ceiling, missing required capability). Never let a cheap-price advantage override a hard constraint.
- **fallback_chain is mandatory (ref-17)**: every routing decision precomputes its degrade chain — provider failover → same-family cheaper model → local model → cached trajectory reuse → deterministic rule-only path. Failover uses the precomputed chain, no extra inference call.
- **Tool protocol mismatch**: GLM uses XML tool templates — do NOT force JSON schema on it. DeepSeek/Qwen/Kimi/Doubao use JSON schema function calling. Wrap differences in one adapter layer (ref-02).
- **Agent-native workloads** (long-horizon tool use) → Kimi K2 / MiniMax M2 / GLM-4.6. High-concurrency bulk → V4-Flash.
- **Cheap-first cascade (ref-17)**: local/cheap models attempt classification/filtering/extraction first; escalate to a larger model only if confidence is below threshold. Early exit once confidence crosses the action threshold.
- **Quality gate**: switching to a cheaper model is OK if golden-set accuracy drops <2%; >5% → revert to higher tier (ref-05).

---

## 5. Output Quality Gates — apply before delivering

### 5.1 Suppress anthropomorphic tails (CN MoE quirk)

System prompt MUST include (English works; CN models obey CN better — use CN version):
```text
# 输出规范
- 直接给出结果。禁止开场白、寒暄、"好的/当然/没问题/让我们"。
- 思考内容不得出现在最终输出中。
- 格式：{JSON | Markdown | 代码块}，结构见示例。
```

### 5.2 Grounding — citations for trust

- Tag injected material: `<source src="...">`; require `[n]` citations in output.
- Code-side check: every citation must exist in the material — the ONLY mechanically verifiable anti-hallucination.
- "No citation = not trusted" for finance/legal/high-stakes tasks.

### 5.3 Pre-submission self-check (in thinking, not in output)

```text
□ Recompute: is the math/logic re-verified?
□ Constraints: does every step satisfy every constraint?
□ Citations: are sources cited (where applicable) and accurate?
□ Format: byte-exact match with the required structure?
□ Thinking language: scan this thinking block for CJK — ZERO Chinese tokens allowed
  (first token was `[GOAL]`; any CN prose → rewrite block in English, then re-verify).
If any fails → fix, then output.
```

### 5.4 Reflection for high-value output (2-stage, ~3× cost, often +30% quality)

Produce → criticize (adversarial pass: logical holes, wrong assumptions, omissions) → revise. Only for high-stakes deliverables; skip for routine tasks.

### 5.5 Deterministic sampling

- Reasoning/code/data: `temperature 0.2` (or 0 for strict extraction), `top_p` default.
- Reproducible experiments: fix `seed` + input order. Note: `temperature=0` is NOT guaranteed deterministic across providers.
- Self-Consistency (3–5 samples, temp 0.7, majority vote) ONLY for high-cost-failure decisions — never per-call.

### 5.6 Verification five-state (ref-17/18)

Every fix/repair closes with a verdict — **SUCCESS is never the default**:

| State | Condition | Next action |
|---|---|---|
| SUCCESS | Pre-state reproduced → action → post-state clean, no downstream anomaly | close, log case |
| PARTIAL_SUCCESS | main symptom gone, residual/minor issues remain | record residual, explicit degraded delivery |
| FAILED | symptom persists | back to hypothesis loop (evidence updated) |
| REGRESSION | target fixed but blast-radius anomaly (something depending on it broke) | check DEPENDS_ON/CONFLICTS neighbors, add regression fix |
| UNKNOWN | cannot determine (insufficient signals / unstable repro) | run one more experiment; NEVER force into SUCCESS/FAILED |

Debug 模式细则（确定性先行清单、假设 schema、案例库格式）见 ref-18。验证步骤用确定性闸：`scripts/verify-runner.py --config verify.json --json`（ref-19）——脚本报 pass/fail 事实，五态判定留在 agent。

---

## 6. Tool Routing — mode → toolset (static map)

| Mode | Tools (priority order) | Purpose | Probe |
|------|------------------------|---------|-------|
| **Review** | `review-prefilter.py`（ref-19, 差异统计+静态检查→精简关注包）→ `ocr` CLI → code-review-graph MCP (get_review_context/get_impact_radius) → graphify MCP (query_graph) → `gh` CLI → `strix` (ref-13, 授权安全审计) | line-level review + blast radius + graph + PR data + PoC 漏洞验证 | `probe-tools.py --json` / MCP registered? / `strix --version` |
| **Debug** | code-review-graph MCP (debug-issue) → graphify MCP (query_graph) → codebase-memory-mcp (trace_path) | graph navigation + feedback loop | same |
| **Engineering** | codebase-memory-mcp (search_graph/trace_path) → code-review-graph (refactor_tool) → graphify (query_graph) → find-docs · `cli-hub` (ref-09, 真实软件 Agent 化) | retrieve/trace + safe refactor + understand + docs · 驱动桌面软件 | same · `cli-hub --version` |
| **SDD** | `specify` CLI (ref-08) → find-docs / context7-cli (ref-16) → codebase-memory-mcp (search_graph) | spec-kit SDD pipeline + docs + retrieval | `uv tool run --from specify-cli specify --version` |
| **Vibe** | graphify (light codebase understanding) · ui-ux-pro-max (ref-11, 离线 UI/UX 设计智能) | prototype cheap · UI/UX 设计依据 | same |
| **Quick Edit** | none (task too small) | fix → verify | skip |

Probe rules: **once per session via `scripts/probe-tools.py --json`**（ref-19 单次调用探全部，替代逐个 `--version`）; unavailable → next in chain, never block; report degradation in final summary. **Minimal-need principle**: graph query > grep > full-file read.

**维护（工具栈巡检）**：`python scripts/toolstack-pipeline.py --update --commit`（ref-15）——六阶段 probe→diff→report→update→commit→push-gate；`--push` 需交互 TTY 显式确认。建议每月一次（§8 version-drift re-run 落地）。

**Security/DFIR 任务链**（任何安全域任务，先走授权门禁）：`reverse-skill-router`（入口，授权确认）→ `cybersecurity-skills-router`（ref-14 本地库检索，search.py 只读）→ 目标 SKILL.md playbook（方法）→ ref-13 Strix / 既有工具（执行）→ Verification 验证。⚠️ 未确认目标归属与书面授权 → 禁止调用攻击类技能。

---

## 7. Context Assembly — stable prefix structure

```text
[System prompt (role/rules/thinking protocol/output spec)]   ← FIXED, never changes (cache hit zone)
[Task instructions (invariant part)]                         ← FIXED
[Material pool (docs/knowledge chunks, injected on demand)]  ← versioned, stable
-----------------------------------------------------------------
[User input this turn]                                       ← volatile, LAST
[Retrieved results this turn]                                ← volatile, LAST
```

- Byte-identical prefix = cache hit. One extra space/newline/timestamp breaks it.
- If 20% of the pool changes often: keep the stable 80% inside the cached prefix, push the volatile 20% after it.
- Long-context usage: full document injection for whole-book analysis (cite sections); key-files + tree for codebases; retrieval top-k for Q&A (8–16K chunks OK on 1M-context MoE).

---

## 8. Evaluation & Version Drift — close the loop (ref-05)

- **Golden set**: 20–50 CN-first samples covering QA/code/long-text/extraction/tool-use, each with acceptance points. Full regression on ANY change (prompt/model/params/skill).
- **Metrics**: pass rate · **token efficiency** (out+think tokens / passed — the number to watch) · think-token ratio (>70% without accuracy gain = overthinking) · **cache hit rate** (<60% = prefix construction broken) · cost/task · version drift (monthly re-run).
- **Version pinning**: dated IDs in production (`deepseek-v4-pro-0813`), never semantic aliases. A/B on golden set before switching.

---

## 9. References (progressive disclosure — load on demand)

| Ref | File | Load when... |
|-----|------|--------------|
| 01 | `references/01-thinking-protocols.md` | Need deeper CoT variants (protocol vs literal vs skeleton injection), English CoT fine-tuning, anti-rambling techniques |
| 02 | `references/02-routing-matrix.md` | Choosing models, per-vendor sampling params, tool-protocol differences, agent-native workload mapping |
| 03 | `references/03-prompt-templates.md` | Need copy-paste system prompt templates (EN/CN), structured-output spec, few-shot examples |
| 04 | `references/04-cache-strategy.md` | Designing stable prefixes, cache-hit rules, context caching pitfalls |
| 05 | `references/05-eval-loop.md` | Building golden sets, metrics, A/B experiments, LLM-as-judge, regression workflow |
| 06 | `references/06-token-budget.md` | Computing token budgets, thinking-token measurement, cost accounting, billing checkups |
| 07 | `references/07-git-workflow.md` | Commit/push/branch discipline, undo recipes, skill self-versioning — detailed workflows for §10 |
| 08 | `references/08-spec-kit.md` | GitHub spec-kit (`specify` CLI) — verified install/init gotchas, Path E mapping, WorkBuddy adaptation (§1, §6) |
| 09 | `references/09-cli-anything.md` | CLI-Anything (HKUDS) — 软件 Agent-Native CLI 生成，cli-hub 用法与风险（轻量条目, §6 Engineering） |
| 10 | `references/10-academic-research-skills.md` | ARS-Codex — 学术研究技能套件（系统综述/论文流水线/实验 agent），CC BY-NC 指针引用 |
| 11 | `references/11-ui-ux-pro-max.md` | UI/UX Pro Max — 设计智能技能套件（7 子技能，离线数据引擎），核心运行时 Benign / CLI 2 项 Suspicious，§6 Vibe 接入 |
| 12 | `../public-apis/SKILL.md` | public-apis — 公共 API 离线检索（50 分类 / 1668 API，数据 pinned commit + SHA256 溯源，stdlib 只读脚本 Benign），Tier T2 |
| 13 | `references/13-strix.md` | Strix — AI 渗透测试（授权目标）：Graph of Agents 多代理利用+PoC 验证，SARIF/MD 报告，官方 4 技能，§6 Review 接入；⚠️ 仅限授权 |
| 14 | `references/14-cybersecurity-skills.md` | Anthropic Cybersecurity Skills — 817 技能 / 34 域 / 6 框架安全知识库（agentskills.io），**已本地落地**（`cybersecurity-skills` 全量库 + `cybersecurity-skills-router` 检索），复核审计 Benign；安全任务走 §6 链：reverse-skill-router → cybersecurity-skills-router → ref-14 → Strix；⚠️ 仅限授权 |
| 15 | `references/15-toolstack-pipeline.md` | 工具栈维护流水线（`scripts/toolstack-pipeline.py` + `toolstack.json`）——probe→diff→report→update→commit→push-gate 六阶段自动化，gh api 上游核对 + SHA256 数据完整性 + push 显式确认门禁（§10 纪律编码） |
| 16 | `references/16-context7.md` | Context7（upstash/context7，MIT，60.9K★）——实时库文档查询 / ctx7 技能管理 / MCP，§6 SDD·Engineering 的 docs 检索环节；pin @upstash/context7-mcp@4.0.2 |
| 19 | `references/19-token-scripts.md` | Token 脚本化流水线——9 脚本全实现：probe-tools / verify-runner / bump-version（P0）· golden-run / error-sig / case-search（P1）· env-snapshot / review-prefilter / token-meter（P2）；§3 G-gates 落地 |
| 17 | `references/17-agent-doctor.md` | Agent Doctor 架构（AI Ops 控制平面，本地文档指针）——状态化路由/验证五态/风险分层的设计依据；吸收映射与排除项（§4/§5.6/§10.9 来源） |
| 18 | `references/18-debug-diagnosis.md` | Debug 诊断协议——确定性先行清单 → 假设-证据-实验环 → 验证五态判定 → 问题案例库（§1 Debug / §5.6 落地细则） |

---

## 10. Git Management — version-control discipline (details: ref-07)

> Applies to EVERY coding session. The SDK itself lives in `~/.workbuddy/skills/` (a git repo) — every skill edit is a commit.

**Hard rules (user standing conventions, non-negotiable):**
1. **Local commit = default.** Commit at every logical unit (feature done, bug fixed, refactor complete, review feedback landed, session end). Never leave a session with uncommitted work.
2. **git push = ask FIRST, always.** ANY push (`git push` / `gh pr create`) stops and asks the user explicitly: what will be pushed, to which remote/branch, and what deploy side-effects follow (CI, Cloudflare/Vercel auto-deploy quota). No push without confirmation.
3. **One logical change per commit.** No mixed fix+refactor commits (breaks rollback).
4. **Conventional Commits**: `type(scope): summary` — types `feat/fix/refactor/docs/chore/test/perf`; scope = module; Chinese summary OK; no emoji.
5. **Branch policy**: `main` = stable-only; features → `feature/<name>`; hotfixes → `fix/<name>`; isolation via git worktree; small tasks commit straight to main.
6. **Mode → git action** (recipes in ref-07 §3): Vibe → throwaway branch/worktree, commit milestones; Engineering/SDD → ticket-granular commits on feature branch, verify then merge; Debug → one bug = one `fix:` commit; Review → landed feedback = one `refactor:`/`fix:` commit after verification.
7. **Rollback safety**: prefer `git revert` for shared history; `git reset --soft` only for unpushed local commits; `stash` WIP; never force-delete / `--hard` without user confirmation (recipes: ref-07 §4).
8. **Skill self-versioning**: every skill change bumps version + CHANGELOG.md 顶部条目 (aligns §8 dated pinning); commit each edit (`chore(skill): bump vX.Y.Z`). **Bump 脚本化**：`python scripts/bump-version.py vX.Y.Z --apply --commit`（ref-19，改 SKILL/README 版本串 + CHANGELOG 日期头 + 本地提交，永不 push）。
9. **Risk-tier gate (ref-17)**: every action beyond read-only diagnosis is risk-tiered — 0 read-only (no gate) / 1 safe reversible (no gate) / 2 controlled modification (automatic if confident + verification plan) / 3 destructive (needs independent cross-check + rollback tested) / 4 irreversible-or-credentials (ALWAYS human approval, structurally required — push-gate in rule 2 is tier-4). `can_act = risk_level ≤ ceiling AND confidence ≥ threshold AND rollback validated`.

---

## Rules (non-negotiable)

1. **THINK IN ENGLISH** — thinking chain is English skeleton-fill (⛔ LANGUAGE RULES banner, top of file), never free-form CN self-talk; final output language follows the user (CN by default). Zero CJK in thinking; first token must be `[GOAL]`'s `[`.
2. **No code before plan** — EXCEPT Vibe mode.
3. **No completion without verification** — §5.3 self-check + `verification-before-completion`.
4. **Default thinking OFF** — enable per tier, not by habit.
5. **Least-token principle** — static tool routing, lazy skill load, progressive disclosure, minimal context.
6. **Stable prefix first** — cacheable content in front, volatile last.
7. **Env conventions** — Python deps via uv; git discipline per §10 (local commit default, push needs explicit confirmation); final replies in Chinese.
8. **Model/version changes go through golden-set regression** before adoption.
