---
name: user-vibe_coding-sdk-moe
description: >
  MoE-optimized coding skill SDK (v2.10.6). USE when the user starts a coding session,
  says "start coding" / "coding mode" / "vibe coding" / "开发模式" / "写代码" /
  or asks to begin any write/debug/review/refactor task. Maximizes Mixture-of-Experts
  model output quality via MANDATORY ENGLISH COT (thinking chain), per-task thinking
  budget control, model routing matrix, stable-prefix caching, and token-budget
  gates — while cutting token consumption 30-60% vs default prompting.
  Route to the right path: Vibe / Engineering / SDD / Debug / Review / Quick-Edit.
---

# user-vibe_coding-sdk-moe v2.10.6 — MoE-Optimized Coding SDK

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
- Path E SDD (local loop): `to-spec → to-tickets → implement → triage(可选)` — spec-kit 集成见 ref-08（`specify` CLI；非 TTY 环境 init 必须 `--script ps|sh`）；**tickets → 状态机**走 `scripts/spec-tasks-import.py`（tasks.md `- [ ]` → task-state.v1，P0-P3 + acceptance 落位）；任务状态外置见 ref-20，上下文检索见 ref-21，修复升级阶梯见 ref-22。
- **远程 CI 选择行（v2.6.0 C2-2/C2-3）**：需要远程 CI 时**只选择** `.github/reusable/{python-ci,node-ci,docker-build}.yml`（Agent 不生成 ad-hoc job 体）；控制面走 `workflow_dispatch` 三输入 `operation/version/agent_run_id`（`agent_run_id` 串接 `task-state.py transition --run-id`）；结构合规用 `scripts/gh-workflow-check.py` 校验。
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
| **G2 Progressive disclosure** | This SKILL.md is the entry (~37KB, 实测 2026-09-02 = 38,375B). Load `references/*` only when a section is needed — NEVER the whole set. |
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
- **bandit 建议接线（v2.4.0, ref-23）**: 有历史数据时，路由前先 `scripts/router-stats.py recommend --db scripts/data/router-stats.db --cell <task_cell>` 取 Thompson 排名作**建议**，与 §4 静态矩阵 + §10.9 硬过滤合并为最终选择；bandit 仅为建议，硬过滤与最终裁决留 agent（评估报告 P2-2）。

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

Debug 模式细则（确定性先行清单、假设 schema、案例库格式）见 ref-18。验证步骤用确定性闸：`scripts/verify-runner.py --config <preset>.json --json`（ref-19）——**随包预设** `scripts/presets/verify.{python,node,docs}.json`（必带 `--cwd .`），脚本报 pass/fail 事实，五态判定留在 agent。状态机落地：五态判定后经 `scripts/task-state.py transition` 写任务状态（ref-20）；修复升级阶梯 L0-L5、熔断与 L5 人类终态见 ref-22。

**三条已脚本化的硬闸（v2.7.0，此前只有协议文本）**：

| 闸 | 命令 | 触发即拒绝 |
|---|---|---|
| 修复预算 `max_repair_attempts=3` | `task-state.py transition`（进入 REPAIR/REPAIRING 时自动判定） | 第 4 次修复 → exit 2，唯一合法出口 `ESCALATED`（`--max-repair` 可调，0=不限） |
| 振荡检测 | 同上 | 同一 `(from,to)` 转移 > 3 次 → exit 2（`--allow-loop` 显式放行） |
| Diff Risk Scoring | `scripts/diff-risk.py --diff-file p.patch --known-failures ... --error-class ...` | `score > 0.7` → exit 2，人工审核，agent 不得自行放行（ref-22 §8） |

另有 **DAG 依赖闸**：`depends_on` 未完成（非 DONE）时禁止进入 `IMPLEMENT`；**崩溃恢复**：`task-state.py checkpoint` / `resume`（WAITING/CRASHED 均为可恢复非终态）。CI 失败日志用 `scripts/ci-fail-analyze.py` 解析为 diagnostic.v1（C1-4，v2.8.0 增 permission/dependency/assertion 类）喂 ref-18 环。**origin class（v2.9.0 T-19）**：diagnostic 增 `origin`（code/test/dependency/infra/environment/flaky/unknown）+ `recommended_action`（infra→RETRY · test→REPAIR_TEST · unknown→DIAGNOSE…）——**由 origin 而非 leaf 决定下一步动作**（防"一切皆代码缺陷"误修）。**flaky 前置判别（v2.9.0 T-20）**：`scripts/flaky-check.py --runs 5 --cmd <测试命令>`——单次失败绝不直接修代码；混合结果且 N≥5 → FLAKY → QUARANTINE（永不删除）；Stage 5-8 失败先过它再进修复环。**回归测试双向闸（v2.9.0 T-21）**：`scripts/regression-guard.py --base <修复前ref> --test <命令>`——base 必须 FAIL、head 必须 PASS，两边都过 = 自证式弱测试 exit 2。**测试选择（v2.9.0 T-22）**：`verify-runner --changed <files>` 按约定映射注入 test-targeted 层（无映射 fail-open）——修复循环只跑受影响测试。**补丁规模预算（v2.10.0 T-23）**：`scripts/patch-gate.py --numstat-file n.txt`（kernel §I：files≤5 / lines≤300 / 依赖清单≤1）超限 exit 2 → ESCALATED——diff-risk 是评分不是预算闸；`diff-risk --verify-confidence` 合成 `repair_confidence`（<0.7 强制人工，B.21）。**动作预执行门（v2.10.0 T-25）**：`scripts/action-gate.py --tool <name>`——toolstack 存在性/风险分级/args 校验，tier≥4 须 `--user-approved`（先问用户）。**v2.10.1 修正**：查表范围含 `sdk_tools` + `local_tools` 两张表（原仅查 `local_tools`，22 个自有脚本全部被误判 DENY），并支持 stem 匹配（`diff-risk` ≡ `diff-risk.py`）；`git-push` 以 tier-4 登记，push 闸门有落点。**升级即出包（v2.10.0 T-24）**：`task-state.py escalation-pack --task <id>` 七字段高信号包，ref-22 L5 必附。**幂等键（v2.10.0 T-26）**：`task-state transition --idempotency-key <k>` 同键同目标重放 = no-op 不耗预算，同键换目标 exit 2。**版本串与 CHANGELOG 顺序闸（v2.8.2 T-16）**：`scripts/version-check.py --json` —— SKILL frontmatter / SKILL 标题 / README blurb / README 版本行 / CHANGELOG 首个条目五处一致 + 条目严格递减无重复，失配即 exit 2，已置为 ci-smoke 第 0 步（cheapest-first；F-26 盲区闭合：此前红灯只能靠 workspace 侧 audit 发现）。**自适应验证深度（v2.8.0 T-07）**：`verify-runner.py --confidence <0-1>`（<0.4 全层 / 0.4-0.7 语法+类型+目标测试 / >0.7 语法+目标测试；`--layers` 显式声明优先；层名走显式别名匹配表，T-18）。**security 层恒保（v2.8.2 T-17）**：任何档位都不得剔除安全扫描层（verification-kernel Stage 9 属硬闸；F-27 曾让高置信补丁静默跳过 pip-audit / npm audit）。**完成条件闸（T-08）**：`task-state.py init --done-when` + FINALIZE→DONE 必须附 `--done-evidence`；transition 同步追加 `events.jsonl` 事件台账（T-10，trace-export 读流）。

### 5.7 编辑协议（Edit Protocol — v2.7.0 新增，harness §21）

编辑原语的选择直接决定 diff 规模与 token 成本，**默认序不可颠倒**：

```text
Search/Replace  ──▶  Unified Diff / Patch  ──▶  whole-file rewrite
   （首选）              （多块/跨文件时）          （最后手段，须说明）
```

- **不要默认 whole-file rewrite**：它会让 diff 风险评分（§5.6）与 review 成本同步上升，且丢失局部意图。
- 大文件先 `grep`/图谱定位，再走 Search/Replace；单次编辑跨越 > 5 处时改用 Unified Diff。
- 编辑失败降级阶梯：Search/Replace 命中 0 → 重新定位（换更短的唯一锚点）→ 改 Unified Diff → 最后才 whole-file rewrite。
- 改完即走确定性闸：`verify-runner --config scripts/presets/verify.*.json --cwd .`，再 `diff-risk.py` 定风险档位。

---

## 6. Tool Routing — mode → toolset (static map)

| Mode | Tools (priority order) | Purpose | Probe |
|------|------------------------|---------|-------|
| **Review** | `review-prefilter.py`（ref-19, 差异统计+静态检查→精简关注包）→ `diff-risk.py`（ref-22 §8 风险分档，>0.7 人工）→ `ocr` CLI → code-review-graph MCP (get_review_context/get_impact_radius) → graphify MCP (query_graph) → `gh` CLI → `strix` (ref-13, 授权安全审计) | line-level review + 风险分档 + blast radius + graph + PR data + PoC 漏洞验证 | `probe-tools.py --json` / MCP registered? / `strix --version` |
| **Debug** | code-review-graph MCP (debug-issue) → graphify MCP (query_graph) → codebase-memory-mcp (trace_path) | graph navigation + feedback loop | same |
| **Engineering** | codebase-memory-mcp (search_graph/trace_path) → code-review-graph (refactor_tool) → graphify (query_graph) → find-docs · `cli-hub` (ref-09, 真实软件 Agent 化) | retrieve/trace + safe refactor + understand + docs · 驱动桌面软件 | same · `cli-hub --version` |
| **SDD** | `specify` CLI (ref-08) → find-docs / context7-cli (ref-16) → codebase-memory-mcp (search_graph) → `task-state.py` (ref-20) → `gh-workflow-check.py` (C2-3) | spec-kit SDD pipeline + docs + retrieval + 任务状态外置 + CI 控制面合规 | `uv tool run --from specify-cli specify --version` |
| **Vibe** | graphify (light codebase understanding) · ui-ux-pro-max (ref-11, 离线 UI/UX 设计智能) | prototype cheap · UI/UX 设计依据 | same |
| **Execution Plane**（Engineering/SDD 开工前） | `task-workspace.py` create/verify（per-task worktree 隔离）→ `task-state.py init --depends-on ...`（DAG 依赖）→ `task-state.py checkpoint` / `resume`（崩溃恢复） | 多任务隔离 + 依赖编排 + 长会话可恢复 | `task-workspace.py status --dir <ws>` |
| **Quick Edit** | none (task too small) | fix → verify（走 §5.7 编辑协议） | skip |

Probe rules: **once per session via `scripts/probe-tools.py --json`**（ref-19 单次调用探全部，替代逐个 `--version`）; unavailable → next in chain, never block; report degradation in final summary. **Minimal-need principle**: graph query > grep > full-file read.

**维护（工具栈巡检）**：`python scripts/toolstack-pipeline.py --update --commit`（ref-15）——六阶段 probe→diff→report→update→commit→push-gate；`--push` 需交互 TTY 显式确认。建议每月一次（§8 version-drift re-run 落地）。

**静态自检（v2.10.1 / v2.10.2 补强）**：`scripts/selfcheck-static.py`——frontmatter / references 完整性 / 脚本存在性 / **toolstack 一致性（含"脚本存在但未登记"双向校验）** 四项，秒级、零 LLM，exit 2 = 结构破损；已置为 ci-smoke 第 2 步（`--quiet`）与 **pre-commit 第 4 闸**（任何 SDK 改动即跑，漏登记在提交时刻就被拒）。**`sdk_tools` 曾有零自动化**（toolstack-pipeline 只管 `refs`/`provider_health`）——v2.10.2 起 `toolstack-pipeline` 新增 Stage 3b 差集扫描（`--update` 自动登记、仅增不删），本脚本仍是提交时刻的唯一硬闸。

**自动化门禁（v2.4.0, ref-23）**：`scripts/install-hooks.py` 安装 pre-commit 钩子（改 SDK 脚本 → robustness `--only` 子集 + 新文件 → privacy-scan，fail-closed）；`scripts/ci-smoke.py` 定时冒烟（全量 robustness + golden 校验/离线 + privacy，`--report` 存档）；**新 clone / 换机后先 `python scripts/install-hooks.py`**，否则按 §10 规则 10 人工兜底。

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
- 动态检索协议（检索顺序 / 按类预算 / 排除清单 / 压缩时机）见 ref-21 —— 本节管静态前缀，ref-21 管动态检索，合并为完整上下文流水线。

---

## 8. Evaluation & Version Drift — close the loop (ref-05)

- **Golden set**: 20–50 CN-first samples covering QA/code/long-text/extraction/tool-use, each with acceptance points. Full regression on ANY change (prompt/model/params/skill).
- **Metrics**: pass rate · **token efficiency** (out+think tokens / passed — the number to watch) · think-token ratio (>70% without accuracy gain = overthinking) · **cache hit rate** (<60% = prefix construction broken) · cost/task · version drift (monthly re-run).
- **Version pinning**: dated IDs in production (`deepseek-v4-pro-0813`), never semantic aliases. A/B on golden set before switching.
- **全面自检（一个命令）**：`python scripts/ci-smoke.py --json` —— 7 步 cheapest-first：version-check → selfcheck-static（静态结构）→ robustness 全量 → golden v2/v3 validate → v3 离线回归 → privacy；零 LLM，exit 0/2，`--report <file>` 存档。**改了 SDK 任何文件就跑它**（v2.10.1：只看单点绿灯不够——F-42 曾让 22 个自有脚本的动作门失效而全套门禁仍全绿）。

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
| 20 | `references/20-task-state-machine.md` | 任务状态机 + 黑板协议（吸收 coding-agent-os §10-11/§28.4）：状态外置/转移表/五态映射/黑板规则/多代理单代理默认；脚本 task-state.py |
| 21 | `references/21-context-engineering.md` | 上下文工程检索协议（吸收 §7/§16）：检索 6 步/按类预算 A-B-C/排除清单/压缩时机；SKILL §7 的动态层 |
| 22 | `references/22-repair-escalation.md` | 修复升级阶梯 L0-L5（吸收 §6.6/§13/§28.8）：重试预算/失败类感知/熔断/L5 人类一等终态；§7 修复总预算 max_repair_attempts=3、§8 Diff Risk Scoring（C1-5）；与 ref-18 合并关系 |
| 23 | `references/23-pipeline-automation.md` | 流水线自动化与门禁（评估报告落地）：pre-commit 门禁（git-pre-commit.py + install-hooks.py）/ ci-smoke 定时冒烟 / 月检+周度调度自动化 / bandit recommend 接线 |
| 24 | `references/24-gh-security.md` | 远程执行引擎（GH Actions）安全设计（GH 方案 §2/§3/§16，C1-6）：installation token 最小权限表 + GITHUB_TOKEN 优先 + OIDC 指针 + Tool Layer 抽象（Agent 不拼 API） |
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
8. **Skill self-versioning**: every skill change bumps version + CHANGELOG.md 顶部条目 (aligns §8 dated pinning); commit each edit (`chore(skill): bump vX.Y.Z`). **Bump 脚本化**：`python scripts/bump-version.py vX.Y.Z --apply --commit`（ref-19，改 SKILL/README 版本串 + CHANGELOG 日期头 + 本地提交，永不 push）。**豁免边界（v2.7.1）**：`data:`/`chore:` 且无行为变更可不 bump（但 CHANGELOG 月度合并记录一条）；**`fix:`/`feat:` 必须记录并 bump**（patch 号即可）——CHANGELOG 断链会让下轮自查无法追溯门禁用例与行为变更。
9. **Risk-tier gate (ref-17)**: every action beyond read-only diagnosis is risk-tiered — 0 read-only (no gate) / 1 safe reversible (no gate) / 2 controlled modification (automatic if confident + verification plan) / 3 destructive (needs independent cross-check + rollback tested) / 4 irreversible-or-credentials (ALWAYS human approval, structurally required — push-gate in rule 2 is tier-4). `can_act = risk_level ≤ ceiling AND confidence ≥ threshold AND rollback validated`. 动作分类示例（吸收 coding-agent-os §17）：低危（读/检索/临时文件）→0-1 级；中危（改代码/写数据/本地安装）→2 级；高危（删数据/改全局配置/网络外发）→3 级（交叉核对+回滚验证）；不可逆/凭据（push/凭据读写）→4 级（结构上强制人工）。toolstack.json 每工具带 `risk_tier` 字段供策略读取。
10. **Pre-commit gate (ref-23)**: installed via `scripts/install-hooks.py` — changed SDK scripts → robustness `--only` subset, staged new files → privacy-scan, **任何 SDK 改动 → `selfcheck-static`（v2.10.2 闸 4，~1s：未登记脚本 / 断链引用 / 版本结构破损）**, fail-closed (exit 1 blocks commit). 钩子缺失（新 clone/换机）时按 P0-2 纪律兜底：先跑 `scripts/robustness-suite.py --only <改动脚本>` + `scripts/privacy-scan.py . --user <本机用户名>` 再提交。

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
