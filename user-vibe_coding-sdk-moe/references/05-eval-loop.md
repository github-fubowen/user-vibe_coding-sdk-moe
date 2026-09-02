# Ref-05 · Eval Loop — golden sets, metrics, A/B, regression

> Load when building golden sets, running A/B experiments, LLM-as-judge, or regression before model/prompt changes.
> Source basis: LLM DIY Tuning Handbook (§7, §8) + CN MoE Handbook (§8) + GitHub survey (deepeval/opencompass).

---

## 1. Golden set (CN-first) — the standard

- **Size**: 20–50 samples covering five families: CN QA · code · long-text analysis · extraction/structured output · tool-use.
- **Each sample**: {input, expected output / acceptance points, difficulty, task type}.
- **Usage**: full regression on ANY change — model version, system prompt, params, skill, tool protocol.
- **Failure-mode logging**: categorize failures (hallucination / format / logic / missing constraint / overthinking) — improvement direction comes from the failure histogram, not vibes.

---

## 2. Metrics — what to track

| Metric | Meaning | Compute | Watch for |
|--------|---------|---------|-----------|
| **Pass rate** | Primary | passed / total | Main signal |
| **Token efficiency** | Quality per token | (out+think tokens) / passed | The number DIY players should track — lower is better |
| **First-pass rate** | No-retry success | first-round passes / total | Harness quality |
| **Format compliance** | Machine-parseable output | parseable / total | Structured-output health |
| **Think-token ratio** | Thinking share | think / (think+answer) | >70% + flat accuracy = overthinking → cut budget |
| **Cache hit rate** | Prefix quality | hit tokens / input tokens | <60% = prefix construction broken (ref-04) |
| **Cost per task** | Final metric | ¥ / task | The landing point of all optimization |

---

## 3. LLM-as-judge — correct posture

- Use a **stronger/different** model as judge (avoid self-judging bias).
- Give the judge a **rubric**, not an open "score it".
- Judge and answerer use **different system prompts** (reduce style coupling).
- Blind the judge: strip model names / prompt-version markers (prevents name bias).
- Spot-check judge scores manually — judges err too.
- Tools: deepeval (17.6k⭐, assertion-style + judge) for automation; opencompass (7.3k⭐, Shanghai AI Lab) for CN-model cross-comparison.

---

## 4. A/B experiment design (one variable at a time)

Canonical template (falsifiable — e.g. "protocol prefix beats literal prefix"):

| Group | System-prompt variant | Fixed conditions |
|-------|----------------------|------------------|
| A baseline | No thinking protocol | same model, temp 0, same max_tokens, same seed |
| B literal | "Start thoughts with 'We need to'" | same |
| C protocol | SKILL.md §2.1 protocol | same |
| D skeleton | Fill-in skeleton (ref-01 §2) | same |

Steps: 20 tasks of varied difficulty → run all four with fixed seed → record per-question correctness, think tokens, total tokens → compute pass rate, avg tokens, token efficiency → conclude (C/D usually ≥ A accuracy AND ≤ A tokens; B usually ≈ A — mechanism is in *structure*, not phrasing).

**Expected outcomes** (from DIY handbook §8.1): C/D gain +5–15% accuracy on hard tasks, −30–50% thinking tokens. Verify with YOUR data.

---

## 5. Other experiments worth running

| Experiment | Design | Output |
|------------|--------|--------|
| Thinking-budget sweep | Same tasks × reasoning_effort low/medium/high | Find the "profit inflection" per task family → budget table |
| Temperature sweep | temp 0/0.3/0.7/1.0 × 5 runs (seed family) | Mean + variance; high variance → needs low temp or voting |
| Model comparison | New vs old, same prompt/params, same golden set | "Quality per yuan", not "who's smarter" |
| Version drift | Same model name, monthly re-run | Detect silent behavior change (pin dated IDs!) |

---

## 6. Regression workflow (before every production change)

```
1. Freeze golden set (versioned file, e.g. golden-set-v3.json)
2. Baseline run → record pass rate + token efficiency + cost/task
3. Apply change (ONE variable)
4. Re-run → diff against baseline
5. Decision rules:
   - pass rate drop ≤ 2% on cheaper model → demote OK
   - pass rate drop > 5% → revert
   - token efficiency better at equal pass rate → keep (free money)
6. Update experiment log (ref-06 Appendix template)
```

---

## 7. Logging — your DIY superpower

Minimal per-call record (JSONL/CSV):

```
time | task_type | model_id | prompt_version | temperature | thinking | in_tokens
| out_tokens | think_tokens | latency_ms | success | failure_mode
```

- 50+ records → statistics become meaningful.
- This log IS the evidence for every tuning decision — without it, tuning is superstition.
- Gateway logs (litellm/tensorzero/OmniRoute) can auto-fill most fields.

---

## 8. Appendix — experiment record template

```markdown
## Experiment {N}: {one-sentence hypothesis}
- date / model / temperature / thinking / seed:
- change (ONE): {which prompt part / param / model}
- dataset: {golden subset, N, difficulty mix}
- results:

| Group | Pass rate | Avg out tokens | Avg think tokens | Token efficiency | Notes |
|-------|-----------|----------------|------------------|------------------|-------|
| A baseline |  |  |  |  |  |
| B variant |  |  |  |  |  |

- failure-mode shift: {A→B failure type migration}
- conclusion: {confirmed / falsified / inconclusive} — {one line}
- next: {fix the most concentrated failure family, change one variable, re-run}
```
