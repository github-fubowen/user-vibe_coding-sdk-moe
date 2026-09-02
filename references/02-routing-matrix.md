# Ref-02 · MoE Routing Matrix — model selection, sampling, tool protocols

> Load when choosing models, setting per-vendor sampling params, or bridging tool-protocol differences.
> Source basis: CN MoE Architecture Report (2026-08) + CN MoE Maximization Handbook (§1–§7, §9, §11).

---

## 1. Tier routing matrix (2026-08 snapshot — re-verify prices/params at official docs)

| Tier | Task profile | Primary | Alt | Thinking | temp | Notes |
|------|--------------|---------|-----|----------|------|-------|
| **T0** | Complex reasoning, code, agent brain, long-form writing, whole-doc analysis | DeepSeek V4 (1.6T/49B, 1M ctx, MLA+CSA/HCA) | Qwen3.5-Max (397B/17B, 1M, GQA); Kimi K2 (1.04T/32.6B, agent-native, MCP) | ON | 0.2 | V4 = cheapest long-context cost; Qwen = best think/no_think ergonomics |
| **T1** | Summarize, translate, structured extraction, routine writing | GLM-4.6 (400B/45B, ARC: agentic/reasoning/coding) | Doubao-1.5-pro (7× leverage, W4A8); MiniMax M2 (229.9B/9.8B, full-attention, 192K) | OFF–medium | 0.2–0.3 | MiniMax M2 shines on complex multi-hop; weak on trivial |
| **T2** | Classification, tags, formatting, simple QA, chat | DeepSeek V4-Flash (284B/13B, high-concurrency) | Qwen3 series; Doubao light tier | OFF | 0 (extract) / 0.7 (chat) | Cheap enough to "use liberally, not sparingly" |
| **T3** | Private data, batch embedding, offline, free | Local Qwen3-30B-A3B (3B active) | Local MiniLM embedding (384d) | — | 0 | 16GB RAM: only small-MoE (total params ≤ RAM) or dense small |
| **T4** | Edge / end-cloud | Step-3.5 Flash (1960B/110B, 350 tok/s) | Qwen3-30B-A3B | — | — | 端云协同: edge understands, cloud decides |

**Dated-ID rule**: production uses `deepseek-v4-pro-0813` style IDs, never `deepseek-chat` semantic aliases (CN models iterate weekly; same name = possibly different model).

---

## 2. Sampling parameters by vendor (ALWAYS check official docs — CN vendors diverge)

| Param | DeepSeek | Qwen | Kimi | Recommendation |
|-------|----------|------|------|----------------|
| `temperature` | wide range (historical 0–2) | varies | varies | Reasoning 0–0.3; creative 0.7–1.2 |
| `top_p` | use OR temperature, not both | same | same | Keep default |
| `max_tokens` | counts thinking tokens! | same | same | Measure first → set = thinking + answer (ref-06) |
| `stop` | supported | supported | supported | Set for structured output |
| Structured output | JSON mode (version-dependent) | JSON mode mature | supported | Production: hard schema (`response_format`) |
| `seed` | partial support | varies | — | Fix for A/B reproducibility only |
| Streaming | yes | yes | yes | Mandatory for agent loops |

**Determinism caveat**: `temperature=0` is NOT guaranteed deterministic (floating point, parallel scheduling). For strict reproducibility: seed + fixed input order + single-threaded.

**Rate limits**: free/cheap tiers often 2–10 QPS. Agent loops need queues + exponential backoff + timeout + auto-failover to backup model.

---

## 3. Tool-protocol differences (the #1 integration trap)

| Vendor | Tool protocol | DIY rule |
|--------|---------------|----------|
| **GLM-4.6** | **XML tool template** | Do NOT force JSON schema. Write tool defs in GLM's XML format. |
| DeepSeek / Qwen / Kimi / Doubao | JSON schema function calling | Mainstream; per-vendor schema field details differ (descriptions, required flags) |
| Kimi K2 | Native MCP tools | Plug MCP servers directly |
| Hunyuan Hy3 | Function calling | Standard-ish; verify against docs |

**Adapter pattern** (mandatory): one thin tool layer that converts vendor-specific formats at the edges. Business code never touches vendor formats. Tool descriptions in CN (CN models understand CN descriptions better), param names in EN (code-side stability).

---

## 4. Agent-native workload mapping

| Scenario | Pick | Why |
|----------|------|-----|
| Long-horizon multi-step agent (tool-dense) | Kimi K2 / MiniMax M2 | Long-trajectory RL (Forge RL, 3000+ real MCP tools), low latency |
| Agent + reasoning hybrid | GLM-4.6 | ARC trinity: agentic + reasoning + coding native |
| High-concurrency tool calls | DeepSeek V4-Flash | 13B active, trillion-token-scale throughput |
| Private local agent | Qwen3-30B-A3B | 3B active, consumer hardware |
| Deep-think interleaved | Hunyuan Hy3 | 交错式思考: think-while-acting |

**Agent-loop economics (CN-specific)**: each call is cheap → decompose MORE (finer steps, more tool calls) than you would with overseas flagship pricing. Flagship for decision points, Flash for bulk parallel sub-tasks.

---

## 5. Cache-aware model pairing

| Provider | Cache | DIY win |
|----------|-------|---------|
| DeepSeek | Official context caching (~1/10 hit price) | Stable prefix design = bill slashed (ref-04) |
| SGLang (self-hosted DeepSeek/Qwen) | RadixAttention prefix tree | Local equivalent of cache discount |
| All | KV cache on multi-turn | Keep sessions alive; don't restart conversations |

---

## 6. Local + API hybrid on a 16GB machine (low-spec reality)

| Task | Channel | Model |
|------|---------|-------|
| Private data (finance, personal docs) | Local | Qwen3-30B-A3B (quantized, ~20GB OK-ish; verify RAM) |
| Batch embedding | Local | paraphrase-multilingual-MiniLM-L12-v2 |
| Bulk classify/tag | Local OR V4-Flash | Volume → local free; volume+quality → Flash |
| High-intelligence reasoning, agent brain | API | V4 / Qwen3.5-Max / Kimi K2 |
| Tool-dense long-horizon | API | Kimi K2 / GLM-4.6 |

Engineering notes: local inference via SGLang/vLLM/llama.cpp (GGUF); unified gateway between local & API (model switch = config change); model files on D: drive (user convention); monthly local-vs-API golden-set comparison.

---

## 7. Anti-patterns

- ❌ Sending T2 bulk work to a flagship — the #1 waste ("using a 49B-active model to add tags").
- ❌ Forcing JSON schema on GLM — use its XML template.
- ❌ Believing `temperature=0` = deterministic across vendors — verify with seed for A/B only.
- ❌ No failover — CN APIs have occasional blips (promos, disconnects); gateway must auto-switch backup.
- ❌ Trusting same model-name stability — pin dated IDs, monthly golden regression (ref-05).
