# Ref-01 · English Thinking Protocols — deep dive

> Load when you need CoT variants, English-thinking tuning, or anti-rambling techniques beyond the SDK skeleton (§2).
> Source basis: LLM DIY Tuning Handbook (§1, §2, §8) + CN MoE Handbook (§4).

---

## 1. Why English CoT works on MoE models (the mechanism)

| Claim | Evidence | DIY lever |
|-------|----------|-----------|
| English reasoning tokens are denser | 1 EN word ≈ 1.3 tokens; 1 CJK char ≈ 1–2 tokens, and EN structured markers (`GOAL→` etc.) are near-free | Use EN skeleton markers, not CN phrases, inside thinking |
| Reasoning models were trained EN-first | o1/R1-era long-CoT corpora are dominated by English math/code/solution traces | EN CoT tracks the model's strongest reasoning manifold |
| Structured thinking beats rambling | Community + DIY experiments: skeleton CoT cuts thinking tokens 30–60% at equal or better accuracy | Skeleton fill (§2 of SKILL.md) is mandatory, free-form self-talk is banned |
| MoE routing is NOT phrase-controllable | Router is token-level; "Let me" vs "We need" is a decoding/attention effect, not expert selection | Never tune prompts for "expert activation" — tune for thinking *structure* |

**The one lever you actually own**: the *shape* of the thinking chain (structure, length, markers), set by instructions + few-shot + sampling. Not the experts.

---

## 2. Three injection types — ranked by proven strength

| Type | Example | Strength | When |
|------|---------|----------|------|
| **Literal prefix** | "Start every thought with 'We need to'" | Weak — model mimics surface, wastes tokens acting | Never use |
| **Protocol prefix** | "Think in order: state GOAL → list CONSTRAINTS → derive stepwise → verify" | Strong — changes thinking *structure* | Default |
| **Skeleton prefix** | "Fill this template:\n[GOAL]\n[CONSTRAINTS]\n[PLAN]\n[EXECUTE]\n[VERIFY]" | Strongest — gives a fillable scaffold, best CoT control | Default for complex tasks |
| **Closing prefix** | "Before final answer, check: ① computation ② logic ③ facts ④ format" | Strong — fixes verification into the flow | Always append |

Placement (attention peaks — first & last positions):
- Global rules → end of system prompt (right after the opening peak zone).
- This-task rules → start of user message.
- Verification → at the output template's tail, as a pre-submit gate.

---

## 3. Thinking protocol full template (EN, system-prompt ready)

```text
# THINKING PROTOCOL (internal only — never printed)
Before answering any non-trivial request, fill this skeleton IN ENGLISH:

[GOAL]        One-sentence restatement of the objective. What must be true at the end?
[CONSTRAINTS] Bullet list of hard constraints: inputs, forbidden moves, format, boundaries.
[PLAN]        Numbered steps. Each step does ONE thing. No premature conclusions.
[EXECUTE]     Work the steps. Use tools where precision beats guessing.
[VERIFY]      Recheck: every step vs every constraint. Recompute arithmetic.
              On contradiction → backtrack to PLAN. Never plow forward.

Banned inside thinking:
- Self-talk ("Let me think...", "Hmm...") — fill the skeleton, don't narrate.
- Repeating the same approach twice — dead-end → switch strategy, state why.
- Translating the skeleton to Chinese — English markers only.
```

For CN MoE models, the protocol above works verbatim (they obey EN structural instruction well); the final *deliverable* language still follows the user.

---

## 4. Few-shot: teach structure by demonstration

One or two high-quality examples teach *structure*, not content:

```
User: A 300m train passes a 900m tunnel at 72 km/h. How many seconds?
Think:
[GOAL] Time for the train to fully clear the tunnel.
[CONSTRAINTS] "Fully clear" = nose enters until tail exits → distance = 300+900 = 1200 m.
[PLAN] 1) km/h → m/s; 2) t = distance / speed.
[EXECUTE] 72 km/h = 20 m/s. t = 1200 / 20 = 60 s.
[VERIFY] Units (s) consistent; logic complete. → 60 seconds.
```

Few-shot is a *thinking* demo, not an output demo — keep the final answer minimal.

---

## 5. Thinking budget by tier (control knobs per API)

| Tier | `reasoning_effort` / thinking switch | Thinking-token headroom | Pitfall |
|------|--------------------------------------|-------------------------|---------|
| T0 reasoning/math | high | generous; measure first | thinking eats max_tokens → truncation |
| T1 code/debug | medium | medium | overthinking on easy bugs |
| T1 long writing | low–medium | tight | over-polish loops |
| T2 extract/classify | OFF (`/no_think` or param) | 0 | thinking drops accuracy AND multiplies cost 5–20× |
| T3 chat/streaming | OFF | 0 | latency |

**Overthinking diagnostic**: think-token ratio = think / (think+answer). >70% with flat accuracy → cut budget. (Full formula in ref-06.)

---

## 6. Anti-rambling techniques (CN MoE special)

- CN models trained on Q&A corpora tend to open with "好的！""让我们一起来…" and close with "希望这个回答对你有帮助". Suppress via output spec (SKILL.md §5.1), NOT by arguing about personhood.
- Strip thinking artifacts from final output — reasoning must never leak.
- If a model still rambles after the output spec: lower temperature (0.2 → 0), and/or tighten the output template with a hard character/point limit.
- Verify: the "let me vs we need" debate is falsifiable — run the A/B in ref-05 §4 if you want your own data.

---

## 7. Quick reference — the 5-line English CoT

```
GOAL → CONSTRAINTS → PLAN → EXECUTE → VERIFY
(one step per line, EN markers, no narration, verify before output)
```

---

## 8. Failure mode: CN thinking leak — root cause & hardening (v1.0.1)

**Observed symptom** (2026-08-16): the first deep-thought and later thinking blocks came out in Chinese even though the SDK mandates English CoT — e.g. a chain opening with `用户要求使用该技能…让我先加载这个技能` instead of `[GOAL] …`.

**Root causes, ranked by contribution**:

| # | Cause | Mechanism |
|---|-------|-----------|
| 1 | **Language mirror trap** | CN MoE models mirror the user's input language inside their own reasoning. Chinese user input + Chinese priming in the prompt → Chinese thinking chain. The SDK's EN mandate was buried mid-file (§2), *after* CN-heavy sections (v1.0 diff note, §1 triggers, §5.1 CN output spec) — CN priming won by position. |
| 2 | **No first-token hook** | "THINK IN ENGLISH" is a soft instruction. Without a mechanically checkable anchor (`first token must be `[``), the model opens in whatever language the preceding context primes. |
| 3 | **No verification gate for language** | §5.3 checked math/constraints/format/citations but never scanned the thinking block for CJK — so a CN chain passed the pre-submit gate silently. |
| 4 | **"Thinking is invisible" contradiction** | WorkBuddy renders deep-thought to the user. The SDK claimed thinking stays invisible, so the model relaxed discipline (nobody sees it → no cost). Once thinking is user-visible, language rules must match output strictness. |

**Hardening applied (v1.0.1)** — every counter-measure targets a specific cause:

| Counter-measure | Kills cause | Where |
|-----------------|-------------|-------|
| ⛔ LANGUAGE RULES banner moved to the VERY TOP of SKILL.md, before any CN text | #1 (priming by position) | SKILL.md top |
| Explicit "independence rule": output = user language, thinking = ALWAYS English (two channels) | #1 (mirror trap) | banner + §2 |
| First-token hook: every thinking block MUST open with `[` (`[GOAL]`); CN opener = restart | #2 | banner + §2.1 |
| ZERO-CJK rule in skeleton rules + banned/OK pairs (❌中文开场 → ✅[GOAL]…) | #1, #2 | banner + §2.1 |
| §5.3 adds `□ Thinking language: scan for CJK — zero CN tokens allowed` | #3 | §5.3 |
| "Visible thinking" note: WorkBuddy shows the chain → same strictness as output | #4 | banner + §2 |

**Self-test before adopting any further prompt tweak**: reproduce with a CN user message (`请帮我写一个…`) and confirm the *first* thinking token is `[`. If it is not, the fix is a placement/priming problem, not a wording problem — move the EN mandate earlier and strip CN text from the head of the prompt.
