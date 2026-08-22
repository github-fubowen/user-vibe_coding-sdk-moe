# Ref-06 · Token Budget — measurement, caps, cost accounting

> Load when computing max_tokens, setting thinking budgets, or doing a billing checkup.
> Source basis: LLM DIY Tuning Handbook (§4, §7) + CN MoE Handbook (§4.3, §11.3).

---

## 1. The max_tokens trap (read first)

Thinking tokens COUNT toward output quota on most MoE APIs. If `max_tokens` is too small:
- The thinking phase eats the whole budget → the real answer gets **hard-truncated** mid-sentence.
- You receive a "half-thought" artifact and blame the model.

**Procedure** (always):
1. Run the task once with a generous cap.
2. Measure the ACTUAL distribution: `think_tokens` vs `answer_tokens` per task tier.
3. Set `max_tokens = typical_think + expected_answer × 1.5` (headroom factor 1.5).

---

## 2. Token measurement

| What | How |
|------|-----|
| Think tokens | API usage fields (`reasoning_tokens` / `completion_tokens_details`), or gateway logs |
| Cache hit | DeepSeek context-cache fields / vendor dashboard / litellm usage |
| Rough CN estimate | ~1.5 CJK chars per token (tokenizer-dependent — verify with a tokenizer tool for critical payloads) |
| EN estimate | ~1.3 tokens per word |

---

## 3. Thinking budget by tier (with measurement anchor)

| Tier | thinking | reasoning_effort | Headroom rule |
|------|----------|------------------|---------------|
| T0 reasoning/math | ON | high | generous; measure, then set cap |
| T1 code/debug | ON | medium | medium |
| T1 long writing | ON | low–medium | tight (prevent over-polish) |
| T2 extract/classify | OFF | 0 | 0 — explicit `/no_think` or param |
| T3 chat/streaming | OFF | 0 | 0 — latency |

**Overthinking alarm**: think-ratio > 70% AND flat pass rate → cut budget. (Overthinking also HURTS simple tasks — accuracy drops while cost ×5–20.)

---

## 4. Cost accounting formulas

```
single_task_cost =
    in_tokens × in_price × (1 − hit_ratio × discount)      # cache-adjusted input
  + out_tokens × out_price
  + think_tokens × think_price

daily_cost = Σ over models: (calls × avg_task_cost)
```

**Billing checkup order** (per CN MoE Handbook §11.3):
1. **Cache hit rate** < 60% → fix prefixes first (biggest, cheapest lever).
2. **Think-token ratio** > 70% without accuracy gain → cut thinking budget.
3. **T0 usage share** > 30% of calls → demote tasks to cheaper tiers.
4. Only THEN consider switching providers.

---

## 5. The six gates (from SKILL.md §3) — enforcement checklist

| Gate | Verify | Fails when |
|------|--------|------------|
| G1 Context minimalism | Only task-relevant context loaded | "Full repo" reads, whole-skill bulk loads |
| G2 Progressive disclosure | Only needed references loaded | Loading all 6 refs upfront |
| G3 Static tool routing | Mode→toolset mapped once, no re-listing | Re-enumerating tools per call |
| G4 max_tokens headroom | Set from measured distribution ×1.5 | Guessing a cap; truncation visible |
| G5 Stable prefix | Cacheable content first, volatile last | Timestamps/IDs front; unversioned docs |
| G6 Cheap-model offload | T2/T3 → Flash/local; T0/T1 → flagship | Bulk work on flagship |

---

## 6. Efficiency techniques (ranked by ROI)

1. **Stable-prefix caching** — near-free money; hits ≈ 1/10 price (ref-04).
2. **Thinking OFF on T2/T3** — kills 5–20× waste AND raises simple-task accuracy.
3. **Structured EN skeleton CoT** — −30–60% thinking tokens at equal/better quality (ref-01).
4. **Task demotion** — 60% of token volume is usually T2-class; offload it.
5. **Retrieval over injection** — for pools that don't fit or repeat rarely: inject top-k, not everything.
6. **Idempotent local caching** — embeddings, classifications: same input → same result, store locally, zero cost on repeat.
7. **Session reuse (KV cache)** — keep conversations alive for follow-ups.

---

## 7. Degradation & resilience (cheap tiers)

- Free/cheap tiers: 2–10 QPS typical → queue + exponential backoff + jitter.
- Timeouts mandatory; auto-failover to backup model on repeated failure.
- Track time-of-day quality variance (CN providers occasionally throttle peaks) — route bulk work off-peak.

---

## 8. Appendix — tuning experiment log template

```markdown
## Task family: {classify/code/agent...} tuning round {N}

### Changes
- date / change (one variable): {model version / prefix / think budget / temperature}
- models & dated IDs:

### Golden-set results (20–50 CN samples)

| Metric | Old config | New config | Δ |
|--------|-----------|-----------|-----|
| Pass rate |  |  |  |
| Avg output tokens |  |  |  |
| Avg think tokens |  |  |  |
| Think ratio |  |  |  |
| Cache hit rate |  |  |  |
| Cost / task (¥) |  |  |  |

### Failure-mode shift
- old top3: {type: count}
- new top3: {type: count}

### Verdict & next
- verdict: {keep / rollback / keep tuning} — {one-line reason}
- next: {change ONE variable on the most concentrated failure family}
```
