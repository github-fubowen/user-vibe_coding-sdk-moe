# Ref-04 · Cache Strategy — stable prefixes, hit rules, pitfalls

> Load when designing prompts/contexts for cache-friendly calls, or debugging "why is my bill not dropping".
> Source basis: CN MoE Handbook (§3) + LLM Power-User Handbook (§7.2).

---

## 1. Cache hit — the hard rules (read before optimizing)

| Rule | Detail |
|------|--------|
| **Byte-identical prefix** | Hit detection is token-prefix based. One extra space, newline, character, or timestamp = MISS. |
| **Only stable prefixes hit** | Anything that changes per-call (user input, retrieved chunks, time) must sit AFTER the stable block. |
| **Discount applies to hit part only** | The changing tail still bills full price. |
| **Cache has TTL** | Unused prefixes expire (vendor-specific). Reuse patterns keep them warm. |
| **Volatile tail does not poison the prefix** | Everything before the first volatile byte can still hit if the prefix is unchanged. |

---

## 2. Canonical prefix layout

```text
[System prompt (role/rules/thinking protocol/output spec)]   ← FIXED, never changes
[Task instructions (invariant part)]                         ← FIXED
[Versioned material pool (docs/knowledge, injected on demand)] ← stable, versioned
------------------------------------------------------------------
[User input this turn]                                       ← VOLATILE, last
[Retrieved results this turn]                                ← VOLATILE, last
```

**80/20 split trick**: if ~20% of your material pool changes often, split it — stable 80% inside the cached prefix, volatile 20% after the separator. Maximizes hit surface.

---

## 3. Cache-hit self-diagnosis

Symptoms → causes:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Bill not dropping | Prefix broken by invisible diff (trailing space, CRLF vs LF, timestamp, random IDs, UUIDs in URLs) | Diff the two payloads byte-for-byte; freeze the prefix |
| Hit rate < 60% | Prefix too short / too volatile | Move more content left; version your docs |
| Sometimes hits, sometimes not | Alternating prompt layouts | Single canonical template per task family |
| TTL expiry on idle tasks | Long gaps between calls | Keep recurring jobs; accept re-warm cost |

**Where to check**: gateway logs (DeepSeek context-cache hit fields / litellm usage), or vendor dashboard. Track `cache_hit_tokens / input_tokens` per task family.

---

## 4. Cache × MoE specifics

- **DeepSeek** official context caching: hit ≈ 1/10 price (verify current rate). Long-context tasks (whole-doc analysis) get the biggest absolute savings.
- **SGLang RadixAttention** (self-hosted DeepSeek/Qwen): server-side prefix tree = local cache discount. Keep the same stable prefix convention even self-hosted.
- **KV cache** (multi-turn): don't restart conversations — reuse the session for related follow-ups.
- **Long-context caution**: one-shot long inputs are NOT cached (only repeated prefixes are). "Big document in, one answer out" pays full prefill — decide injection vs retrieval accordingly (§7 SKILL.md).

---

## 5. Material-pool versioning (cache + quality)

- Version your documents: `docs/v3.2/...` — changing a file breaks the prefix.
- Inject by reference for big pools: keep stable snippets in the prefix, fetch the rest via retrieval.
- Tag injected chunks: `<source src="docs/v3.2/glossary.md">` — citations + cache stability + provenance in one move.

---

## 6. Cost accounting with cache

```
effective_input_price = price × (hit_ratio × discount + (1 − hit_ratio))
task_cost = in_tokens × effective_input_price
          + out_tokens × out_price
          + think_tokens × think_price
```

**Checkup order** (per CN MoE Handbook §11.3):
1. Cache hit rate < 60% → fix prefixes FIRST (biggest lever).
2. Think-token ratio > 70% without accuracy gain → cut thinking budget.
3. T0-tier usage > 30% of calls → demote tasks to cheaper tiers.
4. Only then consider switching providers.

---

## 7. Anti-patterns

- ❌ Putting timestamps/random IDs at the front of the prompt.
- ❌ Regenerating the system prompt per session instead of keeping one canonical version.
- ❌ Re-pasting the same long doc every turn instead of relying on session KV cache.
- ❌ Cache-oblivious chunking: retrieved chunks change per query → they live AFTER the stable block, always.
- ❌ Assuming caching is automatic — on some providers you must opt in (check official docs).
