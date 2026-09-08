# Agentic RAG Subsystem for a Self-Improving AgentOS
### A Production-Grade Architecture Specification

---

## 1. Executive Summary

Conventional RAG treats retrieval as a stateless function: `embed(query) → top_k(vector_db) → stuff_context(llm)`. This fails inside an autonomous agent because the agent's information need is dynamic, multi-hop, contradictory-prone, cost-constrained, and evolves as the agent reasons. This document specifies **Agent RAG** — a retrieval subsystem that is itself an agent: it decides *whether* to retrieve, *what* to retrieve, *from where*, *how many rounds*, *how to fuse and verify* results, and *what to remember* for next time.

The subsystem is designed as a first-class service inside an AgentOS (alongside planning, tool execution, and memory), exposed through a small set of APIs (`plan`, `search`, `rerank`, `verify`, `context`, `feedback`), backed by a **polyglot storage layer** (SQL + vector + graph + search engine + object storage + cache), and closed with a **feedback loop** that turns every task execution into training signal for the router, the ranker, and the sufficiency model — without requiring manual labeling.

Design priorities, in order: **correctness/groundedness → cost/latency control → autonomy → self-improvement**. LLM calls are used only where they provide asymmetric value (query decomposition, sufficiency judgment on ambiguous cases, final synthesis) — everything that can be a deterministic algorithm (fusion, scoring, caching, routing under confidence, dedup, budget allocation) is implemented as one, because deterministic mechanisms are cheaper, debuggable, and don't hallucinate.

---

## 2. Design Principles

| # | Principle | Rationale |
|---|---|---|
| 1 | **Retrieval is a decision, not a step.** | The agent must be able to choose *not* to retrieve. Most conventional RAG wastes tokens retrieving for things the model already knows or that don't need grounding. |
| 2 | **Router before retriever.** | Source selection happens before search execution; a Query Planner + Router precedes any lexical/vector/graph call. |
| 3 | **Cheap-first, expensive-later.** | Lexical/metadata filters run before ANN; ANN runs before cross-encoders; cross-encoders run before LLM reranking. |
| 4 | **Evidence, not documents.** | The unit that reaches the LLM is a verified, deduplicated, attributed evidence span — not a raw chunk. |
| 5 | **Sufficiency is measured, not assumed.** | A quantitative Sufficiency Score gates whether another retrieval round happens. |
| 6 | **Every retrieval is a labeled event.** | Task outcome propagates backward to (query, retriever, source, chunk) tuples, generating training data automatically. |
| 7 | **Untrusted by default.** | All retrieved content is treated as adversarial input until verified (prompt-injection scanning, permission checks, authority scoring). |
| 8 | **Determinism where possible, LLM where necessary.** | Fusion, budgeting, caching, and routing-under-confidence are deterministic; decomposition, sufficiency-on-the-margin, and synthesis use the LLM. |
| 9 | **Everything is traced.** | Every query→answer path is replayable from logs (OpenTelemetry-compatible), because "why did the agent retrieve this?" must always be answerable. |
| 10 | **Bounded autonomy.** | Recursive/iterative retrieval has hard ceilings (rounds, tokens, latency, cost) to prevent runaway loops. |

---

## 3. Complete Architecture

```
User Goal
   │
   ▼
Task Understanding ────────────────────────────────────────────┐
   │                                                            │
   ▼                                                            │
Information Need Detector  ──(no retrieval needed)──► Direct Answer
   │ (retrieval needed)
   ▼
Retrieval Planner  (builds Information Need Graph / DAG of sub-queries)
   │
   ▼
Query Decomposer  (rewrite, expand, split multi-hop)
   │
   ▼
Retrieval Router   (per sub-query: which retriever(s), budget, order)
   │
   ├──► Lexical (BM25/ripgrep) ─┐
   ├──► Dense Vector (ANN)      │
   ├──► Sparse (SPLADE)         │
   ├──► Graph (multi-hop)       ├──► Candidate Pools
   ├──► Structured (SQL)        │
   ├──► Code (AST/symbol)       │
   ├──► Memory (episodic/etc.)  │
   ├──► Experience (trajectory) │
   └──► Web (search+crawl)     ─┘
   │
   ▼
Candidate Fusion (RRF / weighted / learned)
   │
   ▼
Multi-stage Reranking (cheap → cross-encoder → LLM)
   │
   ▼
Evidence Verification (authority, contradiction, freshness, injection scan)
   │
   ▼
Context Builder (dedup, cluster, compress, budget, order)
   │
   ▼
LLM Reasoning / Planning
   │
   ▼
Sufficiency Evaluation ──(insufficient, budget remains)──► back to Query Decomposer
   │ (sufficient OR budget exhausted)
   ▼
Agent Execution
   │
   ▼
Outcome Evaluation
   │
   ▼
Experience Extraction → Experience Store
   │
   ▼
Retrieval Feedback → {Router weights, Ranker model, Sufficiency model, Cache}
   │
   ▼
Continuous Improvement (next task benefits)
```

---

## 4. Component Architecture

```
                         ┌─────────────────────────────┐
                         │           AgentOS            │
                         └──────────────┬───────────────┘
                                         │  Task, Context, Budget
                         ┌──────────────▼───────────────┐
                         │   Retrieval Controller (API)  │
                         └──────────────┬───────────────┘
             ┌───────────────────────────┼───────────────────────────┐
             ▼                           ▼                           ▼
    ┌─────────────────┐       ┌───────────────────┐       ┌───────────────────┐
    │  Query Planner   │       │ Retrieval Router   │       │  Memory Manager    │
    │  (DAG builder)   │       │ (source selection) │       │ (4 memory types)   │
    └────────┬─────────┘       └─────────┬──────────┘       └─────────┬─────────┘
             └───────────────────────────┼───────────────────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │     Multi-Source Retrieval     │
                         │  (parallel, budget-governed)   │
                         └───────────────┬────────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │       Candidate Fusion         │
                         └───────────────┬────────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │     Multi-stage Reranker       │
                         └───────────────┬────────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │   Evidence Verification Layer  │
                         └───────────────┬────────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │        Context Builder         │
                         └───────────────┬────────────────┘
                                         ▼
                                   LLM Agent Core
                                         │
                          ┌──────────────┴──────────────┐
                          ▼                              ▼
                 Sufficiency Model                  Execution Engine
                          │                              │
                          └──────────────┬───────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │   Outcome & Experience Store   │
                         └───────────────┬────────────────┘
                                         ▼
                         ┌───────────────────────────────┐
                         │   Retrieval Policy Learner     │
                         │ (router weights / ranker /     │
                         │  sufficiency thresholds/cache) │
                         └────────────────────────────────┘
```

Cross-cutting: **Observability bus** (traces every arrow above), **Security/Permission filter** (gates every candidate before it reaches Fusion), **Cost/Budget governor** (gates every stage).

---

## 5. Retrieval Source Architecture

### 5.1 Unified Interface

```typescript
interface RetrievalQuery {
  raw: string;
  rewritten?: string;
  taskId: string;
  entities?: Entity[];
  filters?: MetadataFilter;         // date, version, permission, repo, tenant
  topK: number;
  costBudget: number;               // ms + $ + tokens
  mode: "targeted" | "exploratory" | "verification";
}

interface Candidate {
  objectId: string;
  type: KnowledgeObjectType;
  content: string;
  score: number;                    // retriever-native score, NOT yet normalized
  retriever: RetrieverName;
  source: SourceRef;
  metadata: Record<string, any>;
}

interface Retriever {
  name: RetrieverName;
  capabilities: RetrieverCapability[];   // e.g. ["exact-match","code","low-latency"]
  estimateCost(q: RetrievalQuery): CostEstimate;
  search(q: RetrievalQuery): Promise<Candidate[]>;
  healthCheck(): Promise<HealthStatus>;
}
```

Every concrete retriever (`LexicalRetriever`, `DenseVectorRetriever`, `SparseRetriever`, `HybridRetriever`, `StructuredRetriever`, `GraphRetriever`, `CodeRetriever`, `MemoryRetriever`, `ExperienceRetriever`, `WebRetriever`, `MultimodalRetriever`) implements this interface. This gives the Router a **uniform capability contract**: it doesn't need to know *how* graph traversal works, only that `GraphRetriever.capabilities` includes `multi-hop` and its `estimateCost` returns something inside budget.

### 5.2 Registration & Discovery

Retrievers self-register into a `RetrieverRegistry` with declared capabilities and cost profile at startup (or dynamically, for pluggable data sources added by tenants). The Router queries the registry rather than hardcoding retriever references — this is what allows new sources (e.g., a new SaaS connector) to be added without touching routing logic.

### 5.3 Per-Source Notes

- **Lexical** (BM25 via Elasticsearch/OpenSearch/Tantivy, ripgrep for raw filesystem/code): best for exact identifiers, error strings, symbol names, config keys — anything where semantic drift would hurt (a stack trace should not be "semantically similar" to another stack trace, it should exact/fuzzy match).
- **Dense Vector** (HNSW/IVF+PQ): best for conceptual/semantic queries, paraphrase-tolerant retrieval, cross-lingual.
- **Sparse (SPLADE-style)**: middle ground — learned term expansion gives some semantic generalization while keeping interpretability and exact-term precision; cheaper than dense at index time for some corpora.
- **Structured/SQL**: anything with hard constraints (tenant_id, date ranges, status, permissions) — always applied as a *pre-filter*, never a post-filter, for both correctness and cost.
- **Graph**: multi-hop entity relationships (service → depends_on → service, function → calls → function, incident → caused_by → change). Two entry patterns: `Vector → Entity → Graph → Documents` (semantic seed, structural expansion) and `Query → Entity(NER) → Graph Traversal → Vector Search` (structural seed, semantic refinement).
- **Code**: AST/symbol index (ctags/tree-sitter/LSP), call graph, import graph, git blame/history, issue/PR search — treated as a *distinct modality* from generic text because relevance signals differ (symbol exactness, recency of change, call-graph proximity to the file under edit).
- **Memory**: working (current session scratchpad), semantic (durable facts about the user/project), episodic (past conversations/events), procedural (how-to / learned skills).
- **Experience**: past task trajectories, indexed by task-embedding + outcome + toolset used.
- **Web**: search engine + crawler + extraction, with mandatory authority/freshness scoring and cross-source agreement before use.
- **Multimodal**: images/PDF/tables — routed to modality-specific encoders (e.g. layout-aware PDF parsing, table-to-structured extraction) before being embedded into the same Knowledge Object schema (§9), so downstream fusion doesn't need to special-case modality.

---

## 6. Agentic Retrieval

### 6.1 Why Single-Shot Search Fails

For "Fix the authentication bug," a single BM25/vector query over "authentication bug" returns generic auth-related text. The actual information need decomposes into an **Information Need Graph**: which service, which recent error (logs), which code path (code search), which config (structured), which historical fix (experience), which docs, which tests. None of these are discoverable from the surface query alone — they must be inferred, and refined as evidence arrives.

### 6.2 Information Need Detection

Before any retrieval, classify the task's need:

```python
def detect_information_need(task, agent_state) -> InformationNeedAssessment:
    # 1. Does the agent already have sufficient grounding in working memory / context?
    if covered_by_context(task, agent_state.context):
        return InformationNeedAssessment(needed=False)
    # 2. Is this a closed-book reasoning/generation task (no external facts needed)?
    if is_self_contained(task):           # e.g. "refactor this function for readability"
        return InformationNeedAssessment(needed=False)
    # 3. Otherwise: classify need type(s)
    needs = classify_need_types(task)     # {factual, code, historical, procedural, current-state, ...}
    return InformationNeedAssessment(needed=True, need_types=needs)
```

This is a cheap classifier (fine-tuned small model or rules + embedding similarity threshold against "already known" context), *not* an LLM call for every task — LLM involvement is reserved for ambiguous cases that the classifier flags with low confidence.

### 6.3 Agentic Retrieval Controller Loop

```
Retrieval Goal
  ↓
Information Need Graph  (nodes = sub-needs, edges = dependencies)
  ↓
Sub-query Generation     (LLM-assisted decomposition, §7)
  ↓
Retriever Selection      (Router, §8)
  ↓
Search                   (parallel, budgeted)
  ↓
Evidence Evaluation      (relevance + trust, §14)
  ↓
Information Gap Detection
  ↓
  ├─ gap found & budget remains → refine query → Sub-query Generation
  └─ no gap OR budget exhausted → return evidence set
```

```python
def agentic_retrieve(goal, agent_state, budget: RetrievalBudget) -> EvidenceSet:
    need_graph = build_information_need_graph(goal, agent_state)
    evidence = EvidenceSet()
    frontier = need_graph.roots()
    rounds = 0

    while frontier and budget.remaining() and rounds < budget.max_rounds:
        rounds += 1
        subqueries = generate_subqueries(frontier, evidence, agent_state)  # expansion/decomposition
        plans = [router.route(sq, agent_state, budget) for sq in subqueries]
        raw_candidates = parallel_search(plans, budget)
        fused = fuse(raw_candidates)
        ranked = rerank(fused, subqueries, budget)
        verified = verify_evidence(ranked, agent_state.permissions)
        evidence.merge(verified)

        gaps = detect_gaps(need_graph, evidence)      # missing entity/dependency/temporal ctx
        frontier = next_frontier(need_graph, gaps)
        if sufficiency(evidence, goal) >= budget.sufficiency_threshold:
            break

    return evidence.finalize()
```

Supported retrieval modes, all expressed as configurations of the loop above:
- **Query expansion**: add synonyms/related terms to widen recall (cheap, deterministic — WordNet/embedding-neighbor expansion or learned expansion model).
- **Query rewriting**: normalize ambiguous/conversational phrasing into a retrieval-optimized query (LLM or a fine-tuned rewriter).
- **Query decomposition**: split compound queries into atomic sub-queries (LLM-assisted, §7).
- **Multi-query retrieval**: issue several reformulations of the same need in parallel, fuse results (RAG-Fusion style) — improves recall against embedding brittleness.
- **Iterative retrieval**: loop the whole controller until sufficiency or budget exhaustion.
- **Multi-hop / recursive retrieval**: follow entity/graph edges discovered in round *n* to seed round *n+1* (bounded depth, cycle detection required).
- **Exploratory retrieval**: wide, shallow, diversity-maximizing (used when need is underspecified).
- **Targeted retrieval**: narrow, precision-maximizing (used when a known entity/ID/error is present).
- **Verification retrieval**: a query issued specifically to confirm or refute a claim already in evidence (used by the Evidence Verification Layer, §14).
- **Contradiction search**: deliberately searches for evidence that would *disagree* with the current leading hypothesis, to avoid confirmation bias in the evidence set.

---

## 7. Query Planning

### 7.1 Information Need Graph as a DAG

```
Goal: "Design a scalable MCP tool management system"
├── Q1: MCP protocol architecture           (root)
├── Q2: tool discovery
│    ├── Q2.1: discovery protocols          (depends_on: Q1)
│    └── Q2.2: existing discovery impls     (depends_on: Q2.1)
├── Q3: tool registry                       (depends_on: Q1)
├── Q4: tool routing                        (depends_on: Q2, Q3)
├── Q5: permission management               (depends_on: Q1)
├── Q6: tool execution                      (depends_on: Q3, Q4)
├── Q7: tool lifecycle                      (depends_on: Q3)
├── Q8: existing implementations            (root, exploratory)
├── Q9: scalability constraints             (depends_on: Q4, Q6)
└── Q10: security                           (depends_on: Q5, Q6)
```

```python
@dataclass
class QueryNode:
    id: str
    text: str
    depends_on: list[str]
    need_type: str            # factual | code | experience | current-state | historical
    status: str = "pending"   # pending | ready | executing | done | failed

def topo_schedule(dag: dict[str, QueryNode]) -> list[list[str]]:
    """Returns execution waves: nodes in the same wave can run in parallel."""
    in_degree = {n: len(dag[n].depends_on) for n in dag}
    waves, remaining = [], set(dag)
    while remaining:
        wave = [n for n in remaining if in_degree[n] == 0]
        if not wave:
            raise CycleError("Information need graph has a cycle")
        waves.append(wave)
        remaining -= set(wave)
        for n in remaining:
            in_degree[n] = len(set(dag[n].depends_on) & remaining)
    return waves
```

The DAG lets independent sub-queries (Q1, Q8) execute in parallel while dependent ones (Q2.2 needs Q2.1's output — e.g., a discovered protocol name — to be well-formed) execute sequentially. **Node count is bounded** (default max 12 open nodes per goal) to prevent unbounded fan-out; the LLM decomposer is prompted with this ceiling and instructed to merge redundant needs.

### 7.2 Decomposition Algorithm

1. Deterministic pass: pattern-match compound conjunctions ("X and Y", enumerated lists) — no LLM needed for the common case.
2. LLM pass (only if deterministic pass yields <2 nodes and task complexity heuristic is high): prompt the LLM to emit a DAG in structured JSON (id, text, depends_on, need_type), validated against a schema and a max-node constraint.
3. Deduplicate near-identical nodes via embedding similarity (threshold ~0.92) before scheduling.

---

## 8. Retrieval Router

### 8.1 Inputs / Outputs

**Input:** query (rewritten), task, agent state, project state, known entities, prior retrieval results (this session), available retriever registry, cost budget, latency budget.
**Output:** a `RetrievalPlan`: ordered/parallel list of `(retriever, sub-query, top_k, filters, budget_share)`.

### 8.2 Routing Strategies Compared

| Strategy | How it works | Pros | Cons | Use when |
|---|---|---|---|---|
| Rule-based | Regex/heuristics on query shape (has stack trace → lexical+code; has date → temporal filter; has entity ID → structured) | Zero latency, fully interpretable, zero training data | Brittle, doesn't generalize | Cold start, high-confidence patterns (>80% of traffic in mature systems) |
| Classifier-based | Small supervised model (query features → retriever set) trained on logged outcomes | Fast, cheap, improves with data | Needs labeled/derived training data | Once feedback loop (§16) has ≥10k logged tasks |
| LLM routing | Prompt LLM with registry + query, ask for plan | Handles novel/ambiguous queries, no training data needed | Latency + cost per query, possible hallucinated retriever names | Ambiguous/exploratory queries, low-traffic sources |
| RL routing | Router is a policy trained via reward = downstream task success − cost | Learns non-obvious multi-source strategies over time | Complex to train/validate safely, delayed/sparse reward | Mature system with a large task-outcome dataset |
| Bandit-based | Contextual bandit per query-cluster, reward = retrieval quality signal (immediate) | Fast online learning, exploration/exploitation built in, simpler than full RL | Assumes independence across rounds (violates multi-hop dependency) | Per-sub-query retriever selection within a single round |
| Hybrid (recommended) | Rules for the high-confidence cases → classifier for the bulk → bandit for retriever choice within a source category → LLM fallback for low-confidence/novel cases | Best latency/cost/accuracy trade-off | More moving parts to operate | **Production default** |

### 8.3 Recommended Production Architecture

```python
def route(query: RetrievalQuery, state, budget) -> RetrievalPlan:
    # Tier 0: hard rules (identifiers, stack traces, file paths, explicit "as of <date>")
    if rule_match := match_hard_rules(query):
        return rule_match.to_plan(budget)

    # Tier 1: classifier over query embedding + task features → candidate retriever set
    candidate_sources = source_classifier.predict(query, state)   # e.g. {lexical, code, graph}

    # Tier 2: contextual bandit selects among near-tied candidates / allocates budget share
    weighted_sources = bandit.select(candidate_sources, context=query_cluster(query))

    # Tier 3: low-confidence fallback → LLM plans explicitly
    if classifier.confidence < CONF_THRESHOLD:
        weighted_sources = llm_router.plan(query, registry.capabilities(), budget)

    return build_plan(weighted_sources, query, budget)
```

Example — `"Why is payment timeout occurring?"` → Tier 0 rules detect no hard pattern → Tier 1 classifier (trained on past incident-investigation tasks) proposes `{structured(prod env filter), lexical(log search "timeout"), code(payment service), graph(service dependencies), experience(past incidents), web(external API status)}` → Tier 2 bandit allocates more budget share to `experience` and `structured` because historically, for this query cluster, those two sources drove task success more than `web` → plan executes in parallel with per-source budget caps.

---

## 9. Retrieval Fusion

### 9.1 Composite Candidate Score

```
CandidateScore =
    w1 · semantic_score
  + w2 · lexical_score
  + w3 · structural_score      (graph proximity / AST proximity)
  + w4 · graph_score
  + w5 · authority_score
  + w6 · freshness_score
  + w7 · experience_score      (did similar retrievals help before)
  + w8 · task_relevance_score  (LLM/classifier: does this actually answer the need)
  − p1 · redundancy_penalty
  − p2 · contradiction_penalty
```

Weights `w*, p*` start from priors (below) and are tuned by the Retrieval Policy Learner (§16) via learning-to-rank on logged (candidate, used, outcome) triples.

**Default priors:** semantic 0.25, lexical 0.20, structural 0.10, graph 0.10, authority 0.10, freshness 0.10, experience 0.10, task_relevance 0.15 *(renormalized to sum to 1 minus penalties, since components overlap)* — in practice we don't hand-tune a single global weight vector; weights are conditioned on **query need_type** (a code query up-weights structural/lexical; a "current state" query up-weights freshness; an incident query up-weights experience).

### 9.2 Score Normalization

Different retrievers produce incomparable raw scores (BM25 is unbounded, cosine similarity is [-1,1], graph proximity might be hop-count). Before fusion:

```python
def normalize(scores: list[float], method="minmax_robust") -> list[float]:
    # robust min-max: clip outliers at p1/p99 before scaling to [0,1]
    lo, hi = percentile(scores, 1), percentile(scores, 99)
    return [clamp((s - lo) / (hi - lo + 1e-9), 0, 1) for s in scores]
```

Per-retriever normalization is computed **within each retriever's own result set**, per query, not globally — global normalization drifts as corpora and score distributions change.

### 9.3 Fusion Methods

| Method | Formula / mechanism | When to use |
|---|---|---|
| **RRF** (Reciprocal Rank Fusion) | `score(d) = Σ 1/(k + rank_r(d))` over retrievers r | Default: rank-based, robust to score-scale mismatch, no training needed |
| Weighted score fusion | Normalize then weighted sum (§9.1) | When you have enough logged data to trust learned weights |
| Learned ranking (LTR) | LambdaMART/XGBoost over feature vector (all component scores + metadata) → single relevance score | Once ≥ tens of thousands of labeled/derived (query, doc, relevance) triples exist |
| Cross-encoder reranking | Joint (query, doc) transformer scoring | Stage 4 in the ranking pipeline (§10) — expensive, used on ≤500 candidates |
| LLM reranking | LLM scores/orders a short list with reasoning | Stage 5, ≤20 candidates, used for nuanced task-relevance judgment |

**Recommendation:** RRF as the default fusion for combining heterogeneous retriever outputs cheaply; LTR once volume supports it; cross-encoder + optional LLM pass as the final two ranking stages regardless of fusion method chosen upstream.

---

## 10. Reranking

### 10.1 Multi-Stage Funnel

```
10^6–10^9 objects
    │ cheap filtering (metadata/permission/tenant pre-filter)
    ▼
~10,000 candidates
    │ ANN / BM25 (per-retriever top-k)
    ▼
~500 candidates
    │ fusion (RRF or weighted)
    ▼
~100 candidates
    │ lightweight reranker (small cross-encoder or LTR model)
    ▼
~20 candidates
    │ heavy cross-encoder / LLM reranker
    ▼
5–10 evidence units → Context Builder
```

Each stage cuts candidate volume by ~10-50x while increasing per-candidate scoring cost by ~10-100x — net cost stays roughly flat while precision increases monotonically. This "cheap-first, expensive-later" funnel is the single most important cost control in the system (§18).

### 10.2 Optimizing for More Than Relevance

The final 5–10 selection additionally optimizes for:
- **Diversity** via **MMR (Maximal Marginal Relevance)**:
  `MMR = argmax_{d ∈ C \ S} [ λ·relevance(d) − (1−λ)·max_{s∈S} similarity(d,s) ]`
  greedily selects the next document that is relevant but not redundant with what's already selected (`λ≈0.7` typical starting point). This prevents the classic RAG failure of 8 near-duplicate chunks all saying the same thing while missing a distinct angle.
- **Authority** — prefer canonical docs over mirrors/forks/stale copies (§14).
- **Freshness** — decay function on document age, task-timestamp-aware (§13).
- **Completeness** — does the selected set jointly cover all sub-query nodes in the Information Need Graph (§7), not just the top-scoring single node repeatedly.
- **Contradiction** — deliberately *keep* one representative of each side of a genuine contradiction (don't silently drop it) and flag it for the Context Builder to surface as uncertainty rather than pick a winner silently.
- **Token efficiency** — score-per-token, not just score, when deciding marginal inclusion under a tight budget.

---

## 11. Context Engineering

### 11.1 Pipeline

```
retrieval → deduplication → clustering → compression → evidence extraction
→ contradiction detection → relevance filtering → context ordering
→ token budgeting → final context construction
```

- **Deduplication**: near-duplicate detection via SimHash/MinHash on chunks (cheap) before embedding-based clustering (more expensive) — catches copy-pasted docs/mirrors early.
- **Clustering**: group remaining candidates by topic/entity (agglomerative clustering on embeddings) to support both diversity selection (§10.2) and structured presentation (group evidence by sub-topic in the final context).
- **Compression**: contextual compression — extract only the query-relevant spans from a long document (extractive: sentence-level relevance scoring; abstractive: LLM summarization of a cluster into a "summary node" that cites its sources) rather than injecting whole documents.
- **Evidence extraction**: pull sentence-/paragraph-level spans with span-level citations back to source id, not whole-document dumps.
- **Contradiction detection**: pairwise NLI (entailment/contradiction/neutral) classifier across the surviving evidence set; contradictions are annotated, not resolved silently.
- **Relevance filtering**: final task-relevance threshold cut (distinct from ranking — this is a hard floor, e.g. drop anything below a minimum absolute relevance even if it's "top 10" among low-quality candidates).
- **Context ordering**: order matters for LLM attention — put highest-relevance and most-recent evidence near the start and end of the context (avoid "lost in the middle"); group by sub-query/cluster with clear headers.
- **Token budgeting**: see below.

### 11.2 Adaptive Token Allocation

Rather than fixed percentages, allocate the context budget proportional to **measured information value per category for this task type**, subject to floors and ceilings:

```python
def allocate_budget(total_tokens: int, categories: dict[str, CategoryStats], need_types: set[str]) -> dict[str, int]:
    # base priors, adjusted by observed marginal-utility-per-token from feedback (§16)
    priors = {
        "primary_evidence": 0.20, "supporting_evidence": 0.20, "code": 0.15,
        "experience": 0.15, "constraints": 0.10, "source_metadata": 0.10,
        "uncertainty": 0.10,
    }
    # task-type adjustment, e.g. code-fix tasks shift weight to code/experience
    adjusted = adjust_for_need_types(priors, need_types)
    # learned adjustment from historical marginal utility (§16), bounded to +/-50% of prior
    adjusted = blend(adjusted, categories.learned_weights, floor=0.5, ceiling=1.5)
    raw = {k: int(total_tokens * v) for k, v in adjusted.items()}
    return enforce_floors_and_ceilings(raw, min_tokens=200, max_share=0.4)
```

If a category is starved (e.g., "uncertainty" evidence exists but the fixed 10% would truncate a critical contradiction), the allocator reallocates unused budget from lower-marginal-value categories greedily (knapsack-style, sorted by score-per-token) rather than rigidly enforcing percentages.

### 11.3 Retrieval Granularity

- **Chunk-level**: default unit for search/ranking (fixed or semantic chunking).
- **Parent-document retrieval**: rank at chunk level, but expand to the parent section/document when injecting into context, to preserve surrounding structure the LLM needs (a common failure of naive chunk-RAG is a fact stripped of the qualifier two sentences earlier).
- **Hierarchical retrieval**: document → section → chunk → sentence index, allowing coarse-to-fine drilling (search sections first, then chunks within top sections) — cuts ANN index size and improves precision for long documents.
- **Sentence-level evidence**: final citations resolve to sentence spans, not whole chunks, for groundedness/citation accuracy (§21).
- **Summary nodes**: precomputed (or on-demand, cached) LLM summaries of clusters/documents, stored as their own Knowledge Objects (type=`Summary`, `parent`=source doc) so repeated queries against the same cluster don't re-summarize.
- **Document relationships**: `parent`/`children`/`dependencies` fields on the Knowledge Object (§12) let the Context Builder pull in a referenced doc (e.g., a config file a runbook mentions) proactively when budget allows.

---

## 12. Knowledge Representation

### 12.1 Unified Knowledge Object

```json
{
  "id": "kobj_...",
  "type": "Document | Chunk | CodeSymbol | Function | Class | Repository | Issue | PR | Tool | Skill | Project | Memory | Episode | Trajectory | Experiment | Error | Solution | WebPage | API | Dataset | Summary",
  "content": "raw text/code content",
  "summary": "short abstractive summary (cached)",
  "embedding": [0.013, ...],
  "sparse_representation": {"term_id": weight, ...},
  "entities": [{"id": "ent_...", "type": "Service", "text": "payment-svc"}],
  "relations": [{"type": "depends_on", "target": "kobj_..."}],
  "metadata": {"repo": "...", "language": "python", "tags": [...]},
  "source": {"origin": "github|confluence|web|db|experience", "uri": "..."},
  "authority": 0.82,
  "timestamp": "2026-06-01T00:00:00Z",
  "version": "v1.4.2",
  "permissions": {"tenant_id": "...", "acl": ["role:eng"]},
  "parent": "kobj_parent_id",
  "children": ["kobj_child_1", "..."],
  "dependencies": ["kobj_dep_1"],
  "hash": "sha256:...",
  "quality_score": 0.77,
  "usage_statistics": {"retrieved_count": 42, "used_in_success": 30, "used_in_failure": 3}
}
```

### 12.2 Simultaneous Indexing

Each Knowledge Object is fanned out to the store appropriate to each of its representations at write time (via an event/queue, §18):

| Representation | Store |
|---|---|
| `id`, `metadata`, `permissions`, `version`, `timestamp`, `authority`, `quality_score`, `usage_statistics` | SQL (Postgres) — source of truth, transactional |
| `embedding` | Vector DB (HNSW index) |
| `sparse_representation` + full text | Search engine (BM25/SPLADE index) |
| `entities`, `relations` | Graph DB |
| `content` (large blobs, code, PDFs, images) | Object storage (S3-compatible), referenced by `source.uri` |
| hot/recent objects | Cache (Redis) |

The SQL row is authoritative for identity/permissions/lifecycle; all other indexes are **derived and rebuildable** from it — this is what makes re-indexing, schema migration, and embedding-model upgrades tractable without data loss.

---

## 13. Graph + Vector + Lexical RAG

```
                Knowledge
                   │
    ┌──────────────┼──────────────┐
    ↓              ↓              ↓
Lexical         Vector          Graph
Search          Search          Search
    │              │              │
    └──────────────┼──────────────┘
                   ↓
                Fusion
                   ↓
               Reranking
                   ↓
                Context
```

**When each layer dominates:**
- **Lexical dominates** when the query contains exact identifiers (error codes, function names, config keys, IDs) — vector search under-performs here because embeddings blur exact tokens.
- **Vector dominates** when the query is conceptual/paraphrastic ("how does our retry logic handle timeouts") with no exact anchor.
- **Graph dominates** when the need is inherently relational/multi-hop ("what else breaks if I change this service's schema") — vector/lexical can find the service doc but not its blast radius.

**Two composed traversal patterns:**
1. `Vector → Entity → Graph → Documents`: semantic search finds a seed document, NER/entity-linking extracts entities from it, graph traversal expands to related entities, then documents attached to those entities are pulled — used when the query is fuzzy but the answer requires structural context (e.g., "why might this API be slow" → seed doc on the API → traverse to its dependencies → pull docs on each dependency).
2. `Query → Entity → Graph Traversal → Vector Search`: NER on the query directly extracts a known entity (e.g., "payment-service"), graph traversal finds structurally related entities (callers, callees, owning team, recent incidents), then vector search is scoped *within* that entity set — used when the query names something concrete and the goal is depth, not discovery.

The Router (§8) selects between these two patterns based on whether entity extraction on the raw query succeeds with high confidence (pattern 2) or not (pattern 1).

---

## 14. Trust, Verification & Evidence

### 14.1 Evidence Verification Layer

Distinguishes: **Retrieved → Relevant → Trusted → Verified → Consistent.** A candidate must pass all five gates before entering the final context.

```python
def verify_evidence(candidates: list[Candidate], permissions) -> list[VerifiedEvidence]:
    out = []
    for c in candidates:
        if not permission_check(c, permissions):            # gate 0: never even see denied content
            continue
        if injection_scan(c.content).is_suspicious:          # gate: prompt-injection / malicious payload
            flag_and_quarantine(c); continue
        relevance = task_relevance_score(c)
        if relevance < MIN_RELEVANCE:
            continue
        authority = compute_authority(c.source)
        freshness = compute_freshness(c.metadata.timestamp, task_timestamp)
        agreement = cross_source_agreement(c, candidates)      # how many independent sources corroborate
        contradiction = contradiction_score(c, candidates)
        confidence = combine(relevance, authority, freshness, agreement, contradiction)
        out.append(VerifiedEvidence(c, confidence, contradiction_flag=contradiction > CONTRA_THRESHOLD))
    return out
```

### 14.2 Detected Failure Modes

- **Unsupported claims**: text asserts a fact with no corroborating source — flagged, down-weighted, or excluded depending on confidence threshold for the task (a code-fix task should be stricter than a brainstorming task).
- **Contradictory documents**: NLI-based pairwise contradiction detection (§11) surfaces conflicts explicitly rather than silently picking one.
- **Outdated information**: freshness score vs. task/query temporal intent (§15).
- **Hallucinated retrieval**: candidate's claimed content doesn't actually appear in the source when spot-checked (span verification against the source hash) — a defense against corrupted or synthetic index entries.
- **Low-quality sources**: authority score below floor.
- **Duplicated evidence**: caught upstream by dedup (§11) but re-checked here for near-duplicates that slipped through with paraphrase.
- **Circular evidence**: a claim's only support is another document that itself cites the first document (detected via provenance graph traversal — if two "independent" sources share a common ancestor in the citation graph, they don't count as independent corroboration).
- **Source poisoning**: anomalous authority/edit patterns (sudden edits, low-reputation contributor injecting a doc right before it's retrieved) — flagged for exclusion or human review.

### 14.3 Scoring Definitions

```
authority_score   = f(source_type, domain_reputation, internal_review_status, citation_count)
evidence_confidence = w1·relevance + w2·authority + w3·freshness + w4·agreement − w5·contradiction
cross_source_agreement = |{independent sources supporting claim}| / |{independent sources addressing claim}|
contradiction_score = max NLI-contradiction probability against any other kept candidate
freshness_score   = decay(now - doc.timestamp; half_life = f(domain))   # §15
```

### 14.4 Evidence Graph

Maintain a small per-query provenance graph: nodes = evidence units, edges = `supports` / `contradicts` / `derived_from`. This graph (a) powers circular-evidence detection, (b) is what gets surfaced to the user/agent as "here's a genuine disagreement between source A and source B," and (c) is logged for the Observability layer.

---

## 15. Self-Correcting Retrieval

### 15.1 Sufficiency Model

```
Sufficiency = w1·coverage + w2·relevance + w3·authority + w4·consistency + w5·freshness − w6·uncertainty
```

- `coverage`: fraction of Information Need Graph nodes (§7) with at least one confidence-passing evidence unit.
- `relevance`: mean task-relevance of kept evidence.
- `authority`: mean authority of kept evidence.
- `consistency`: `1 − contradiction_rate` among kept evidence.
- `freshness`: mean freshness score, weighted by whether the task needs current vs. historical state.
- `uncertainty`: proportion of Information Need Graph nodes with only low-confidence or single-source evidence.

```python
def sufficiency(evidence: EvidenceSet, need_graph) -> float:
    coverage = covered_nodes(need_graph, evidence) / len(need_graph.nodes)
    return (W_COV*coverage + W_REL*evidence.mean_relevance() + W_AUTH*evidence.mean_authority()
            + W_CONS*(1 - evidence.contradiction_rate()) + W_FRESH*evidence.mean_freshness()
            - W_UNC*evidence.uncertainty_ratio())

if sufficiency(evidence, need_graph) < THRESHOLD and budget.remaining():
    trigger_gap_driven_retrieval(evidence, need_graph)
```

### 15.2 Failure Detection → Corrective Action Map

| Detected failure | Signal | Corrective action |
|---|---|---|
| Too few relevant docs | candidate count post-filter < floor | query expansion, broaden filters |
| High similarity, low actual relevance | embedding score high but task_relevance_score low | switch retriever (lexical/graph instead of vector), rewrite query |
| Conflicting evidence | contradiction_score > threshold | verification retrieval targeting the specific claim |
| Missing critical entity | Information Need Graph node has zero candidates | targeted retrieval seeded by the entity name, or NER re-run on evidence found so far |
| Missing dependency | graph traversal returns node with no attached docs | expand graph hop count by 1, or code/structured retrieval on that node |
| Missing temporal context | freshness score all stale, or task needs "current" and nothing recent found | re-query with recency filter, escalate to web retrieval |
| Low source authority | mean authority < floor | escalate to higher-authority source class (official docs > web > forum) |
| Insufficient evidence coverage | sufficiency.coverage low | more retrieval hops / additional sub-queries from the DAG |

All corrective actions loop back into the Agentic Retrieval Controller (§6.3) as a new frontier, bounded by `budget.max_rounds` (default 3–5) to prevent unbounded recursion (§17, anti-pattern 17).

---

## 16. Self-Improving RAG

### 16.1 Feedback Loop

```
Retrieval → Agent Reasoning → Execution → Result → Evaluation
   → Retrieval Feedback → {Router, Ranker, Sufficiency thresholds, Cache, Index quality scores}
```

Every task produces a feedback record without manual labeling, because **task outcome is the label**:

```python
@dataclass
class RetrievalFeedbackEvent:
    task_id: str
    query: str
    need_type: str
    plan: RetrievalPlan             # which retrievers/sources were used
    candidates_shown: list[str]     # object ids surfaced to context
    candidates_cited: list[str]     # object ids the LLM actually cited/used
    task_success: bool
    task_reward: float              # graded, not just binary, when available
    tokens_used: int
    latency_ms: int
    contradiction_encountered: bool
```

### 16.2 What Is Learned, From What Signal

| Learned thing | Signal | Method |
|---|---|---|
| Which retriever works for which task/need_type | (need_type, retriever) → task_success rate | Contextual bandit reward update / classifier retrain |
| Which query transformations work | (raw_query, rewritten_query, retriever) → success | Offline LTR / rewriter fine-tuning on high-reward transformations |
| Which sources are reliable | source → (cited_rate, contradiction_rate, task_success when used) | Authority score update (§14) — exponential moving average |
| Which chunks are useful | chunk → (shown_count, cited_count, success-when-cited) | `quality_score` update on Knowledge Object (§12) |
| Which experiences lead to success | trajectory → downstream reuse success | Experience ranking model (§17.4) |
| Which retrieval paths waste tokens | plan → tokens_used vs. marginal sufficiency gain | Cost-aware routing penalty update (§18) |
| Which retrieval paths cause errors | plan → error/exception rate | Router blacklist/derate for that (need_type, source) pair |

### 16.3 Learning Methods, Compared

- **Contextual bandits** — best for *per-query* retriever/source selection where reward is available almost immediately (was this candidate cited, was it contradicted). Low complexity, safe to deploy continuously.
- **Learning-to-rank** — best for reranking-stage score calibration; trained offline/batch on logged (query, doc, cited/success) triples; deployed as a periodically-refreshed model, not online.
- **Preference optimization** (e.g., DPO-style) — best for tuning the query-rewriter / LLM-router prompt policy using pairs of (better plan, worse plan) derived from A/B or logged comparisons.
- **Reinforcement learning (full RL)** — reserved for the *multi-round* retrieval policy (how many rounds, when to stop) where reward is delayed to end-of-task; higher complexity/risk, deploy only once bandit + LTR are stable and there's sufficient trajectory volume.
- **Retrieval policy optimization** (bounded-search policy gradient over the Sufficiency threshold and round budget) — tunes `THRESHOLD` and `max_rounds` in §15.1 automatically instead of by hand, using task_reward vs. tokens_used trade-off curves.
- **Adaptive query routing** — the composite Tier0/1/2/3 router (§8.3) is retrained continuously (Tier 1 classifier nightly batch, Tier 2 bandit online, Tier 0 rules updated manually/quarterly from audit).

### 16.4 Guardrails on Self-Improvement

- All learned-weight updates are **bounded-delta** (max % change per retrain cycle) to avoid regressions from a bad batch.
- A **shadow/canary evaluation** gate: new router/ranker weights run in shadow mode against a held-out task set before promotion.
- **Rollback**: every policy version is stored; automatic rollback if canary success rate drops beyond a threshold.

---

## 17. Anti-Patterns

| # | Anti-pattern | Failure mode at scale | Engineering fix |
|---|---|---|---|
| 1 | Vector DB only | Misses exact-match needs (IDs, error codes), degrades on structured/temporal constraints | Hybrid retrieval (§5.4/§9), metadata pre-filtering |
| 2 | Top-K only | No accounting for redundancy, diversity, or budget adaptivity; fixed K wastes tokens on easy queries and starves hard ones | Adaptive-K via sufficiency model (§15), MMR (§10.2) |
| 3 | Fixed chunk size | Splits semantic units mid-thought; wrong granularity for code vs. prose vs. tables | Content-aware/semantic chunking + hierarchical retrieval (§11.3) |
| 4 | Fixed embedding model | Can't improve without re-indexing everything; poor fit for code vs. prose vs. multimodal | Per-modality embedding models behind the unified `Retriever` interface; embedding version stored on Knowledge Object for staged migration |
| 5 | Single retrieval pass | Can't recover from a bad first query; no handling of multi-hop needs | Iterative Agentic Retrieval Controller (§6.3) with sufficiency gate (§15) |
| 6 | Blind context stuffing | Dilutes attention, wastes tokens, increases hallucination via irrelevant noise | Context Builder pipeline (§11): dedup, compress, budget |
| 7 | No reranking | Retriever-native scores are not directly comparable/optimal; low precision at the top | Multi-stage reranking funnel (§10) |
| 8 | No metadata filtering | Permission leaks, stale/wrong-version docs surfacing, tenant crossover | Structured pre-filter before any semantic scoring (§5.3, §19) |
| 9 | No source authority | Low-quality/forum content ranked equal to canonical docs | Authority score as a first-class fusion component (§9.1, §14.3) |
| 10 | No temporal awareness | "Current API" answered with 2-year-old doc | Temporal RAG (§15... see §13 below in doc / freshness scoring) |
| 11 | No contradiction detection | Agent confidently states a claim contradicted elsewhere in the corpus | NLI-based contradiction detection in Evidence Verification (§14) |
| 12 | No retrieval evaluation | No visibility into whether retrieval is actually helping | Retrieval + Agent + System metrics (§21), traced (§20) |
| 13 | No memory integration | Agent re-retrieves/re-derives things it already learned this session or in past sessions | Memory-Aware RAG (§ Memory section) |
| 14 | No experience retrieval | Agent repeats past mistakes, doesn't reuse successful strategies | Experience RAG (§ Experience section) |
| 15 | LLM deciding everything | Slow, expensive, non-deterministic, hard to debug/regress-test | Deterministic mechanisms (fusion, budgeting, dedup, rule-tier routing) wherever value doesn't require judgment |
| 16 | Excessive LLM calls | Cost/latency blow up; diminishing returns past a few calls per task | Cheap-first funnel (§10), Tier 0/1/2 routing before any LLM call, cached summaries |
| 17 | Unlimited recursive search | Infinite loops, runaway cost, agent "rabbit-holing" | Hard round/token/latency/cost ceilings on the Agentic Retrieval Controller (§6.3, §15), cycle detection in graph traversal |

---

## 18. Performance / Cost Optimization

### 18.1 Cost Model

```
Cost(plan) = Σ_over_stages [ latency_i · λ  +  compute_i · c  +  network_i · n
                             + token_cost_i · t  +  retrieval_complexity_i · r ]
```

Each retriever declares an `estimateCost()` (§5.1) so the Router can reject/downgrade plans that exceed `costBudget` *before* execution, not after.

### 18.2 Mechanisms

| Mechanism | Where applied |
|---|---|
| Query result cache | Exact-query cache (hash of normalized query+filters) — highest hit rate on repeated/templated queries |
| Semantic cache | Cache keyed by embedding-similarity bucket (catches paraphrases of previously-answered queries) |
| Embedding cache | Content-hash keyed — never re-embed unchanged content |
| Hierarchical indexes | Coarse (document/section) index filters before fine (chunk) ANN search — cuts ANN search space |
| Incremental / async indexing | New/changed content indexed via event queue, not full re-index; keeps write path off the critical query path |
| Batch embedding | Amortizes embedding-model inference cost for bulk ingestion |
| Adaptive retrieval depth | `topK` and `max_rounds` scale with query complexity/ambiguity, not fixed constants |
| Cheap-first, expensive-later | The funnel in §10.1 — the core cost lever of the whole system |

### 18.3 Cost-Aware Retrieval Policy

```python
def cost_aware_plan(candidates_plans: list[RetrievalPlan], budget) -> RetrievalPlan:
    feasible = [p for p in candidates_plans if p.estimated_cost() <= budget]
    if not feasible:
        return cheapest_partial_plan(candidates_plans, budget)   # degrade gracefully, don't fail
    return max(feasible, key=lambda p: p.expected_sufficiency_gain() / p.estimated_cost())
```

Scale targets (10^6–10^9 objects) are met by: ANN indexes sharded by tenant/project (never a single global HNSW graph), SQL for exact filters (never scan-and-filter post-vector-search), object storage for large blobs (never store raw content in the vector DB), and read replicas / cache in front of all hot paths.

---

## 19. Security

### 19.1 Threats & Defenses

| Threat | Defense |
|---|---|
| Prompt injection in retrieved documents | Injection-pattern scanner (heuristic + classifier) at Evidence Verification (§14); retrieved content is always wrapped/delimited and never treated as instructions by the LLM prompt template |
| Malicious web pages | Sandboxed fetch/extraction, strip scripts, authority-score gate before use, no execution of any fetched content |
| Poisoned embeddings/knowledge | Provenance tracking, anomaly detection on sudden authority/content shifts, human-review queue for flagged sources |
| Malicious skills/code retrieved | Code retrieval results are never auto-executed; execution stays behind the Agent's separate tool-execution sandbox with its own review gate |
| Data exfiltration via retrieval | Egress filtering on any web/tool retriever; output scanning before it leaves the trust boundary |
| Cross-project / cross-tenant leakage | Tenant ID is a mandatory SQL pre-filter on every query path, enforced at the retriever interface level, not just application logic |
| Permission bypass | Permission check gate (§14.1) is first in Evidence Verification and also duplicated at index-query time (defense in depth) |
| Tenant isolation | Physically or logically partitioned indexes per tenant for regulated/high-sensitivity deployments |

### 19.2 Permission Chain

```
User Permission → Agent Permission → Project Permission → Document Permission → Field Permission
```

Enforced as an AND-chain: a candidate is only eligible if it passes every link. This check happens **before** semantic scoring (cheapest-first: don't waste a rerank cycle on content that will be discarded) and again immediately before context injection (defense in depth against a stale permission cache).

---

## 20. Observability

### 20.1 Logged Fields (per retrieval operation)

```
query, rewritten_query, retriever, source, candidate_count, ranking, scores,
reranking_stage_scores, selected_documents, token_cost, latency_ms, llm_calls,
evidence_confidence, final_answer_ref, outcome, retrieval_success, plan_id, task_id
```

### 20.2 OpenTelemetry-Compatible Trace

```
Span: Task
 └─ Span: Query
     └─ Span: QueryRewrite
     └─ Span: RetrieverA (attributes: source, candidate_count, latency, cost)
     └─ Span: RetrieverB
     └─ Span: Fusion (attributes: fusion_method, input_count, output_count)
     └─ Span: Reranker (attributes: stage, model, input_count, output_count)
     └─ Span: EvidenceVerification (attributes: rejected_count, contradiction_count)
     └─ Span: LLM (attributes: tokens_in, tokens_out, model)
     └─ Span: Decision (attributes: sufficiency_score, action)
     └─ Span: Outcome (attributes: success, reward)
```

Every span carries `task_id`/`trace_id` correlation, exported to a standard OTel collector → any compatible backend (Jaeger/Tempo/etc.). This trace is what makes "why did the agent retrieve X and not Y" and "why is this task slow/expensive" answerable without guesswork, and is the raw material the Retrieval Policy Learner (§16) consumes.

---

## 21. Evaluation

| Category | Metrics |
|---|---|
| Retrieval | Recall@K, Precision@K, MRR, NDCG, Hit Rate, Coverage, Diversity |
| Agent | Task Success Rate, Retrieval Success Rate, Evidence Sufficiency, Answer Groundedness, Citation Accuracy, Hallucination Rate |
| System | P50/P95/P99 latency, tokens/task, LLM calls/task, retrieval calls/task, cost/task |
| Self-improvement | Retrieval success improvement (Δ over time), task success improvement, token reduction, latency reduction, failure recovery rate, experience reuse rate |

**Benchmark methodology:**
- **Offline**: curated gold-labeled query/document sets per need_type (factual, code, multi-hop, temporal, contradiction) — regression-tested on every router/ranker deploy.
- **Online**: shadow evaluation (new policy runs in parallel, not shown to user, compared on the same live traffic) before canary rollout (small % of real traffic) before full promotion — with automatic rollback (§16.4) if canary metrics regress beyond threshold.
- **Held-out task suites**: periodic replay of historical tasks against the current system to detect silent regressions in groundedness/citation accuracy as the index/models evolve.

---

## 22. Recommended Production Tech Stack

| Layer | Recommended default | Alternatives | Notes |
|---|---|---|---|
| Embedding | Open-weight sentence-transformer family (deployed self-hosted) or a managed embedding API | Domain fine-tuned model for code | Version-stamp embeddings on the Knowledge Object; support N models concurrently during migration |
| Reranking | Small cross-encoder (self-hosted) for stage 4; LLM only for stage 5, capped at ≤20 candidates | Managed rerank API | Cost dominates here — keep candidate count small before this stage |
| Vector DB | **Qdrant** (self-hosted, good filtering + payload support, simple ops) as default | **Milvus** (larger-scale, more ops overhead), **pgvector** (when you want vector search inside the same Postgres as your metadata, lowest ops complexity, best for <10M vectors), **FAISS** (library, not a service — good for embedded/offline/local-first deployments, not for multi-tenant production) | Choose pgvector first for low-resource/local deployments; graduate to Qdrant/Milvus at scale |
| Search Engine | **OpenSearch** (BM25 + SPLADE-style sparse support, mature ops tooling) | Elasticsearch (license considerations), Tantivy/Meilisearch (lighter weight, good for local/small deployments) | |
| Graph DB | **Neo4j** for rich multi-hop/Cypher use cases | Postgres + a graph extension (e.g. AGE) if you want to avoid a second database for small graphs | Only introduce a dedicated graph DB once multi-hop queries are a measured, frequent need — don't add complexity speculatively |
| SQL | **PostgreSQL** | — | Source of truth for identity/permissions/metadata (§12.2); also viable for vector (pgvector) and lightweight graph (AGE) at small-to-mid scale, minimizing the number of systems to operate |
| Object Storage | S3-compatible (AWS S3 / MinIO for self-hosted) | — | Raw content, PDFs, images, large code blobs |
| Cache | **Redis** | — | Query cache, semantic cache, hot Knowledge Objects, bandit state |
| Message Queue | Kafka (high volume) or a lighter broker (RabbitMQ/SQS) for smaller deployments | — | Async/incremental indexing, feedback event stream |
| Workflow Engine | Temporal (or equivalent durable-execution engine) | Simple queue+worker for smaller scale | Orchestrates the multi-round Agentic Retrieval Controller reliably, with retries/timeouts as first-class |
| Observability | OpenTelemetry + Prometheus/Grafana + a trace backend (Jaeger/Tempo) | — | §20 |
| Crawler | Self-hosted headless-browser fetcher with strict domain allow/deny lists | Managed web-search/crawl API | Security posture (§19) applies regardless of source |
| Document Parsing | Layout-aware PDF/table extraction library (e.g. a Docling/Unstructured-class tool) | — | Feeds the multimodal retriever (§5.3) |
| Code Indexing | tree-sitter (AST) + ctags/LSP (symbols) + a git-aware indexer for history/blame | — | Feeds `CodeRetriever` |

**Default stack for a lean/local-first deployment:** Postgres (+pgvector, +AGE for light graph needs) + Redis + OpenSearch (or Tantivy/Meilisearch) — three systems total, minimal ops. **Graduate** to Qdrant/Milvus + Neo4j + Kafka + Temporal as scale/multi-tenancy/throughput demand it. Do not adopt the "graduated" stack on day one — operational complexity is a real cost (§17 doesn't list this as an anti-pattern, but over-engineering the stack for anticipated-not-actual scale is a common self-inflicted one).

---

## 23. API Specification

### 23.1 External APIs

```
POST /retrieval/plan
  body: { taskId, goal, agentState, budget }
  → { needGraph, subqueries[], estimatedCost }

POST /retrieval/search
  body: { query, filters, retrievers?, topK, budget }
  → { candidates: Candidate[], perRetrieverStats }

POST /retrieval/rerank
  body: { query, candidates: Candidate[], stage }
  → { ranked: Candidate[] }

POST /retrieval/verify
  body: { candidates: Candidate[], permissions, taskTimestamp }
  → { verified: VerifiedEvidence[], rejected: {id, reason}[] }

POST /retrieval/context
  body: { evidence: VerifiedEvidence[], tokenBudget, needTypes }
  → { context: string, allocation: Record<string, number>, citations: Citation[] }

POST /retrieval/feedback
  body: RetrievalFeedbackEvent
  → { accepted: true }
```

### 23.2 Internal Interfaces

```typescript
interface QueryPlanner   { plan(goal, state): InformationNeedGraph }
interface RetrievalRouter{ route(query, state, budget): RetrievalPlan }
interface Reranker       { rerank(query, candidates, stage): Candidate[] }
interface EvidenceVerifier{ verify(candidates, permissions): VerifiedEvidence[] }
interface ContextBuilder { build(evidence, budget, needTypes): Context }
interface MemoryStore    { get(kind, key): Memory[]; put(kind, memory): void }
interface ExperienceStore{ findSimilar(task): Trajectory[]; record(trajectory): void }
interface RetrievalEvaluator { score(traceId): Metrics }
interface RetrievalPolicy{ getWeights(needType): Weights; update(feedback): void }
```

---

## 24. Database / Index Design

| Data | Store | Why |
|---|---|---|
| `documents`, `chunks`, `document_versions`, `source_metadata`, `permissions` | SQL (Postgres) | Transactional integrity, permission joins, versioning queries |
| `entities`, `relations` | Graph DB (Neo4j) or SQL+AGE | Multi-hop traversal performance |
| `embeddings` | Vector DB | ANN index structures (HNSW/IVF) not efficient in row-store SQL at scale |
| `memories` (working/semantic/episodic/procedural) | SQL for structured fields + Vector DB for semantic recall | Mixed access pattern: exact lookup by session/user + similarity search |
| `experiences`, `trajectories` | SQL for structured trajectory metadata + Object Storage for full trajectory logs + Vector DB for task-embedding similarity | Trajectories are large and mostly append-only |
| `retrieval_logs`, `retrieval_feedback` | Append-only store (columnar/OLAP-friendly, e.g. partitioned Postgres or a dedicated analytics store) | High write volume, analytical read pattern for the Policy Learner |

Representative schema fragment:

```sql
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  type TEXT NOT NULL,
  source_uri TEXT NOT NULL,
  authority REAL DEFAULT 0.5,
  quality_score REAL DEFAULT 0.5,
  version TEXT,
  tenant_id UUID NOT NULL,
  acl TEXT[],
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  valid_from TIMESTAMPTZ,
  valid_to TIMESTAMPTZ         -- NULL = current
);
CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_validity ON documents(valid_from, valid_to);

CREATE TABLE retrieval_logs (
  trace_id UUID,
  task_id UUID,
  query TEXT,
  retriever TEXT,
  candidate_count INT,
  latency_ms INT,
  token_cost INT,
  created_at TIMESTAMPTZ
) PARTITION BY RANGE (created_at);

CREATE TABLE retrieval_feedback (
  task_id UUID,
  candidate_id UUID,
  cited BOOLEAN,
  task_success BOOLEAN,
  task_reward REAL,
  created_at TIMESTAMPTZ
);
```

---

## 25. Temporal RAG & Memory / Experience RAG (Summary Cross-Reference)

*(Full mechanics integrated into §6, §11, §13–16 above; summarized here for completeness per the deliverable list.)*

- **Temporal**: ranking includes `freshness_score` (§14.3) combined with query temporal-intent classification ("current API" → `valid_to IS NULL` filter + high freshness weight; "as of 2024" → `valid_from/valid_to` range filter, freshness weight suppressed). Document versioning is a first-class SQL concern (§24), not a vector-store afterthought.
- **Memory-Aware RAG**: the Router treats `MemoryRetriever` as a mandatory low-cost first check for tasks referencing "this project/user/session" — working memory is checked before any external retrieval (cheapest possible source, §18), semantic/episodic/procedural memory are queried in parallel with external sources when the task references past interactions or established preferences (e.g., "deploy service X" → pull preferred deployment strategy from procedural memory alongside doc retrieval).
- **Experience RAG**: retrieval of similar past trajectories is outcome-aware and failure-aware — successful and failed trajectories are both retrievable, but strategy is *extracted* (what worked, what to avoid) rather than the trajectory being replayed verbatim, via an LLM-assisted "strategy extraction" step that compresses a trajectory into reusable procedural knowledge, stored back as a `Skill`/`Solution` Knowledge Object. Experience relevance decays over time and is invalidated when the underlying system it describes changes materially (detected via a linked `dependencies` change on the referenced Knowledge Objects).

---

## 26. Failure Modes and Recovery Strategies

| Failure | Detection | Recovery |
|---|---|---|
| Retriever timeout/outage | `healthCheck()` failure, per-retriever circuit breaker | Router excludes the source for a cool-down window, degrades to remaining sources, logs partial-plan execution |
| Empty result set across all sources | candidate_count == 0 post-fusion | Escalate: broaden filters → query expansion → exploratory mode → surface "insufficient information" to the agent rather than fabricating |
| Runaway iterative retrieval | round/token/cost ceiling hit | Hard stop, return best-available evidence with an explicit low-sufficiency flag to the LLM/agent |
| Index staleness (write-index lag) | freshness metadata vs. known write timestamp mismatch | Read-your-writes path for critical updates (direct SQL check bypassing stale ANN index when object was just modified in this session) |
| Contradictory evidence with no way to resolve | contradiction_score high on all candidates for a node | Surface uncertainty explicitly in context (§11) rather than silently choosing a side; flag for human-in-the-loop if task criticality warrants |
| Poisoned/malicious content detected | injection scanner / anomaly detector fires | Quarantine object, exclude from all future retrieval pending review, alert |
| Router misroute (wrong source selected) | low sufficiency + high cost after execution | Logged as negative feedback (§16), triggers bandit/classifier update; short-term fallback to LLM routing tier for similar future queries |
| Permission-check failure mid-pipeline | ACL join fails / stale permission cache | Fail closed (exclude candidate), do not fail open; alert if failure rate spikes (possible systemic ACL bug) |

---

## 27. Implementation Roadmap

| Phase | Scope | Key deliverables |
|---|---|---|
| **1. Minimal production RAG** | Single-source (vector) retrieval, basic chunking, fixed top-K | `Retriever` interface, `DenseVectorRetriever`, Postgres+pgvector, basic `/retrieval/search`, Recall@K/NDCG offline eval harness |
| **2. Hybrid retrieval** | Add lexical + structured filtering, RRF fusion | `LexicalRetriever`, `StructuredRetriever`, fusion module, permission pre-filter (§19) |
| **3. Reranking** | Multi-stage funnel, MMR diversity | Cross-encoder reranker, `/retrieval/rerank`, diversity/redundancy metrics |
| **4. Agentic retrieval** | Query planning DAG, router, sufficiency-gated iteration | `QueryPlanner`, `RetrievalRouter` (rule+classifier tiers), Sufficiency Model, `/retrieval/plan` |
| **5. Graph + Memory** | Graph retrieval, 4-type memory integration | `GraphRetriever`, `MemoryStore`, entity/relation schema, two composed traversal patterns (§13) |
| **6. Experience RAG** | Trajectory logging, experience retrieval + strategy extraction | `ExperienceStore`, trajectory schema, strategy-extraction pipeline |
| **7. Self-improving retrieval** | Feedback loop, bandit routing, LTR reranking | `/retrieval/feedback`, Retrieval Policy Learner, canary/shadow eval pipeline (§16.4) |
| **8. Large-scale distributed retrieval** | Sharding, multi-tenant isolation, full observability, cost governor | Sharded vector indexes, OTel tracing (§20), cost-aware routing (§18.3), Temporal-orchestrated multi-round controller |

Each phase carries its own acceptance criteria (§21 metrics thresholds), regression test suite (offline gold sets), and a go/no-go gate on the Observability dashboards before promotion to the next phase — no phase ships without its corresponding evaluation harness in place.

---

## 28. Acceptance Criteria (System-Level)

- Retrieval never returns permission-violating content (0 tolerance — hard gate, tested via adversarial permission fuzzing).
- P95 end-to-end retrieval latency within task-class SLA (e.g. ≤2s for interactive, ≤30s for deep research mode).
- Sufficiency-gated iteration terminates within `max_rounds` on 100% of executions (no unbounded loops — enforced structurally, not just by convention).
- Citation accuracy (claims traceable to retrieved evidence) above a defined floor on the held-out groundedness benchmark, tracked release-over-release with no regression tolerance.
- Router/ranker updates pass shadow + canary evaluation before promotion, with automatic rollback wired and tested.
- Cost-per-task trends flat-to-declining as corpus size grows (validates that the cheap-first funnel and caching are actually load-bearing, not just present).

---

*This specification is intended as an implementable engineering blueprint. Each numbered interface, schema, and algorithm above is meant to be taken directly into a design-review / RFC process by the owning engineering team, with Phase 1 (§27) as the concrete starting point.*
