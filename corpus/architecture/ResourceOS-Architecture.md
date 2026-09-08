# ResourceOS: A Unified Resource Operating System for Large-Scale Autonomous Coding Agents

**Architecture Document v1.0**
**Classification:** Reference Architecture — Infrastructure Layer
**Author:** Principal Software / AI Systems Architecture

---

## 1. Executive Summary

ResourceOS is the infrastructure layer that lets a coding agent operate over an unbounded population of skills, tools, MCP servers, agents, workflows, projects, references, memories, templates, scripts, artifacts, policies, prompts, and plugins — collectively **Resources** — without ever placing that population in the LLM's context window.

The central design bet is that **capability discovery is a search-engine problem, not a prompt-engineering problem**. Instead of enumerating tools in a system prompt or dumping SKILL.md files into context, ResourceOS treats every resource as an indexed, versioned, permissioned object with a cheap identity layer and an expensive runtime layer, and interposes a router that resolves *task → capability → ranked candidates → progressively loaded resource → sandboxed execution*. Context is a scarce, budgeted resource allocated by an explicit allocator, not a dumping ground.

At small scale (tens of resources) this looks like overengineering. At the target scale (10⁴–10⁶ resources, thousands of concurrent tasks) it is the only architecture that keeps token cost, latency, and tool-selection accuracy bounded as the resource population grows. The document below specifies the resource model, registry, capability graph, hybrid retrieval pipeline, router APIs, security model, storage architecture (from single-machine SQLite+FAISS up to a distributed enterprise topology), database schema, directory layout, and a worked end-to-end execution trace, followed by token budgets, scalability targets, trade-off analysis, and an implementation roadmap.

**Core numeric targets** (elaborated in §32–33): P50 candidate-resolution latency < 150ms at 100K resources; top-5 retrieval precision ≥ 0.85; < 2% of task-context tokens spent on resource metadata for typical tasks; zero cross-project resource leakage; every resource execution traced end-to-end.

---

## 2. Problem Definition

A simple chatbot has a handful of tools and can afford to declare them all in a system prompt. An autonomous coding agent operating as a **software factory** does not have this luxury:

- **Population scale.** A large organization's agent surface — internal skills, per-repo tooling, MCP servers for every SaaS integration, generated workflows, historical playbooks — reaches thousands to millions of distinct resources within a few years of accumulation.
- **Heterogeneity.** A "resource" might be a 200-token tool schema, a 5,000-token SKILL.md with scripts and templates, a stateful long-running MCP session, or a 50MB project workspace. They cannot share one loading strategy.
- **Context is the bottleneck, not compute.** LLM context windows are large but not unbounded, and cost/latency scale with tokens actually sent, not resources that exist. Every token spent describing resources the task doesn't need is a token not spent on reasoning, code, or task state — and it measurably degrades tool-selection accuracy (needle-in-haystack degradation is well documented as context grows).
- **Selection errors compound.** In a single-tool-call chatbot a wrong tool choice is a minor annoyance. In an autonomous multi-step coding agent, a wrong skill or tool selection three steps into a plan can corrupt a repository, leak a credential, or silently produce a wrong artifact that downstream steps build on.
- **Security cannot be delegated to the model.** A model that can be talked into calling a destructive tool via clever phrasing is not a safe foundation for an agent with filesystem, network, and credential access. Authorization must be enforced by policy outside the model's persuadable surface.
- **The system must improve, not just operate.** Static tool sets rot: duplicates accumulate, some resources silently degrade (an API changes, a script bit-rots), and naive popularity-based ranking creates feedback loops that entrench mediocre-but-frequently-used resources over better alternatives.

The architectural question this document answers: **how does an agent efficiently discover and safely activate the right small subset of a massive, heterogeneous, evolving resource population, for every task, at bounded token cost and bounded latency, with auditable safety guarantees?**

---

## 3. Design Principles

1. **Unify the model, specialize the runtime.** One Resource abstraction, many Resource *type handlers*. (§4 explains why.)
2. **Identity is cheap; content is expensive.** Every resource has a near-free identity/metadata layer (§9) that is always searchable, and an expensive full-definition/runtime layer loaded only after it is selected.
3. **Capability, not resource, is the unit of reasoning for the agent.** The agent thinks in terms of "I need dependency-audit capability," not "I need the `snyk-cli-v3` tool." Resolution from capability to concrete resource is the router's job (§6, §10).
4. **Context is budgeted, not appended.** ContextOS (§15) allocates a fixed token budget per stage and evicts/compresses rather than growing unbounded.
5. **Search before you read.** Structured filters and cheap indexes eliminate the vast majority of candidates before any embedding or reranking model runs, and long before any resource content is loaded into the LLM.
6. **Policy is enforced outside the model.** The model requests; the Policy Engine and sandbox decide. No natural-language jailbreak can grant a permission the policy layer didn't already grant.
7. **Everything is versioned and provenance-tracked.** A resource without a version and a source is not trustworthy enough to execute against a production repository.
8. **Reputation is earned, not assumed, and is resistant to popularity feedback loops** (§21).
9. **Failure is a first-class state**, not an exception path bolted on afterward (§24).
10. **Every stage is observable.** If a task fails, there must be a trace showing exactly which resources were considered, why they were ranked as they were, which were loaded, and what happened at execution (§24).
11. **Prefer deterministic routing where possible; reserve LLM judgment for genuinely ambiguous ranking/composition decisions.** Determinism is cheaper, faster, and auditable; LLM routing is reserved for the residual ambiguity structured methods can't resolve (§34).

---

## 4. System Architecture (Overview)

ResourceOS sits between the agent's reasoning loop and the universe of resources. At the top level:

```
                    ┌───────────────────────────────────────────────────┐
                    │                    AGENT KERNEL                    │
                    │   (task loop, planning, LLM calls, tool-call I/O)  │
                    └───────────────────────┬───────────────────────────┘
                                             │  resource.search/resolve/load/execute
                                             ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │                              RESOURCEOS                                  │
   │                                                                          │
   │   ┌───────────┐   ┌────────────┐   ┌─────────────┐   ┌───────────────┐  │
   │   │ CapabilityOS│→ │ Resource   │→ │  Retrieval   │→ │  Policy Engine │  │
   │   │ (taxonomy,  │  │ Router     │  │  Engine      │  │ (authZ, quota, │  │
   │   │  graph)     │  │ (orchestr.)│  │ (hybrid RAG) │  │  sandbox rules)│  │
   │   └───────────┘   └─────┬──────┘   └──────┬───────┘   └───────┬───────┘  │
   │                          │                 │                   │          │
   │                          ▼                 ▼                   ▼          │
   │                   ┌─────────────────────────────────────────────────┐    │
   │                   │              RESOURCE REGISTRY                   │    │
   │                   │  (metadata store, versions, deps, permissions,   │    │
   │                   │   quality scores — see §9, §28)                  │    │
   │                   └──────────────────────┬──────────────────────────┘    │
   │                                          │                               │
   │            ┌─────────────────────────────┼─────────────────────────┐    │
   │            ▼                              ▼                          ▼    │
   │     ┌─────────────┐              ┌───────────────┐          ┌─────────────┐│
   │     │  ContextOS   │              │   ProjectOS    │          │  MemoryOS   ││
   │     │ (budgeting,  │              │ (workspace,    │          │ (hierarchical││
   │     │  assembly)   │              │  state, git)   │          │  memory)    ││
   │     └─────────────┘              └───────────────┘          └─────────────┘│
   │                                                                          │
   │   ┌────────────────────────────────────────────────────────────────┐    │
   │   │                       EXECUTION RUNTIME                          │    │
   │   │        (sandbox, MCP clients, script runners, tool adapters)     │    │
   │   └────────────────────────────────────────────────────────────────┘    │
   │                                                                          │
   │   ┌────────────────────────────────────────────────────────────────┐    │
   │   │        OBSERVABILITY · REPUTATION · SELF-IMPROVEMENT LOOP         │    │
   │   └────────────────────────────────────────────────────────────────┘    │
   └─────────────────────────────────────────────────────────────────────────┘
```

Everything below expands each box: its data model, algorithms, APIs, failure modes, and scale behavior.


---

## 5. Resource Model — The Unified Abstraction

### 5.1 Why unify instead of building SkillManager / ToolManager / ProjectManager / etc.

Independent managers seem simpler at first but fail at scale for four concrete reasons:

1. **N× duplicated infrastructure.** Search, versioning, permissions, dependency resolution, caching, and observability all have to be built and maintained *once per manager type* instead of once. Every new resource type (say, "Prompt Library" or "Runbook") means another bespoke manager rather than a new row in one schema.
2. **Cross-type queries become impossible or bespoke.** A real task like "audit this Python project's security" needs to consider Skills, Tools, MCP servers, and References *together*, ranked on the same scale. If each type lives in a separate store with separate scoring, there is no principled way to compare a Skill's relevance score against a Tool's — you get ad hoc merge logic per pair of types, which is O(N²) in the number of types.
3. **Composition and dependency graphs need a common node type.** A Skill depends on a Tool which depends on an MCP server which references Documentation which produces an Artifact. If these are different object models with different IDs and different stores, the dependency graph (§14) cannot be a single graph — it becomes a federation of graphs stitched together with fragile glue code.
4. **Policy, lifecycle, and reputation are structurally identical across types.** Permissions, lifecycle state machines (DISCOVERED → REGISTERED → ... → ARCHIVED), and success/failure statistics apply the same way to a Skill as to an MCP server. Building this once, generically, and letting type-specific behavior live in a thin **Resource Type Handler** is both less code and more consistent.

The unification is at the **model, registry, index, and lifecycle** layer. It is explicitly *not* a unification at the **runtime** layer — a Skill and an MCP server are activated and executed completely differently (§5.3). Unifying identity while specializing runtime is the crux of the design.

### 5.2 The Generic Resource Schema

Every resource — regardless of type — is represented by this envelope. Type-specific detail lives in `type_metadata`, validated against a per-type JSON Schema registered in `capabilities.type_schemas`.

```yaml
# Canonical Resource envelope (stored as the "L1 metadata" row — see §9)
id: "res_9f21c3a0b7"                     # ULID, globally unique, immutable
type: "skill"                            # skill|tool|tool_family|mcp|agent|workflow|
                                          # reference|knowledge|memory|project|
                                          # template|script|artifact|policy|prompt|plugin
name: "python-security-audit"
display_name: "Python Security Audit"
description: >
  Runs SAST, dependency vulnerability scanning, and secret detection
  across a Python codebase and produces a prioritized findings report.
version: "2.3.1"                          # semver
lifecycle_state: "active"                 # see §16
scope: "org"                              # global|org|team|project|user|session
ownership:
  team: "platform-security"
  maintainer: "security-tooling@org"
source:
  origin: "internal-registry"             # internal-registry|github|marketplace|generated
  uri: "git+https://github.com/org/skills/python-security-audit"
  commit: "a91f3e2"
provenance:
  created_by: "human"                     # human|agent|imported
  verified: true
  attestation: "sha256:....signed"

capabilities:                             # capability IDs this resource satisfies (§6)
  - "security.sast.python"
  - "security.dependency-audit.python"
  - "security.secret-detection"

tags: ["python", "security", "sast", "audit", "ci"]

interface:                                # what calling it looks like (L2, §9)
  invocation: "skill"                     # skill|function|mcp_tool|workflow|http
  input_schema: {"$ref": "schemas/psa_input.json"}
  output_schema: {"$ref": "schemas/psa_output.json"}

dependencies:
  requires:
    - {resource: "tool:bandit-cli", version: ">=1.7.0"}
    - {resource: "tool:pip-audit", version: ">=2.6.0"}
  optional:
    - {resource: "mcp:snyk", fallback: "tool:pip-audit"}
  produces_artifact_types: ["security-report.json", "sarif"]

compatibility:
  runtimes: ["python:3.9-3.12"]
  os: ["linux", "macos"]
  conflicts_with: ["skill:legacy-py2-audit"]

permissions:
  filesystem: {read: ["project_root"], write: ["project_root/.reports"]}
  network: {egress: ["api.snyk.io"]}
  secrets: ["SNYK_TOKEN"]
  max_execution_seconds: 600

security_policy:
  sandbox: "container"                    # none|process|container|vm
  trust_tier: "verified-internal"         # §17
  requires_review_above_risk: "medium"

quality_metrics:
  success_rate_30d: 0.94
  avg_user_acceptance: 0.88
  security_incidents: 0

usage_statistics:
  invocations_30d: 1204
  unique_projects_30d: 87
  last_used_at: "2026-08-30T10:04:00Z"

cost:
  avg_token_cost: 3100
  avg_dollar_cost: 0.014
latency:
  p50_ms: 4200
  p95_ms: 11800
reliability:
  uptime_30d: 0.998
  mtbf_hours: 720

type_metadata:                            # type-specific block, schema-validated
  skill_manifest_path: "skill.yaml"
  instructions_path: "SKILL.md"
```

This is the **only** schema the Registry, Router, and Retrieval Engine reason about generically. Type Handlers (§5.3) interpret `type_metadata` and `interface` to know how to actually load and run the thing.

### 5.3 Resource Hierarchy and Runtime Character

```
Resource
├── Skill            executable, contextual, persistent
├── Tool              executable, stateless-call, persistent
├── Tool Family        informational (grouping only, not directly invoked)
├── MCP Server         executable, stateful (session), persistent, external
├── Agent               executable, stateful, persistent (sub-agent spec)
├── Workflow            executable, stateful (multi-step), persistent
├── Reference            informational, persistent, low-mutability
├── Knowledge            informational, persistent, derived (from References)
├── Memory                contextual, stateful, semi-ephemeral (§12)
├── Project               stateful, persistent, isolated container
├── Template              informational/generative, persistent
├── Script                executable, stateless-call, persistent
├── Artifact              informational, persistent, immutable-once-produced
└── Policy                contextual (governs others), persistent, high-authority
```

Not all resources are represented identically at runtime — this is deliberate:

| Type | Executable? | Contextual? | Informational? | Stateful? | Persistent? | Ephemeral? | Runtime shape |
|---|---|---|---|---|---|---|---|
| Skill | Yes | Yes (instructions enter context) | Partially | No (per-invocation) | Yes | — | Loaded instructions + invoked scripts/tools |
| Tool | Yes | No (schema only in context) | No | No | Yes | — | Single function call, in/out schema |
| Tool Family | No | No | Yes (grouping) | No | Yes | — | Pure index node, never "run" |
| MCP Server | Yes | No | No | **Yes** (session/connection) | Yes | — | Long-lived client session, many tool calls |
| Agent | Yes | Yes (its own context) | No | Yes | Yes | — | Spawns sub-agent loop with own ContextOS |
| Workflow | Yes | Partially | No | Yes (multi-step) | Yes | — | DAG of resource activations |
| Reference | No | Yes (chunks retrieved) | Yes | No | Yes | — | Chunked, embedded, retrieved by relevance |
| Knowledge | No | Yes | Yes | No | Yes | — | Derived/summarized from References |
| Memory | No | Yes | No | Yes | Yes (tiered) | Some tiers ephemeral | Time/importance-scored, decays |
| Project | No (container) | Yes (state summarized) | No | **Yes** | Yes | — | Isolated workspace + its own sub-registry view |
| Template | No | Yes (rendered into context) | Yes | No | Yes | — | Parameterized text/code stamped out |
| Script | Yes | No | No | No | Yes | — | Executed in sandbox, stdout/exit code returned |
| Artifact | No | Sometimes | Yes | No | Yes | — | Output object, immutable, addressable |
| Policy | No | Yes (as constraints, not text) | No | No | Yes | — | Evaluated, not "read" by the LLM |

The critical asymmetry: **Tools and Tool Families are never read into context as prose** — only their compact schema is. **Skills, References, and Knowledge are the primary consumers of context budget.** **Policies are never shown to the LLM as instructions to follow voluntarily** — they are enforced structurally by the Policy Engine (§17), because an instruction the model merely "reads" can be argued around; a permission the runtime never grants cannot be.


---

## 6. CapabilityOS

### 6.1 Identity vs. Capability

**Resource identity** answers "what is this specific thing" (`tool:bandit-cli@1.7.2`). **Capability** answers "what can be done" (`security.sast.python`). The agent should reason almost exclusively in capability terms; identity is an implementation detail the Router resolves.

```
Task: "Audit this Python project's security."
   → Intent:              security_audit(target=python_project)
   → Capability:           security.sast.python  +  security.dependency-audit.python
                            + security.secret-detection
   → Capability Graph:     expand aliases/children (SAST → bandit-class, semgrep-class...)
   → Candidate Resources:  {skill:python-security-audit, tool:bandit-cli, tool:semgrep,
                             mcp:snyk, tool:pip-audit, tool:gitleaks, ...}
   → Resource Ranking:     score by capability-match + quality + reputation + fit
   → Selected:             skill:python-security-audit (composite, pulls in bandit+pip-audit)
   → Execution
```

This indirection is what allows the resource population to grow 100× without the agent's reasoning surface growing at all — the agent still just says "I need `security.dependency-audit`."

### 6.2 Capability Taxonomy & Hierarchy

Capabilities form a DAG (not a strict tree — a capability may have multiple valid parents), rooted at broad domains and refining to specific, directly-matchable leaves:

```
software-development
├── coding
│   ├── python  ├── javascript  ├── rust  ├── go
├── testing
│   ├── unit-testing  ├── integration-testing  ├── fuzzing  ├── mutation-testing
├── security
│   ├── sast            (children: sast.python, sast.js, sast.go...)
│   ├── dependency-audit
│   ├── secret-detection
│   ├── dast
│   └── compliance-scan
├── deployment
│   ├── docker  ├── kubernetes  ├── ci-cd
├── version-control
│   ├── git.commit  ├── git.branch  ├── github.pr  ├── github.issue
└── documentation
    ├── api-docs-generation  ├── changelog-generation
```

Each capability node is itself a lightweight record:

```json
{
  "id": "security.dependency-audit.python",
  "parents": ["security.dependency-audit", "coding.python"],
  "aliases": ["python vuln scan", "pip audit", "dependency vulnerability check"],
  "description": "Identify known-vulnerable third-party Python packages.",
  "composable_with": ["security.sast.python", "reporting.sarif"],
  "conflicts_with": [],
  "version_scheme": "capability-contract-v1"
}
```

- **Aliases** absorb the vocabulary mismatch between how a task is phrased and how the capability is named — matched via the same hybrid retrieval used for resources (§8), not hardcoded synonym lists.
- **Dependencies** at the capability level ("dependency-audit composes with reporting") let the Composition engine (§19) pre-filter which resources are even plan-compatible before scoring.
- **Inheritance**: a resource tagged with `security.sast.python` automatically satisfies queries for the parent `security.sast` and `coding.python`-adjacent tasks at reduced confidence — inheritance is a *ranking discount*, not a hard match, to avoid false positives (a Python-only SAST tool should rank low for a Rust task even though both are children of `security.sast`... rather, `security.sast.rust` and `security.sast.python` are siblings, not parent/child, precisely so this discount is correctly scoped).
- **Conflicts**: two capabilities marked mutually exclusive (e.g., `deployment.blue-green` vs `deployment.recreate-strategy`) prevent the Composer from silently selecting both in one workflow.
- **Versioning**: a capability contract can version independently of any resource implementing it (e.g., `security.sast.python@v2` adds a required `severity_taxonomy` field to output) — resources declare which contract version(s) they satisfy, and the Router filters on contract compatibility with the task's requirements.

### 6.3 Capability Graph Construction & Maintenance

The graph is stored as an adjacency structure in the relational store (`capabilities`, `capability_edges` — §28) with a materialized closure table for fast ancestor/descendant queries at scale (avoids recursive CTEs on the hot path). It is built and maintained by:

1. **Manual curation** for top-level domains and stable leaves (security, testing, deployment) — these change rarely and get human review.
2. **Semi-automated extraction** when a new resource is registered: the registration pipeline proposes capability tags via embedding similarity to existing capability descriptions + LLM-assisted classification, but a proposed *new* capability node requires either a confidence threshold or human/maintainer approval before entering the graph — this prevents capability-graph sprawl from every resource inventing its own vocabulary.
3. **Usage-driven pruning**: capability nodes with zero resources and zero query matches after N days are flagged for archival, not deletion (§16).


---

## 7. Resource Registry

### 7.1 Metadata vs. Content

**The Registry stores metadata and references, never bulk content.** A Skill's SKILL.md, scripts, and templates live on the filesystem (or object storage at scale); the Registry stores their path/URI, hash, size, and version — not their bytes. This is non-negotiable for three reasons: (1) the Registry's hot path (search/rank) must stay fast, and scanning multi-KB blobs during a metadata query destroys that; (2) content changes (a script gets patched) shouldn't require a schema migration; (3) it lets L0–L2 loading (§9) work at all — you cannot have a "metadata-only" load tier if metadata and content are the same row.

The one exception: resources whose *entire content* is small and structured (a Prompt template, a short Policy) may inline content directly in `type_metadata` when it is under ~2KB, since the indirection cost would exceed the content cost.

### 7.2 Registry Responsibilities

| Function | Description |
|---|---|
| Registration | Validate schema, assign ID, run capability classification, run duplicate/conflict detection (§18), set initial lifecycle state |
| Discovery | Serve as the system of record queried by the Retrieval Engine's structured-filter stage |
| Lookup | O(1) fetch by ID at any load level (§9) |
| Versioning | Store version history, enforce semver compatibility on dependency edges |
| Validation | Schema validation on write; periodic re-validation (health checks, §16) |
| Dependency resolution | Expose `resolve_dependencies(resource_id)` returning a resolved dependency tree or conflict report |
| Capability mapping | Maintain the resource↔capability edge table |
| Permissions | Store and serve the permission/security_policy block consumed by the Policy Engine |
| Lifecycle management | Enforce legal state transitions (§16) |
| Deprecation / Archival | Mark superseded resources, redirect queries to successors, retain for audit |
| Provenance | Immutable record of origin, signer, commit |
| Health status | Last health-check result, current availability |
| Quality scoring | Aggregate reputation inputs (§21) into a queryable `quality_score` |

### 7.3 Metadata Schema — Concrete Example

```json
{
  "id": "res_9f21c3a0b7",
  "type": "tool",
  "name": "github.pull_request.create",
  "family": "github",
  "category": "pull_request",
  "operation": "create",
  "version": "1.4.0",
  "lifecycle_state": "active",
  "capabilities": ["vcs.github.pr.create"],
  "interface": {
    "invocation": "mcp_tool",
    "mcp_server": "mcp:github",
    "input_schema": {
      "type": "object",
      "required": ["repo", "base", "head", "title"],
      "properties": {
        "repo": {"type": "string"},
        "base": {"type": "string"},
        "head": {"type": "string"},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "draft": {"type": "boolean", "default": false}
      }
    },
    "output_schema": {"$ref": "schemas/github_pr.json"}
  },
  "permissions": {"network": {"egress": ["api.github.com"]}, "secrets": ["GITHUB_TOKEN"]},
  "quality_metrics": {"success_rate_30d": 0.99},
  "tags": ["github", "pull-request", "vcs"]
}
```

```yaml
# Same resource, YAML form used in source-controlled registration manifests
id: res_9f21c3a0b7
type: tool
name: github.pull_request.create
family: github
category: pull_request
operation: create
version: 1.4.0
capabilities: [vcs.github.pr.create]
interface:
  invocation: mcp_tool
  mcp_server: "mcp:github"
  input_schema: { $ref: schemas/github_pr_input.json }
permissions:
  network: { egress: [api.github.com] }
  secrets: [GITHUB_TOKEN]
```

---

## 8. Multi-Level Resource Loading

This is the single highest-leverage mechanism for token efficiency. Nothing above **L1** is ever loaded for a resource that isn't a serious candidate; nothing above **L2** is loaded for a candidate that isn't selected.

| Level | Contents | Approx. size | When loaded |
|---|---|---|---|
| **L0 — Identity** | id, type, name, version, lifecycle_state | ~30 tokens | Always resident in the fast index (in-memory / SQLite index), for every resource, at all times |
| **L1 — Metadata** | description, tags, capabilities, quality_metrics, cost/latency, permissions summary | ~150–300 tokens | Loaded for all candidates surviving structured filtering + retrieval (§9), typically 20–200 resources per query |
| **L2 — Interface** | input/output schema, invocation type, dependency list | ~100–500 tokens | Loaded only for the top-K ranked candidates (K≈3–10) presented to the LLM for final selection or directly auto-selected above a confidence threshold |
| **L3 — Full Definition** | full SKILL.md/instructions, examples, template bodies | 1K–20K tokens | Loaded only for the **one (or few) selected** resource(s), right before use |
| **L4 — Runtime Implementation** | actual script bytes, MCP session establishment, container image | N/A (not context tokens — executed, not read) | Loaded by the Execution Runtime at activation time, never enters LLM context except via its *output* |

```
Task
 → Candidate Discovery        (L0 index scan + structured filters:  ~100,000 → ~500 resources)
 → Metadata Retrieval (L1)    (hydrate survivors:                    ~500 → context-free scoring)
 → Candidate Ranking          (hybrid retrieval + rerank:             500 → top 10)
 → Interface Inspection (L2)  (only top 10 loaded into context:        ~2,000 tokens total)
 → Resource Loading (L3)      (only the 1–3 selected:                  ~5,000–15,000 tokens)
 → Execution (L4)             (sandboxed; results, not source, return to context)
```

**Token math at 100,000 resources**: naive "put everything in context" is infeasible outright. The L0–L2 pipeline described above touches perhaps 500 resources computationally but puts only ~2,000 tokens (L2 for top-10) into the LLM's context before selection, and ~5–15K tokens (L3 for the 1–3 selected) after — a >99.9% reduction versus even a "compressed one-line-per-resource" flat listing of the full registry, which alone would be ~1–3M tokens at 100K resources.


---

## 9. Hybrid Resource Retrieval

"Use RAG" is not an architecture. The actual pipeline, in order, with each stage's job being to **cheaply eliminate candidates** before the next, more expensive stage runs:

```
Query (raw task text)
 → 1. Intent Extraction          — classify task type, extract entities (language, target, action)
 → 2. Structured Filters         — SQL WHERE on type, scope, lifecycle_state=active, permission-
                                    compatible, runtime-compatible, project-compatible
                                    (100,000 → ~2,000)
 → 3. BM25 / Full-Text (FTS5)    — lexical match on name/description/tags
                                    (2,000 → ~300, fast, catches exact terms: "bandit", "SARIF")
 → 4. Vector Retrieval (ANN)     — semantic match on description+capability embeddings
                                    (2,000 → ~300, catches paraphrase: "check for leaked keys"
                                     → secret-detection)
 → 5. Capability Graph Expansion — union in resources tagged with matched capability's
                                    ancestors/descendants/aliases (adds recall for graph-adjacent
                                    resources BM25/vector missed)
 → 6. Reciprocal Rank Fusion     — merge BM25 + vector rankings: score(d) = Σ 1/(k + rank_i(d))
                                    across the retrieval lists (k≈60), producing one ranked list
                                    from ~600 deduplicated candidates
 → 7. Dependency Resolution      — for surviving top candidates, verify their required
                                    dependencies are resolvable in this environment; drop if not
 → 8. Permission Filtering       — hard-drop anything the current agent/project identity lacks
                                    grant for (never merely down-rank — this is a security gate)
 → 9. Runtime Availability       — drop resources whose health check is failing / MCP server
                                    unreachable (cached, checked async, not per-query)
 → 10. Historical Success Prior  — fold in P(success | capability, project-type) from
                                    reputation store (§21) as a Bayesian prior multiplied into
                                    the fused score
 → 11. Deduplication              — cluster near-duplicate resources (semantic similarity above
                                    threshold + overlapping capability set) and keep the
                                    highest-scoring representative unless diversity is requested
 → 12. Cross-Encoder Reranking    — a small reranker model scores (task, resource L1-metadata)
                                    pairs directly for the surviving ~20–50 candidates — this is
                                    the step actually allowed to be "expensive" because the set
                                    is now small
 → 13. Confidence Thresholding    — if top result's score exceeds τ_auto, auto-select; if it
                                    falls in [τ_low, τ_auto), present top-K to the LLM/user for
                                    disambiguation; if below τ_low, trigger fallback (§9.1)
 → Top-K Selection
```

### 9.1 Fallback Mechanisms

- **No resource matches** (all scores below τ_low): the Router reports "no capability found," proposes the nearest capability nodes for human/agent clarification, and can optionally hand off to a "propose new resource" workflow (write a script, register a new Skill).
- **Multiple resources match closely** (top-2 within ε of each other): present both at L2 to the selecting agent/LLM with their differentiating metadata (cost, latency, reputation) rather than silently picking one — ambiguity this close is exactly where a one-line LLM judgment call outperforms a hardcoded tiebreak.
- **Confidence is low but non-zero**: widen the query (drop the most restrictive structured filter, or ascend one level in the capability graph) and re-run once before surfacing ambiguity to the agent.
- **A resource fails at execution**: this feeds back into the *reputation* system (§21) and triggers the *failure recovery* graph (§23), not the retrieval pipeline directly — retrieval already made its best call given the information it had.
- **A resource becomes unavailable mid-task**: cached L1/L2 is still usable for re-ranking alternates; the Router re-queries with that resource's ID added to an exclusion set.

### 9.2 Negative Signals

Explicit negative signals prevent popular-but-wrong resources from dominating: repeated user rejection of a suggested resource for a given capability/query pattern is stored and subtracted from future scores for that (query-cluster, resource) pair; resources with recent security incidents or failed health checks get an explicit score penalty independent of their historical success rate, so a previously-good resource doesn't coast on stale reputation after it starts breaking.

---

## 10. Resource Router

The Router is the orchestration surface the Agent Kernel actually calls. It exposes distinct verbs because **collapsing them destroys the ability to reason about, cache, and audit each stage independently** — "just call `use_resource(task)`" hides exactly the cost/latency/security decisions this whole document is about.

| Verb | Purpose | Cheap? | Side effects |
|---|---|---|---|
| `search` | Run the hybrid retrieval pipeline (§9), return ranked L1 candidates | Yes (ms, no LLM by default) | None |
| `inspect` | Load L2 interface for a specific candidate | Yes | None |
| `resolve` | Resolve a capability/resource + its dependency tree into a concrete, version-pinned execution plan | Cheap–moderate | None (pure planning) |
| `load` | Hydrate L3 full definition into the context/execution environment | Moderate (I/O, decompression) | Populates context budget (ContextOS charged) |
| `activate` | Establish runtime state: open MCP session, warm a container, acquire a lock/quota | Expensive | Creates a live handle; consumes runtime resources |
| `execute` | Invoke the activated resource with validated input, inside sandbox/policy constraints | Expensive | The actual side effect (writes, network calls, commits) |
| `release` | Tear down runtime state, return quota, close sessions | Cheap | Frees resources |

### 10.1 Request/Response Schemas

```json
// POST resource.search
{ "query": "audit this python project's security",
  "context": {"project_id": "proj_44a", "capabilities_hint": ["security.*"]},
  "top_k": 10, "include_types": ["skill","tool","mcp"] }

// → response
{ "candidates": [
    {"id": "res_9f21c3a0b7", "type": "skill", "name": "python-security-audit",
     "score": 0.91, "capabilities": ["security.sast.python", "security.dependency-audit.python"]},
    {"id": "res_1a44e", "type": "tool", "name": "bandit-cli", "score": 0.77,
     "capabilities": ["security.sast.python"]}
  ], "confidence": "high", "fallback_triggered": false }

// POST resource.resolve
{ "resource_id": "res_9f21c3a0b7", "project_id": "proj_44a" }
// → response
{ "execution_plan": {
    "primary": "res_9f21c3a0b7",
    "dependencies": [
      {"resource_id": "res_1a44e", "version_pinned": "1.7.2", "status": "available"},
      {"resource_id": "res_2b91f", "version_pinned": "2.6.1", "status": "available"}
    ],
    "conflicts": [], "unresolved": [] } }

// POST resource.activate
{ "resource_id": "res_9f21c3a0b7", "project_id": "proj_44a", "task_id": "task_772" }
// → response
{ "handle": "hdl_88c1", "sandbox": "container:cid_a02f", "expires_at": "2026-09-03T11:20:00Z" }

// POST resource.execute
{ "handle": "hdl_88c1", "input": {"target_path": "/workspace/repo"} }
// → response
{ "status": "success", "output_ref": "artifact:art_5510",
  "summary": "14 findings (2 high, 6 medium, 6 low)", "duration_ms": 4310, "token_cost": 0 }
```

`execute` returns an **output_ref**, not inline bulk output — large results are artifacts (§13) the agent can selectively pull into context, preventing execution results from silently blowing the context budget.


---

## 11. Hierarchical Tool Discovery

With tens of thousands of tools, a flat tool list destroys selection accuracy (entropy grows with the log of the option count, and cross-tool confusion grows worse than linearly as similar operations from different families collide — e.g. `create` appearing under GitHub, Jira, and Linear). The fix is a strict hierarchy that is *never fully expanded into context at once*:

```
Tool Family (e.g. GitHub)             ← L0/L1 only, ~1 line each, always searchable
 └── Tool Category (e.g. Pull Request) ← L1, loaded once family is selected/matched
      └── Tool (e.g. github.pull_request)   ← L1/L2
           └── Operation (create, review, merge, close, comment)  ← L2, the actual callable unit
```

**Why this reduces tool-selection entropy:** instead of choosing 1-of-40,000 flat options, the model (or, preferably, the deterministic router) makes a sequence of much lower-entropy choices: 1-of-200 families (resolved almost always by structured filter + retrieval, not LLM judgment), then 1-of-8 categories within that family, then 1-of-15 operations within that category. Each step has a small, semantically coherent option set, which is exactly the regime where both embedding retrieval and LLM disambiguation are reliable. Concretely: log2(40,000) ≈ 15.3 bits of selection entropy flat vs. log2(200)+log2(8)+log2(15) ≈ 7.6+3+3.9 ≈ 14.5 bits hierarchical looks similar in raw information content, but the *practical* error rate is far lower hierarchically because (a) most of the family/category resolution is deterministic from the task's structured context (which SaaS did the user name?) rather than a probabilistic LLM guess, and (b) at each level the *semantic distance* between sibling options is much larger than between two similarly-named operations buried in a 40,000-item flat list, which is what actually drives confusion, not raw option count.

In practice only Tool Categories relevant to the resolved Tool Family are ever loaded (L1), and only Operations within the resolved Category are exposed to the LLM as callable schemas (L2) — the LLM never sees "all GitHub tools," only "Pull Request tools," typically 5–10 operations.

---

## 12. Skill Architecture

### 12.1 Skill Package Layout

```
skills/python-security-audit/
├── skill.yaml            # machine-readable manifest (Resource envelope, §5.2)
├── SKILL.md               # LLM-readable instructions (loaded at L3)
├── instructions/
│   └── advanced-remediation.md      # optional deeper instructions, loaded on demand
├── examples/
│   ├── example-findings-report.json
│   └── example-invocation.md
├── scripts/
│   ├── run_bandit.py
│   └── merge_reports.py
├── templates/
│   └── findings-report.md.j2
├── references/
│   └── cwe-mapping.json
├── tests/
│   ├── test_run_bandit.py
│   └── fixtures/vulnerable_sample.py
└── dependencies.lock       # pinned versions of tool/mcp dependencies
```

| Machine-readable (never enters LLM context as prose) | LLM-readable (enters context at L3, budgeted) |
|---|---|
| `skill.yaml` (schema-validated envelope) | `SKILL.md` (instructions, when-to-use guidance) |
| `dependencies.lock` | `examples/*.md` (few-shot patterns, loaded selectively) |
| `tests/*` (run by CI/health-check, not read by agent) | `instructions/*.md` (loaded only if the task needs the deeper path) |
| `references/*.json` (looked up programmatically by scripts) | — |
| `scripts/*` (executed, not read, unless debugging) | — |

This split is what makes L3 loading affordable: `SKILL.md` is written to be *concise and directive* (target: 500–2,000 tokens), while everything a human/CI needs for correctness (tests, lockfiles, reference data tables) lives outside the LLM's reading path entirely.

### 12.2 Skill Versioning & Compatibility

- Skills follow semver. **Major** version bump = breaking input/output schema change or removed capability. **Minor** = added capability/optional input. **Patch** = instruction wording, bug fixes, no interface change.
- `dependencies.lock` pins exact resolved versions of every `requires` dependency at the time the skill was last validated; the Registry re-validates on a schedule and flags skills whose lockfile no longer resolves (a dependency was deprecated/archived).
- Two versions of the same skill can be simultaneously `active` during a deprecation window (§16); the Router defaults to the highest non-deprecated version unless a project pins an older one explicitly (e.g., a project mid-migration).
- Compatibility is declared, not inferred: `compatibility.runtimes`, `compatibility.conflicts_with` are checked during `resource.resolve`, before any execution attempt — this converts a class of runtime failures into planning-time rejections.

---

## 13. ProjectOS / Workspace Architecture

### 13.1 Capability vs. State

Skills, Tools, and MCP servers are **capabilities** — stateless with respect to any particular codebase, reusable across every project. A **Project** is the opposite: it is pure **state** — a specific codebase, its configuration, its history, its currently-active resource set. Conflating them (e.g., "the security-audit skill for project X" as a distinct resource from "the security-audit skill") would multiply the resource count by the project count for no benefit — capabilities don't change per project; what changes is which project state they're applied to and which subset of the global resource catalog that project is permitted/configured to use.

### 13.2 ProjectOS Contents

```
project (proj_44a)
├── source code (mounted workspace, git-tracked)
├── configuration (project.yaml: language, build system, CI config, allowed resource scopes)
├── tasks (active/historical task records, each linking to the resources it used)
├── project memory (§12 MemoryOS project tier: decisions, conventions, gotchas learned)
├── decisions (ADR-style records — "we chose X over Y because Z" — high-authority, long-lived)
├── active resources (the resolved, version-pinned set of resources currently enabled for
│                       this project — a materialized view, not a duplicate registry)
├── artifacts (build outputs, reports, generated files — addressable, immutable)
├── environment (runtime/toolchain versions, secrets scope, sandbox profile)
├── execution history (every resource.execute call made in this project, for audit + reputation)
├── references (project-specific docs: README, ARCHITECTURE.md, runbooks — indexed locally)
└── project-specific policies (overrides/additions to org policy, never loosening it — §17)
```

### 13.3 Project Isolation & Dynamic Resource Activation

- Every Project gets its own **sandbox namespace** (filesystem mount point, network policy, secret scope, container/VM identity) — resources executing "in" a project cannot see another project's filesystem or secrets even if both projects have the same resource activated concurrently.
- A Project's `active resources` set is computed, not manually maintained in the common case: when a task starts, the Router runs `search` scoped to `project.capabilities_hint` (derived from the project's language/stack/config) and *proposes* activation; explicit project config can pin or exclude specific resources.
- **Dynamic activation flow**: task arrives → ProjectOS supplies project context (language, stack, current git branch, recent decisions) to the Router as retrieval filters/boosts → Router's `search`/`resolve` naturally favors resources compatible with this project's stack → `activate` establishes the sandbox scoped to *this* project's identity → on task completion, `release` tears down the activation but the *execution history* and any new project-memory entries persist.
- Cross-project resource reuse (e.g., a Skill successful in Project A) informs **global** reputation (§21), but project-scoped memory and decisions never leak across projects — this is enforced at the MemoryOS retrieval layer (§12), not just by convention.


---

## 14. ContextOS

### 14.1 Why Not Concatenate

Naively concatenating `skills + tools + documents + memory + project files` into one prompt has three failure modes: (1) it blows past reasonable token budgets almost immediately at any real scale; (2) irrelevant content in context measurably degrades model attention to the relevant parts (context dilution); (3) it makes context **non-reproducible and non-auditable** — you can't answer "why did the model do X" if the prompt was an unstructured dump assembled differently every time.

### 14.2 The Assembly Pipeline

```
Context Sources  (ProjectOS state, MemoryOS tiers, resolved Resources at L1-L3,
                   Reference/Knowledge chunks, prior execution results)
 → Context Retrieval     (each source runs its own relevance query against the current task)
 → Context Ranking        (cross-source ranking: a highly relevant memory may outrank a
                            marginally relevant reference chunk)
 → Context Budgeting       (allocate token budget per category — see table below — then
                            truncate/select within each category by rank until budget is spent)
 → Context Assembly        (deterministic template: system → task → project state → active
                            resource(s) → references → memory → prior results, in a fixed order
                            so equivalent inputs produce byte-comparable prompts)
 → Context Compression      (summarize/elide within-budget content that's still too verbose —
                             e.g. collapse a 40-line stack trace to the top 5 relevant frames)
 → LLM
```

### 14.3 Indicative Context Budgets (per task turn, for a ~150K-token-window model)

| Category | Budget (tokens) | Notes |
|---|---|---|
| System instructions | 1,500–2,500 | Fixed, cached across turns (prompt caching) |
| Task description | 500–2,000 | Verbatim user/task text + parsed intent |
| Project state summary | 1,000–3,000 | Compressed: language, structure, recent diffs, not full source |
| Active resource(s), L3 | 2,000–15,000 | Only the 1–3 selected resources' full instructions |
| Candidate resources, L2 | 500–2,000 | Only if disambiguation is needed this turn |
| References/Knowledge | 1,000–4,000 | Top-ranked chunks only, not full documents |
| Memory (all tiers combined) | 500–3,000 | Weighted by importance score (§12), most turns need little |
| Execution results (prior steps) | 1,000–8,000 | Summarized beyond N steps back; full only for the immediately prior step |
| **Reserved for reasoning/output** | remainder | Never let input categories crowd this below a hard floor |

The allocator is **dynamic, not static**: budgets are soft ceilings redistributed by a priority order (Policy > Task > Active Resource > Project State > References > Memory > Prior Results) when one category needs less than its ceiling — unused Memory budget can flow to References, for instance — but the *hard floor* reserved for model reasoning/output is never encroached upon.

### 14.4 Context Allocator Logic (sketch)

```python
def assemble_context(task, sources, total_budget, output_floor):
    available = total_budget - output_floor
    ranked = {cat: rank_by_relevance(sources[cat], task) for cat in sources}
    allocation = default_budgets(available)          # table above, scaled to available
    spent = 0
    assembled = {}
    for cat in PRIORITY_ORDER:                          # policy > task > resource > ...
        items, used = select_within_budget(ranked[cat], allocation[cat])
        assembled[cat] = compress_if_needed(items, allocation[cat])
        spent += used
    # redistribute leftover budget to next-priority categories still truncated
    leftover = available - spent
    assembled = redistribute(assembled, ranked, leftover, PRIORITY_ORDER)
    return render_template(assembled)                    # fixed, deterministic ordering
```

---

## 15. Memory Architecture

### 15.1 Hierarchy

```
Global Memory     — org-wide facts/conventions, rarely written, high trust
User Memory        — this user's preferences, recurring corrections
Project Memory      — this codebase's decisions, conventions, gotchas
Task Memory          — this task's working state (scratch, mostly ephemeral)
Agent Memory          — this agent instance's self-observations (its own error patterns)
Tool Memory            — per-tool usage notes ("this API rate-limits at 100/min")
Episodic Memory          — specific past events ("on 2026-06-02 we reverted PR #441 because...")
Semantic Memory            — generalized facts distilled from multiple episodes
```

### 15.2 Cross-Cutting Behavior

| Aspect | Policy |
|---|---|
| **Storage** | Episodic entries stored as discrete timestamped records; Semantic entries stored as consolidated, periodically re-derived summaries — never store only semantic and discard the episodic source, since provenance must be traceable back to specific events. |
| **Indexing** | Same hybrid retrieval as resources (§9), scoped by tier and, for Project/Task memory, hard-filtered by project_id — no cross-project leakage. |
| **Retrieval** | Ranked by relevance × importance × recency-decay; Task Memory is retrieved almost unconditionally (it's the current working state); Global/Semantic Memory only surfaces when directly relevant. |
| **Expiration** | Task Memory expires at task completion (optionally promoted, see below). Episodic Memory has a decay half-life by tier (Agent/Tool episodic: weeks; Project episodic: months–indefinite for Decisions). |
| **Promotion** | An episodic pattern observed ≥N times with consistent outcome gets promoted to Semantic Memory ("this project always wants tests colocated with source") via an offline consolidation job — never promoted synchronously mid-task, to avoid a single noisy event overwriting established semantic knowledge. |
| **Compression** | Semantic consolidation *is* the compression mechanism — many episodic entries collapse into one semantic statement with a citation list back to source episodes. |
| **Conflict resolution** | Newer Project Memory overrides older on direct contradiction, but Decisions (ADR-style) are only superseded by an explicit new Decision, never silently overwritten by an inferred pattern — this protects deliberate human/agent decisions from being eroded by noisy usage patterns. |
| **Importance scoring** | Function of: explicit marking (user said "remember this"), repetition count, recency, and downstream impact (did following/ignoring this memory correlate with task success in the reputation data, §21). |

Memories are **not treated equally**: a Decision record has different authority than an auto-derived Semantic pattern, and both are structurally distinguished from Reference/Knowledge content (§16) — this is what prevents a plausible-sounding but wrong inferred pattern from being retrieved with the same confidence as an explicit human decision.

---

## 16. Reference / Knowledge Architecture

### 16.1 Distinctions

| | Reference | Knowledge | Memory | Project State | Artifact |
|---|---|---|---|---|---|
| **Lifecycle** | Ingested once, updated on source change | Re-derived when References change | Accumulates continuously | Mutates with every commit/task | Immutable once produced |
| **Authority** | As authoritative as its source | Inherits + can degrade (summarization risk) | Medium; explicit Decisions high, inferred low | High (it *is* the ground truth) | High for what it records, but is a snapshot |
| **Mutability** | Low (external doc changed underneath it) | Low–medium | High | Very high | None (versioned, not edited) |
| **Retrieval strategy** | Chunked hybrid retrieval (§9) | Chunked hybrid retrieval, often smaller/denser chunks | Tiered, importance-weighted (§12) | Structured query (not RAG) — direct DB read | Addressed by ID/hash, rarely searched semantically |
| **Provenance** | Source URI + fetch timestamp | Source Reference IDs it was derived from | Originating task/event ID | Git commit / config version | Producing execution ID |
| **Trust level** | Set by source (internal docs > random web) | ≤ its source References' trust level | Set by origin (human > agent-inferred) | Highest (live system state) | Set by producing resource's trust tier |

### 16.2 Ingestion Pipeline

```
Raw Reference (a doc, RFC, runbook, API spec)
 → Parsing            (format-specific: markdown/HTML/PDF/OpenAPI → structured text)
 → Cleaning             (strip boilerplate/nav chrome, normalize whitespace, de-duplicate)
 → Chunking               (semantic chunking — section/heading-aware, target 200–500 tokens/
                            chunk, with overlap at boundaries to preserve local context)
 → Metadata               (source, section path, timestamp, trust tier, capability tags)
 → Embedding                (vector per chunk, model-versioned so re-embedding on model
                              upgrade is trackable)
 → Indexing                   (chunk → vector index + FTS index + parent-document graph edge)
 → Knowledge                   (optional derivation step: LLM-assisted summarization/synthesis
                                 across multiple chunks/References into a denser Knowledge node,
                                 explicitly tagged as derived and linked back to sources)
 → Retrieval                    (same hybrid pipeline as resources, §9, scoped to
                                  reference/knowledge types)
```

Knowledge nodes are **never presented without their provenance chain retrievable** — every derived claim can be traced back to the specific chunks it was synthesized from, both for auditability and so a downstream user/agent can escalate to the primary source if the summary is ambiguous.


---

## 17. Resource Dependency Graph

### 17.1 Representation

The dependency graph is a **directed graph, resources as nodes, typed edges**, stored relationally (`resource_dependencies` — §28) with edge types: `requires` (hard), `optional` (soft, with declared `fallback`), `references` (informational, e.g. a Skill references Documentation but doesn't require it to function), `produces` (Skill → Artifact type), `modifies` (Workflow → Project). It is **not** stored as a single in-memory graph object at scale — at 10⁵–10⁶ resources it is queried relationally with recursive CTEs / a materialized closure table for the `requires` subgraph specifically (the one that needs topological resolution), while `references`/`produces` edges are queried directly without needing transitive closure.

```
Skill: python-security-audit
 → requires        Tool: bandit-cli (>=1.7.0)
 → requires        Tool: pip-audit (>=2.6.0)
 → optional        MCP: snyk           (fallback: Tool: pip-audit)
 → references        Documentation: cwe-mapping
 → produces            Artifact: security-report.json, sarif
 → modifies              Project: .reports/ directory
```

### 17.2 Resolution Algorithm

```
resolve(resource_id, project_context):
  1. Build the requires-subgraph reachable from resource_id (BFS/DFS via closure table)
  2. Detect cycles (Tarjan's SCC) → reject with a clear cycle report if found; skills/tools
     should never legitimately form a requires-cycle — this indicates a registration error
  3. Topologically sort the DAG → gives valid activation order
  4. For each node, resolve the tightest version satisfying all incoming version constraints
     (a SAT-style constraint solve for anything beyond simple semver ranges; simple ranges
     resolved directly)
  5. For each `optional` edge whose primary is unavailable/unresolvable, substitute its
     declared `fallback` and re-resolve from that point
  6. For any node still unresolved (no compatible version, no fallback), mark the whole plan
     `unresolved` and report exactly which node blocked it — never silently drop a dependency
  7. Return the ordered, version-pinned execution plan (this is exactly the payload shown in
     the resource.resolve example in §10.1)
```

Capability substitution (step 5's fallback) is what lets the graph degrade gracefully: if `mcp:snyk` is down, the plan doesn't fail — it substitutes `tool:pip-audit`, which was declared as satisfying the same `security.dependency-audit.python` capability, and proceeds with a (logged, observable) reduced-capability execution.

---

## 18. Resource Reputation System

### 18.1 Tracked Signals (per resource, per context bucket)

success_rate, failure_rate, p50/p95 latency, avg token cost, avg dollar cost, user acceptance rate (did the human keep the output / revert it), task completion rate (did the *overall* task succeed when this resource was used in it, not just did the call not error), error_rate by error class, security_incident_count, freshness (days since last update / validation), usage_frequency.

### 18.2 From Signals to Ranking Prior

```
P(resource | task, project, environment)
   ∝  capability_match_score(resource, task)                    # from retrieval, §9
      × quality_prior(resource, project_type, task_type)          # from reputation history,
                                                                     bucketed by context so a
                                                                     resource's stats for
                                                                     "python monorepo" tasks
                                                                     don't get diluted by its
                                                                     stats on unrelated tasks
      × recency_decay(freshness)
      × (1 − security_incident_penalty)
```

`quality_prior` is a **Bayesian-smoothed** rate (e.g., Beta(successes+α, failures+β) with weak prior α=β=2), not a raw success/total ratio — this specifically prevents a resource with 2 successes and 0 failures from outranking one with 480 successes and 12 failures on raw rate alone.

### 18.3 Preventing Popularity Feedback Loops

This is the failure mode where a mediocre resource gets used often (because it was once ranked slightly higher, or is simply older/first-registered), accumulates usage volume, and its raw popularity keeps it ranked at the top even as better alternatives emerge — usage count is a *biased, non-random sample* and treating it as ground truth entrenches incumbents. Mitigations:

- **Separate "used" from "worked."** `usage_frequency` never directly enters the ranking prior — only outcome-conditioned signals (success/acceptance/completion rates) do. Popularity alone is not evidence of quality.
- **Explicit exploration budget.** A small fraction (configurable, e.g. 5–10%) of eligible retrieval slots for a given capability are reserved for exploration — surfacing a plausible, under-sampled alternative even when an incumbent scores higher on a thin-but-positive history, using a bandit-style exploration bonus (e.g. UCB: score + c·√(ln(N_capability)/N_resource))) so under-tried resources with reasonable priors get periodically re-evaluated.
- **Context-bucketed stats**, not global stats — a resource's reputation for "used successfully in Rust CLI tools" shouldn't lend confidence to using it in "Python data pipelines," which prevents volume in one context from crowding out better-fit resources in another.
- **Freshness decay.** Old success statistics decay in weight over time relative to recent ones (exponential moving average, not lifetime average), so a resource that degraded 3 months ago (an upstream API changed) loses ranking even if its lifetime numbers still look good.
- **Periodic offline audit** (§25) explicitly looks for capability clusters where one resource holds >80% share and flags them for human review of whether that's deserved dominance or an entrenchment artifact.


---

## 19. Resource Lifecycle

```
DISCOVERED → REGISTERED → VALIDATED → ACTIVE → DEGRADED → DEPRECATED → ARCHIVED
                                          ↑___________↓
                                        (health checks pass → back to ACTIVE)
```

| State | Meaning | Entry condition | Exit condition |
|---|---|---|---|
| DISCOVERED | Found (scanned from a repo, submitted, generated) but not yet in the Registry | Discovery scan / submission | Passes schema validation → REGISTERED |
| REGISTERED | In the Registry, schema-valid, not yet trusted for use | Schema + provenance check passed | Passes integration tests + security scan → VALIDATED |
| VALIDATED | Verified functional and safe in a sandboxed test environment | Integration tests pass, security scan clean | Promoted by policy/human sign-off → ACTIVE |
| ACTIVE | Eligible for discovery and execution | Promotion approved | Health check failure → DEGRADED; superseded → DEPRECATED |
| DEGRADED | Failing health checks / elevated error rate but not yet pulled | Automated health-check threshold breach | Recovers → ACTIVE; persists beyond grace period → DEPRECATED |
| DEPRECATED | Superseded or scheduled for removal; still resolvable for pinned dependents, excluded from new discovery | New version promoted, or manual deprecation, or degradation grace period expired | Deprecation window elapses with no remaining dependents → ARCHIVED |
| ARCHIVED | Retained for audit/provenance, not resolvable, not discoverable | Deprecation window complete | (terminal; can be manually un-archived only via re-REGISTERED path) |

**Health checks**: scheduled probes (does the MCP server respond, does the script still run against its fixture) run async, off the critical query path, and update `lifecycle_state`/`quality_metrics` — a query never blocks on a live health check. **Compatibility checks**: re-run on every dependency version bump. **Security checks**: static analysis + secret-scan on registration and on every content update; a failing security check hard-blocks REGISTERED→VALIDATED regardless of who submitted it. **Schema validation**: enforced on write, not just at registration. **Rollback**: a resource can be pinned back to a prior version at the Project or Org level without going through full re-validation of the old version (its historical validation record is retained). **Version pinning**: any resource reference can specify an exact version; the Router respects pins over "latest active" resolution.

---

## 20. SecurityOS

### 20.1 Principle

The model requests actions in natural language; **it is never the enforcement point**. Every permission a resource could exercise is declared in its `permissions`/`security_policy` block (§5.2) and checked structurally by the Policy Engine before `activate`/`execute` proceed — no amount of persuasive phrasing in a tool call changes what the sandbox actually allows a process to do.

```
Agent  →  Policy Engine  →  Resource  →  Sandbox  →  Runtime
 (proposes                  (checks:                (enforces:
  resource +                 - identity/scope         - filesystem namespace
  input via                    permitted this          - network egress allowlist
  resource.execute)             resource/project?      - syscall/capability limits
                                - requested action       - resource limits (CPU/mem/time)
                                  within declared         - credential injection scoped
                                  permission scope?         to declared secrets only)
                                - trust tier sufficient
                                  for this operation
                                  without human review?
                                - rate/quota limits
                                  not exceeded?)
```

### 20.2 Per-Resource Security Contract

Every resource declares (§5.2 `permissions`/`security_policy`): filesystem scope (read/write paths, never unrestricted), network egress allowlist (specific hosts, not "internet"), secret access (named secrets only, injected at execution time into the sandbox, never into the LLM's context), execution limits (time/CPU/memory), sandbox tier (`none` for pure-read informational resources up to `container`/`vm` for anything with filesystem/network write), and `trust_tier` which gates whether *human* review is required before an operation of a given risk class runs (e.g., `requires_review_above_risk: medium` means a `high`-risk classified action — e.g., `git push --force`, deleting a resource, granting new permissions — always requires human confirmation regardless of resource reputation).

### 20.3 Isolating Malicious or Compromised Resources

- **Registration-time**: static analysis + secret-scanning on any script/code content; anomalous permission requests (a "documentation formatter" skill requesting network egress) are flagged for mandatory human review before VALIDATED.
- **Runtime**: sandboxing means a compromised resource's blast radius is bounded by its declared permission scope, not by what the process *could* do on the host — even a fully malicious script inside a container with no network egress and a read-only mount of one directory can do very little.
- **Detection**: anomaly detection on execution patterns (a resource suddenly requesting far more filesystem access than its historical pattern, or attempting network calls to hosts outside its allowlist — the latter is a hard sandbox denial, not just a flag) triggers automatic DEGRADED transition and alerting.
- **Containment**: on confirmed compromise, the resource is force-transitioned to ARCHIVED, its trust_tier revoked, all cached L3/L4 content invalidated, and every project with it in `active resources` is notified; dependents relying on it via `optional`/fallback edges are automatically re-resolved to their fallback.
- **Credential hygiene**: secrets are never placed in resource metadata, never in context sent to the LLM, and never logged in observability traces (§24) beyond a redacted reference — they exist only inside the sandbox's injected environment for the duration of `execute`.


---

## 21. Resource Conflict Resolution

### 21.1 Detection

- **Duplicate detection**: at registration, embed the new resource's description+capability set and compare against existing resources above a similarity threshold (cosine ≥ ~0.9 on description embeddings *and* ≥70% capability-set overlap); flagged pairs go to a review queue rather than auto-merging (auto-merge risks silently losing a resource with genuinely different, narrower scope).
- **Capability collision**: two resources declaring the *same* capability at the *same* specificity with materially different behavior/output schema (not just alternative implementations) — flagged for a human decision on which should be canonical vs. renamed to a more specific capability.
- **Version conflicts**: detected during dependency resolution (§17.2) when two `requires` edges in one plan demand incompatible version ranges of the same resource — reported at plan time, never silently resolved by picking one arbitrarily.
- **Incompatible tools**: declared via `compatibility.conflicts_with`; the Composer (§22) rejects plans that would concurrently activate two conflicting resources.
- **Conflicting instructions/references**: two References making contradictory claims are surfaced with both provenance chains rather than one silently winning — resolved by the precedence hierarchy below when the retrieval context forces a single answer.

### 21.2 Precedence Rules

```
System Policy
   >
Project Policy
   >
Skill Policy (a Skill's own declared constraints/instructions)
   >
User Preference
   >
Reference (external/internal documentation)
   >
Generated Suggestion (LLM-proposed content not backed by any of the above)
```

Higher tiers can **only restrict**, never grant permission a lower tier didn't already have structurally (a Project Policy cannot grant network egress a System Policy forbids) — precedence governs *which instruction/preference wins when they conflict on a matter both are allowed to have an opinion on*, not authorization itself, which is governed purely by the additive permission model in §20.

---

## 22. Resource Composition

Composition is modeled as a **graph/workflow the Composer builds**, not something the LLM is expected to hold in its head across many steps.

```
Task: "Implement a feature, test it, review it, create a PR, and deploy it."

Composer output (a Workflow resource, generated or matched from an existing template):

  [Coding Skill] → produces → (code diff)
        │
        ▼
  [Testing Skill] → requires (code diff) → produces → (test results)
        │
        ▼
  [Review Skill] → requires (code diff, test results) → produces → (review notes)
        │
        ▼
  [Git Tool: commit] → requires (code diff, review approval gate) → produces → (commit)
        │
        ▼
  [GitHub Tool: create PR] → requires (commit) → produces → (PR artifact)
        │
        ▼
  [CI/CD Workflow] → requires (PR merged) → 
        │
        ▼
  [Deployment Tool] → produces → (deployment artifact)
```

### 22.1 How Composition Actually Works

1. **Decompose** the task into an ordered (or partially-ordered) set of sub-capabilities via the Capability Graph's `composable_with` edges (§6.2) — this can reuse an existing matched Workflow resource if one already encodes this exact composition (preferred: don't re-derive what's already a validated Workflow), or build a new one from the graph.
2. **Resolve** each step to a concrete resource via the same Router `resolve` used for single-resource tasks (§10), respecting each step's input requirements as declared data dependencies (step N's required input must be in the declared output set of some step < N, or an existing context source).
3. **Validate** the composed plan against `conflicts_with`/`compatibility` (§21) and confirm no dependency cycle across steps.
4. **Gate** steps requiring human approval per their `trust_tier`/risk classification (§20.2) — e.g., the PR-merge and deploy steps typically gate.
5. **Execute** step-by-step via the Execution Runtime, with each step's `output_ref` (not full output content) passed as the *reference* the next step's input schema expects — content is pulled into context only where a step's own execution actually needs to read it, not just because it exists.
6. The realized execution — the actual resource IDs, order, and outcomes — is itself recorded and, if it succeeds reliably across multiple tasks of this shape, is a candidate to be **promoted into a reusable Workflow resource** (§25), so the next equivalent task skips steps 1–3 entirely.


---

## 23. Failure Recovery

```
Tool A fails
  → Diagnose        (classify failure: transient (network blip) vs. persistent (schema
                       mismatch, auth failure) vs. resource-unavailable vs. policy-denied)
  → Retry             (only for classified-transient failures; bounded — max 2 retries,
                        exponential backoff, and only if retry is idempotent-safe per the
                        resource's declared `idempotent: true/false`)
  → Alternative Tool B (Router re-queries with Tool A excluded, same capability requirement —
                         reuses the ranked candidate list already computed in §9 if fresh)
  → Alternative Skill   (if no alternative Tool satisfies it alone, widen to a Skill that
                          composes multiple tools to reach the same capability)
  → Fallback Workflow     (a pre-registered degraded-mode workflow for this capability class,
                            e.g. "if automated dependency-audit unavailable, produce a
                            manual-review checklist instead")
  → Human escalation        (terminal fallback: task paused, human notified with full trace
                              of what was tried and why each attempt failed)
```

**Avoiding infinite retry loops**: a hard global retry budget per task-step (not per resource — retrying resource A twice then failing over to resource B which also fails twice is 4 attempts, not infinite); a circuit breaker per resource that trips after N consecutive failures across *any* task and holds the resource in DEGRADED (§19) for a cooldown window, so a systemically broken resource stops being retried by every concurrent task simultaneously; and a monotonic "attempts remaining" counter passed through the fallback chain that forces escalation once exhausted regardless of how many fallback branches remain unexplored.

---

## 24. Observability

### 24.1 Traced Pipeline

```
Task → Retrieval → Candidate Resources → Ranking → Selected Resources →
Context Loaded → Execution → Result → Evaluation
```

Every arrow above is a logged event with a shared `trace_id`, enabling full reconstruction of "why did the agent do that" after the fact.

### 24.2 Trace Schema (indicative)

```json
{
  "trace_id": "trc_88b21f",
  "task_id": "task_772",
  "project_id": "proj_44a",
  "spans": [
    {"span": "retrieval", "query": "audit python security", "candidates_considered": 512,
     "candidates_returned": 10, "latency_ms": 38},
    {"span": "ranking", "top_scores": [{"id": "res_9f21c3a0b7", "score": 0.91}, ...],
     "reranker_used": true, "latency_ms": 22},
    {"span": "selection", "selected": ["res_9f21c3a0b7"], "confidence": "high",
     "auto_selected": true},
    {"span": "context_load", "level": "L3", "tokens": 4120},
    {"span": "activation", "handle": "hdl_88c1", "sandbox": "container:cid_a02f"},
    {"span": "execution", "status": "success", "duration_ms": 4310,
     "output_ref": "artifact:art_5510"},
    {"span": "evaluation", "task_success": true, "user_accepted": null}
  ]
}
```

### 24.3 Metrics

resource retrieval latency (p50/p95/p99), retrieval precision@k / recall@k (measured against a labeled eval set, §33), tool-selection accuracy (did the *first* selected resource end up being the one that succeeded, vs. requiring fallback), resource success rate (per resource, per capability bucket), context tokens used vs. budgeted, wasted tokens (loaded-but-unused L2/L3 content — a strong signal the ranking or budget allocator needs tuning), failed executions (by failure class), fallback frequency (how often step 2+ of the failure-recovery chain is needed — a rising trend flags a specific resource's reliability regressing before its aggregate quality_metrics catch up), resource utilization (active resource count vs. registered count, to catch registry bloat), cost per task (token + dollar).

---

## 25. Self-Improvement Loop

```
Task → Resource Selection → Execution → Result → Evaluation → Feedback →
Resource Ranking Update → Capability Graph Update → Future Selection
```

### 25.1 Online vs. Offline

- **Online adaptation** (safe to run continuously, in the hot path or near it): reputation signal updates (§18) from each execution's outcome; retrieval negative-signal updates from explicit user rejections; circuit-breaker state (§23). These are narrow, bounded, statistically-smoothed updates to *existing* scores — they cannot introduce a new capability, promote a resource's lifecycle state, or change the capability graph's structure.
- **Offline evaluation** (batch, reviewed, never auto-applied to production ranking without passing gates): capability graph structural changes (new nodes, new edges) proposed from usage-pattern mining; candidate new Workflow resources synthesized from repeatedly-successful ad hoc compositions (§22.1 step 6); reputation *model* changes (adjusting the Bayesian prior parameters, the exploration bonus constant); lifecycle promotions (VALIDATED→ACTIVE) — always requires the offline validation pipeline (§19), never auto-promoted from online signal alone, since online signal alone is exactly the mechanism a popularity feedback loop (§18.3) would exploit.

This separation is the safeguard against "the system quietly rewrites its own policy because a burst of correlated-but-wrong online signal pointed that way" — anything with lasting structural effect goes through an offline, reviewable, gated pipeline; only smoothed, bounded, reversible statistics update live.

### 25.2 Learning "which resource works best for which task"

Offline, periodically: aggregate (task_type, project_type, resource, outcome) tuples into a supervised dataset; retrain/recalibrate the reranker and the reputation-prior parameters against a held-out eval slice; A/B the updated ranking against the current production ranking on a shadow traffic sample before promoting; only promote if precision@k and task-success-rate both improve or hold steady without regressing any tracked capability cluster below its current baseline.


---

## 26. Storage Architecture

### 26.1 Technology Comparison

| Technology | Role fit | Strength | Weakness at this scale |
|---|---|---|---|
| **SQLite** | Metadata store, single-node | Zero-ops, transactional, embeds FTS5 | No built-in horizontal scaling, single-writer |
| **PostgreSQL** | Metadata store, multi-node | Mature, JSONB, extensions (pgvector), strong concurrency | Needs real ops (backups, HA) beyond single-machine tier |
| **Redis** | Hot cache (L0/L1 cache, session/lock state) | Sub-ms latency, TTL native, pub/sub for invalidation | Not durable-by-default; not a system of record |
| **FAISS** | Vector index, embedded | Extremely fast ANN, no server process | No native metadata filtering/persistence layer — needs pairing with a metadata store |
| **Qdrant / Milvus** | Vector index, served | Filtered ANN, horizontal scaling, built-in persistence | Operational overhead not justified below ~10⁵–10⁶ vectors |
| **Elasticsearch/OpenSearch** | Full-text + hybrid, served | Mature hybrid (BM25+vector) search, faceting | Heavy operationally; overkill until multi-node scale |
| **Neo4j** | Capability/dependency graph, served | Native graph traversal, Cypher | Unnecessary if graph fits in a relational closure table (true until very large/deep graphs) |
| **Object Storage (S3-class)** | Resource content (scripts, templates, large references) | Cheap, durable, versioned | Not queryable directly; always paired with a metadata index |
| **Filesystem** | Resource content, single-node | Simplest possible, git-friendly for source-controlled skills | No built-in replication/versioning beyond what git gives you |

### 26.2 Three Reference Topologies

**1. Minimal single-machine** (target of §27): SQLite (metadata + FTS5) + FAISS (vectors, flat/IVF index) + local filesystem (resource content, git-tracked) + in-process LRU cache for L0/L1. No server processes beyond the agent itself. Handles up to roughly 10⁴–10⁵ resources comfortably on commodity hardware (§32).

**2. Medium-scale**: PostgreSQL (metadata, JSONB for flexible type_metadata, pgvector extension folding vector search into the same DB to avoid a second system) + Redis (hot L0/L1 cache, distributed locks for activation, rate limiting) + object storage (resource content) + a lightweight capability-graph closure table in Postgres (still relational, not yet worth a graph DB). Handles 10⁵–10⁶ resources across a small cluster.

**3. Enterprise-scale distributed**: PostgreSQL (sharded by scope/org, or a distributed SQL layer) as system of record for metadata + Qdrant/Milvus cluster for vector search at 10⁶+ resources with real-time filtered ANN + OpenSearch for full-text/BM25 at scale + Redis cluster for caching/locking/rate-limits + Neo4j (or a graph layer atop the distributed relational store) once capability/dependency traversal depth and concurrent-write volume justify a dedicated graph engine + object storage (content) fronted by a CDN for widely-shared public resources + a message bus (Kafka-class) decoupling registration/health-check/reputation-update event streams from the synchronous query path.

---

## 27. Recommended Low-Resource Implementation

Target: a single machine, no external services, Python or TypeScript, using **SQLite + FTS5 + FAISS + filesystem**.

```
resourceos-data/
├── registry.db                  # SQLite: all relational tables (§28)
│   # FTS5 virtual table `resources_fts` mirrors name/description/tags for BM25
├── vectors/
│   ├── resources.faiss           # FAISS IndexIVFFlat (or IndexFlatIP below ~50K vectors)
│   └── resources.idmap.json      # FAISS internal int ID → resource_id mapping
├── content/                       # resource file content, mirrors registry `source.uri`
│   ├── skills/python-security-audit/...
│   └── scripts/...
├── artifacts/                      # execution outputs, content-addressed by hash
│   └── art_5510.json
└── logs/
    └── traces.jsonl                # append-only observability trace log (§24)
```

- **Metadata**: every field in §5.2's envelope as SQLite columns/JSON columns (`type_metadata`, `permissions`, etc. as JSON1 columns) — full relational schema in §28.
- **Full text**: an FTS5 virtual table indexing `name || description || tags` per resource, kept in sync via SQLite triggers on `resources` insert/update — gives BM25-quality lexical retrieval (§9 step 3) with zero extra infrastructure.
- **Vectors**: FAISS index built from the same embedding model used at ingestion; below ~50K vectors use a flat (exact) index — at this scale exact search is still sub-10ms and avoids ANN recall loss; above that, switch to `IndexIVFFlat` with a modest `nlist` (e.g. √N clusters) trading a small recall hit for speed. The FAISS int-ID ↔ `resource_id` mapping is a simple JSON/SQLite table since FAISS itself only knows integer IDs.
- **Graph relationships**: the capability graph and dependency graph are plain relational tables (`capability_edges`, `resource_dependencies`) with a maintained **closure table** (`capability_closure`: ancestor_id, descendant_id, depth) rebuilt incrementally on edge insert — this gives O(1) ancestor/descendant lookups without recursive CTEs on the query hot path, and is entirely adequate until graph depth/fan-out reaches a scale (rare for capability taxonomies, which are intentionally shallow) that would justify a dedicated graph engine.
- **Resource files**: left on the filesystem, ideally git-tracked for skills/scripts/templates (gets you free versioning, diffing, and code review for capability changes) — the Registry stores the path + content hash, and a background job periodically verifies the hash matches (detects unauthorized/uncoordinated file edits).
- **Execution logs**: append-only JSONL trace log (§24.2 schema), rotated and periodically compacted into the SQLite `executions`/`execution_events` tables for queryability; the raw JSONL remains the durable audit trail.

This setup comfortably serves the 10³–10⁴ resource range interactively and the 10⁴–10⁵ range with acceptable (double-digit ms to low hundreds of ms) query latency, entirely without a server process — appropriate for a local dev agent, a single-tenant deployment, or as the reference implementation before scaling out per §26.2 tiers 2–3.


---

## 28. API Design

All endpoints are versioned (`/v1/...`), authenticated (agent/service identity, not end-user credentials directly), and every mutating call requires the caller's scope to be checked by the Policy Engine before the Registry is touched.

```
POST   /v1/resources/register            Register a new resource (or new version of existing)
GET    /v1/resources/search              Hybrid search (§9); query params: q, type[], scope,
                                          capabilities[], project_id, top_k
GET    /v1/resources/{id}                 L1 metadata for one resource
GET    /v1/resources/{id}/manifest          L2 interface (schema) for one resource
POST   /v1/resources/{id}/activate           Establish runtime handle (§10.1)
POST   /v1/resources/{id}/execute             Invoke via an active handle
POST   /v1/resources/resolve                   Full dependency-resolved execution plan (§17.2)
GET    /v1/capabilities/search                   Search the capability graph directly
GET    /v1/capabilities/{id}                       One capability node + its resources
GET    /v1/projects/{id}                             Project state summary (ProjectOS)
GET    /v1/memory/search                              Hybrid search scoped to memory tiers
POST   /v1/feedback                                     Explicit accept/reject/correction signal
```

### 28.1 Examples

```json
// GET /v1/resources/search?q=audit%20python%20security&type=skill,tool,mcp&top_k=5
{
  "query": "audit python security",
  "results": [
    {"id": "res_9f21c3a0b7", "type": "skill", "name": "python-security-audit",
     "score": 0.91, "level_returned": "L1"},
    {"id": "res_1a44e", "type": "tool", "name": "bandit-cli", "score": 0.77,
     "level_returned": "L1"}
  ],
  "total_candidates_considered": 512,
  "latency_ms": 41
}

// POST /v1/resources/register
{
  "type": "tool",
  "name": "github.pull_request.create",
  "version": "1.4.0",
  "capabilities": ["vcs.github.pr.create"],
  "interface": { "invocation": "mcp_tool", "mcp_server": "mcp:github",
                 "input_schema": {"$ref": "schemas/github_pr_input.json"} },
  "permissions": {"network": {"egress": ["api.github.com"]}, "secrets": ["GITHUB_TOKEN"]},
  "source": {"origin": "internal-registry", "uri": "git+https://github.com/org/tools/github-mcp"}
}
// → 201
{ "id": "res_9f21c3a0b7", "lifecycle_state": "registered",
  "validation_required": ["schema_check:pass", "security_scan:pending"] }

// POST /v1/feedback
{ "trace_id": "trc_88b21f", "resource_id": "res_9f21c3a0b7",
  "signal": "accepted", "task_success": true, "notes": "findings were accurate" }
// → 202 { "status": "recorded" }
```

---

## 29. Database Schema

Core relational schema (illustrated in Postgres-flavored DDL; identical structure applies to the SQLite low-resource tier with JSON1 in place of JSONB).

```sql
CREATE TABLE resources (
  id                TEXT PRIMARY KEY,           -- ULID
  type              TEXT NOT NULL,               -- skill|tool|mcp|...
  name              TEXT NOT NULL,
  description       TEXT NOT NULL,
  version           TEXT NOT NULL,
  lifecycle_state   TEXT NOT NULL DEFAULT 'discovered',
  scope             TEXT NOT NULL,
  owner_team        TEXT,
  source_origin     TEXT,
  source_uri        TEXT,
  source_commit     TEXT,
  interface         JSONB,                       -- invocation type + schema refs
  permissions       JSONB,
  security_policy   JSONB,
  type_metadata     JSONB,
  quality_score     REAL DEFAULT 0.5,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now(),
  UNIQUE (name, version)
);
CREATE INDEX idx_resources_type_state ON resources (type, lifecycle_state);
CREATE INDEX idx_resources_scope ON resources (scope);
CREATE INDEX idx_resources_quality ON resources (quality_score DESC);

CREATE TABLE resource_versions (
  resource_id TEXT REFERENCES resources(id),
  version     TEXT,
  content_hash TEXT,
  changelog   TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (resource_id, version)
);

CREATE TABLE capabilities (
  id          TEXT PRIMARY KEY,       -- e.g. "security.dependency-audit.python"
  description TEXT,
  aliases     TEXT[],
  contract_version TEXT
);

CREATE TABLE capability_edges (
  parent_id TEXT REFERENCES capabilities(id),
  child_id  TEXT REFERENCES capabilities(id),
  PRIMARY KEY (parent_id, child_id)
);
CREATE TABLE capability_closure (        -- materialized ancestor/descendant table
  ancestor_id   TEXT REFERENCES capabilities(id),
  descendant_id TEXT REFERENCES capabilities(id),
  depth         INT,
  PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE TABLE resource_capabilities (
  resource_id   TEXT REFERENCES resources(id),
  capability_id TEXT REFERENCES capabilities(id),
  confidence    REAL DEFAULT 1.0,
  PRIMARY KEY (resource_id, capability_id)
);
CREATE INDEX idx_res_cap_capability ON resource_capabilities (capability_id);

CREATE TABLE resource_dependencies (
  from_resource TEXT REFERENCES resources(id),
  to_resource   TEXT REFERENCES resources(id),
  edge_type     TEXT NOT NULL,          -- requires|optional|references|produces|modifies
  version_range TEXT,
  fallback_resource TEXT REFERENCES resources(id),
  PRIMARY KEY (from_resource, to_resource, edge_type)
);
CREATE INDEX idx_deps_from ON resource_dependencies (from_resource);

CREATE TABLE resource_permissions (
  resource_id TEXT REFERENCES resources(id),
  scope_type  TEXT,                     -- filesystem|network|secret|execution
  scope_value JSONB,
  PRIMARY KEY (resource_id, scope_type)
);

CREATE TABLE resource_usage (
  resource_id TEXT REFERENCES resources(id),
  project_id  TEXT,
  task_type   TEXT,
  invoked_at  TIMESTAMPTZ,
  status      TEXT,                     -- success|failure|timeout
  latency_ms  INT,
  token_cost  INT
);
CREATE INDEX idx_usage_resource_time ON resource_usage (resource_id, invoked_at DESC);

CREATE TABLE resource_quality (
  resource_id TEXT PRIMARY KEY REFERENCES resources(id),
  success_count INT DEFAULT 0,
  failure_count INT DEFAULT 0,
  ema_latency_ms REAL,
  ema_success_rate REAL,
  last_incident_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE resource_embeddings (
  resource_id TEXT PRIMARY KEY REFERENCES resources(id),
  embedding_model TEXT,
  vector_id   BIGINT                    -- maps to FAISS/Qdrant internal ID
);

CREATE TABLE projects (
  id TEXT PRIMARY KEY, name TEXT, config JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE project_resources (         -- materialized active-resource view (§13.3)
  project_id TEXT REFERENCES projects(id),
  resource_id TEXT REFERENCES resources(id),
  pinned_version TEXT,
  activated_at TIMESTAMPTZ,
  PRIMARY KEY (project_id, resource_id)
);

CREATE TABLE memories (
  id TEXT PRIMARY KEY, tier TEXT, project_id TEXT, user_id TEXT,
  content TEXT, importance REAL, created_at TIMESTAMPTZ, decays_at TIMESTAMPTZ,
  source_event_ids TEXT[]
);
CREATE INDEX idx_memories_tier_project ON memories (tier, project_id);

CREATE TABLE "references" (
  id TEXT PRIMARY KEY, source_uri TEXT, trust_tier TEXT, fetched_at TIMESTAMPTZ
);
CREATE TABLE reference_chunks (
  id TEXT PRIMARY KEY, reference_id TEXT REFERENCES "references"(id),
  content TEXT, section_path TEXT, vector_id BIGINT
);

CREATE TABLE executions (
  id TEXT PRIMARY KEY, task_id TEXT, trace_id TEXT, resource_id TEXT REFERENCES resources(id),
  project_id TEXT, status TEXT, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ,
  output_artifact_id TEXT
);
CREATE INDEX idx_executions_trace ON executions (trace_id);

CREATE TABLE execution_events (
  id BIGSERIAL PRIMARY KEY, execution_id TEXT REFERENCES executions(id),
  span TEXT, payload JSONB, ts TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE artifacts (
  id TEXT PRIMARY KEY, producing_execution_id TEXT REFERENCES executions(id),
  content_hash TEXT, storage_uri TEXT, type TEXT, created_at TIMESTAMPTZ
);

CREATE TABLE policies (
  id TEXT PRIMARY KEY, tier TEXT, scope TEXT, rule JSONB, precedence_rank INT
);
```

**Key indexes** (already annotated above): `(type, lifecycle_state)` for the structured-filter stage (§9 step 2, the hottest query in the system); `capability_id` on `resource_capabilities` for capability-graph expansion (§9 step 5); `(resource_id, invoked_at DESC)` on usage for reputation windowing; `trace_id` on `executions` for observability reconstruction; the closure table indexes making ancestor/descendant capability lookups O(1) instead of recursive.


---

## 30. Directory Structure

```
agentos/
├── kernel/                  # Agent reasoning loop, planning, LLM call orchestration
│   ├── planner.py
│   ├── task_loop.py
│   └── llm_client.py
├── registry/                 # Resource Registry (§7, §28)
│   ├── schema/                # JSON Schemas per resource type, migration scripts
│   ├── store.py                 # DB access layer
│   ├── validation.py             # schema + security-scan validation pipeline
│   └── lifecycle.py               # state machine (§19)
├── router/                   # Resource Router (§10)
│   ├── search.py
│   ├── inspect.py
│   ├── resolve.py
│   ├── activate.py
│   ├── execute.py
│   └── release.py
├── capability/                # CapabilityOS (§6)
│   ├── taxonomy.py
│   ├── graph.py                 # graph build/closure maintenance
│   └── classifier.py              # auto-tagging on registration
├── retrieval/                  # Hybrid Retrieval Engine (§9)
│   ├── structured_filter.py
│   ├── bm25.py
│   ├── vector.py
│   ├── fusion.py                  # RRF
│   ├── rerank.py
│   └── dedup.py
├── ranking/                     # Reputation-informed ranking (§18)
│   ├── quality_prior.py
│   └── exploration.py               # bandit exploration bonus
├── context/                      # ContextOS (§14)
│   ├── budgeting.py
│   ├── assembly.py
│   └── compression.py
├── memory/                        # MemoryOS (§12/§15)
│   ├── tiers/
│   ├── consolidation.py              # episodic → semantic promotion job
│   └── retrieval.py
├── resources/                      # Resource content (skills/tools/templates/scripts)
│   ├── skills/
│   ├── tools/
│   ├── mcp/
│   ├── workflows/
│   └── templates/
├── projects/                        # ProjectOS (§13)
│   ├── workspace.py
│   ├── isolation.py                  # sandbox namespace management
│   └── active_resources.py
├── runtime/                          # Execution Runtime (§20, §L4)
│   ├── sandbox/
│   │   ├── container.py
│   │   └── process.py
│   ├── mcp_client.py
│   └── script_runner.py
├── security/                          # SecurityOS (§20)
│   ├── policy_engine.py
│   ├── permission_check.py
│   └── anomaly_detection.py
├── policy/                              # Policy definitions + precedence engine (§21)
│   ├── system_policy.yaml
│   └── precedence.py
├── dependency/                           # Dependency Graph (§17)
│   ├── graph.py
│   └── resolver.py
├── composition/                           # Resource Composition (§22)
│   └── composer.py
├── evaluation/                              # Offline evaluation, A/B gating (§25)
│   ├── eval_sets/
│   └── shadow_test.py
├── observability/                            # Tracing, metrics (§24)
│   ├── tracer.py
│   └── metrics.py
├── storage/                                   # Storage backends (§26)
│   ├── sqlite_backend.py
│   ├── postgres_backend.py
│   ├── faiss_index.py
│   └── object_store.py
├── api/                                        # HTTP API layer (§28)
│   └── v1/
└── cli/                                         # operator CLI (register, inspect, audit)
    └── commands/
```

Each directory's responsibility maps directly to the numbered section above it defines — this is deliberate so the codebase structure and this document stay mutually navigable.

---

## 31. End-to-End Execution Example

**Task**: *"Analyze this repository, identify security vulnerabilities, fix them, run tests, create a commit, and open a GitHub pull request."*

| Stage | What happens | What enters LLM context |
|---|---|---|
| **User Task** | Task text received by Agent Kernel | The task text itself (~40 tokens) |
| **Intent** | Kernel classifies: multi-step, involves security-audit + code-modification + testing + VCS | Nothing new (internal classification, can be a small non-LLM classifier or a cheap LLM call) |
| **Capability Resolution** | CapabilityOS expands intent → `[security.sast, security.dependency-audit, coding.python, testing.unit-testing, vcs.git.commit, vcs.github.pr.create]` | Nothing (graph lookup) |
| **Resource Search** | Router `search` per capability cluster (§9 pipeline) — 100K→~500→~50 candidates per cluster | Nothing yet (all below L1 hydration is internal) |
| **Candidate Ranking** | Fusion + rerank + reputation prior → top 3–5 per cluster | Nothing yet |
| **Skill Activation** | `resolve` composes: `python-security-audit` Skill (covers SAST+dep-audit), a Coding Skill, a Testing Skill, `git.commit` Tool, `github.pr.create` Tool — Composer (§22) orders them | L2 interfaces of the ~5 selected resources loaded (~1,500 tokens) |
| **Tool Discovery** | Within the "GitHub" family, only the `pull_request.create` operation is exposed (§11), not all 40 GitHub operations | ~150 tokens (one operation's schema) |
| **Context Retrieval** | ContextOS pulls: project state summary, relevant References (e.g. the repo's CONTRIBUTING.md testing conventions), Project Memory (prior related decisions) | Budgeted per §14.3 table, ~3,000–5,000 tokens total |
| **Execution Planning** | Composer's ordered plan is the execution plan; Kernel begins step 1 | The plan itself is compact (~300 tokens): ordered resource IDs + declared I/O |
| **Sandbox** | `activate` for `python-security-audit` Skill establishes a container scoped to this project's isolated workspace | Nothing (infra event, logged not shown) |
| **Code Modification** | Skill's L3 instructions load (only now); scripts run inside sandbox, producing a diff | L3 instructions for *this one* Skill (~3,000 tokens); the diff itself, summarized if large |
| **Testing** | Testing Skill activates, runs test suite in the same sandboxed workspace | Test *summary* (pass/fail counts, failing test names) — not full raw test logs unless a failure needs debugging |
| **Evaluation** | Kernel checks: did fixes resolve findings, do tests pass — gates on this before proceeding | Small summary of findings-resolved vs. remaining |
| **Git Commit** | `git.commit` Tool executes with generated message | Commit hash + message (~50 tokens) |
| **GitHub PR** | `github.pr.create` Tool executes; **gated** — per §20.2's trust-tier rule this may require human confirmation before the network call fires | PR URL/number on success |
| **Artifact** | Security report (SARIF) and PR reference stored as Artifacts, addressable by ID | Only the `output_ref`, not the full SARIF body, unless the agent explicitly needs to reason over specific findings next |
| **Feedback** | Execution outcome (success, human accepted the PR) recorded against every resource used in this trace | Nothing (async, post-hoc) |

**Aggregate context cost for the whole multi-step task**: roughly 10,000–20,000 tokens across the entire trace — versus the >1M tokens a flat "describe every available resource" approach would require just to *begin*, before any actual task content. This is the practical payoff of L0–L4 loading (§8) and hierarchical tool discovery (§11) combined.


---

## 32. Token Optimization

### 32.1 Token Cost Categories

| Category | Nature | Optimization strategy |
|---|---|---|
| Static context (system prompt) | Fixed per session | Prompt caching (provider-level) — pay once, reuse across turns |
| Dynamic context (task, project state) | Varies per turn | Compression (§14.4): summarize project state rather than dumping raw file trees |
| Tool schema tokens | Scales with exposed operations | Hierarchical discovery (§11) keeps exposed schema count to ~5–15 operations per turn, not thousands |
| Skill tokens | L3 content of selected skill(s) | Keep SKILL.md concise by design (§12.1); push depth into on-demand `instructions/` sub-files |
| Reference tokens | Chunked retrieval | Only top-ranked chunks (§9), never full documents; semantic compression on long chunks |
| Memory tokens | Tiered, importance-weighted | Most turns need little; Task Memory is the main recurring cost, kept to working-state essentials |
| Execution result tokens | Can be large (logs, diffs, test output) | Summarize beyond the immediately-prior step; large outputs become Artifacts referenced by ID, pulled in only on demand |

### 32.2 Techniques

- **Progressive disclosure**: L0→L4 (§8) — the core mechanism, applied everywhere.
- **Schema compression**: strip non-essential JSON Schema metadata (verbose `description` fields, redundant `examples`) when presenting L2 interfaces for ranking-stage disambiguation; full schema is only needed at actual invocation time, where it's consumed by validation code, not re-read by the LLM as prose.
- **Context deduplication**: if a Reference chunk and a Memory entry say the same thing, the assembler (§14.4) drops the lower-authority duplicate rather than paying for both.
- **Semantic compression**: long execution results (verbose test output, long stack traces) are summarized to their decision-relevant content (which tests failed and why) before entering context; the raw content remains available as an Artifact if deeper debugging is needed.
- **Result summarization**: applied at every step boundary in a multi-step task (§31) — only the most recent step's full detail persists in context; earlier steps compress to one-line outcome summaries.
- **Context caching**: static/slow-changing categories (system instructions, a Project's rarely-changing conventions) are cached at the provider level and/or memoized in ContextOS so repeated turns within a task don't re-spend tokens re-deriving the same content.
- **Tool grouping**: hierarchical families (§11) mean the LLM's tool-call surface at any moment is a small, task-relevant slice, not the global catalog.
- **Lazy loading**: nothing above L1 loads until a resource is a real candidate; nothing above L2 loads until it's selected; L3 loads for the minimum resource set the composed plan actually requires at that step, not the whole plan's resources upfront.

### 32.3 Indicative Token Budgets by Agent Stage

| Stage | Typical token cost |
|---|---|
| Retrieval (search+rank, no LLM call needed if using structured pipeline) | 0 (or ~200–500 if an LLM assist is used for intent extraction) |
| Disambiguation (L2 candidates shown to LLM) | 500–2,000 |
| Single-resource task, full turn | 3,000–8,000 |
| Multi-step composed task (5–7 steps), full trace | 10,000–25,000 |
| Heavy research/reference-grounded task | 15,000–40,000 (dominated by Reference chunk budget) |

---

## 33. Scalability Targets

| Resource count | Metadata size (approx.) | Vector index size (384–1024 dim) | Retrieval latency target (p50) | Notes |
|---|---|---|---|---|
| 10 | ~5 KB | negligible | <5 ms | In-memory, no index needed at all |
| 100 | ~50 KB | ~150 KB (flat) | <5 ms | Flat scan still fastest |
| 1,000 | ~500 KB | ~1.5 MB (flat) | <10 ms | Flat FAISS index fine |
| 10,000 | ~5 MB | ~15 MB (flat) | 10–30 ms | Flat still viable; consider IVF if latency-sensitive |
| 100,000 | ~50 MB | ~150 MB (IVF) | 50–150 ms | IVF index required; structured pre-filter (§9 step 2) does most of the work before vector search even runs |
| 1,000,000 | ~500 MB–1 GB | ~1.5–4 GB (IVF/HNSW, served) | 100–300 ms | Distributed vector service (Qdrant/Milvus) tier; registry sharded by scope/org |

**Graph traversal complexity**: with the closure-table approach (§17.1, §29), ancestor/descendant capability lookups are O(1) index lookups regardless of resource count — they scale with *capability graph* size (which stays in the thousands even at a million resources, since capabilities are shared across many resources), not resource count. **Registry performance**: structured filtering (§9 step 2) is the highest-leverage stage precisely because it's a plain indexed SQL query — it should always be run *before* vector/BM25 stages, cutting the candidate set by 1–2 orders of magnitude before the more expensive stages run, which is what keeps p50 latency bounded even at 10⁶ resources. **Cache requirements**: L0/L1 for the "hot" resource subset (frequently matched capabilities) fits comfortably in a few hundred MB of in-memory/Redis cache even at 10⁶ total resources, since any given task's capability cluster touches a small, repeat-heavy slice of the catalog. **Indexing strategy**: incremental — new/updated resources re-index (FTS + vector + closure-table delta) asynchronously off the write path, never blocking registration on a full reindex.


---

## 34. Technology Selection Summary

| Layer | Minimal tier | Medium tier | Enterprise tier |
|---|---|---|---|
| Metadata store | SQLite | PostgreSQL | Sharded PostgreSQL / distributed SQL |
| Full-text | SQLite FTS5 | Postgres FTS or Elasticsearch | OpenSearch cluster |
| Vector search | FAISS (embedded) | pgvector or FAISS service | Qdrant / Milvus cluster |
| Cache | In-process LRU | Redis (single) | Redis cluster |
| Graph (capability/dependency) | Relational closure table | Relational closure table | Relational closure table, or Neo4j if traversal depth/write concurrency demands it |
| Content storage | Filesystem (git) | Filesystem + object storage | Object storage + CDN |
| Event/async pipeline | In-process queue | Simple task queue | Kafka-class message bus |

Selection is scale-driven, not preference-driven: don't adopt Qdrant/Neo4j/Kafka until the minimal tier's bottleneck is actually measured, not anticipated.

---

## 35. Architectural Trade-offs

| Choice | Favor A when... | Favor B when... |
|---|---|---|
| **RAG vs. structured retrieval** | Content is unstructured prose (References, Skill instructions) — semantic retrieval is essential | Content has clean categorical attributes (type, scope, lifecycle_state, permissions) — a SQL filter is faster, exact, and auditable; use structured filtering *first*, RAG for the semantic residual (§9) |
| **Vector search vs. graph search** | Query is "what's semantically similar to this description" | Query is "what depends on / is composed with this specific node" — graph traversal is exact and explainable where vector similarity would be a lossy approximation |
| **Static tool injection vs. dynamic discovery** | Tool count is small (<20) and stable across the whole session — injection avoids retrieval overhead entirely | Tool count is large or task-dependent — dynamic discovery (§8, §11) is the only approach that scales |
| **Flat vs. hierarchical tool registry** | Tool count is small enough that a flat list's entropy is already low | Tool count is large — hierarchy reduces selection entropy and lets most resolution be deterministic (family/category resolved from task metadata) rather than probabilistic (§11) |
| **Markdown-only skills vs. manifest + Markdown** | A tiny, single-user, informal skill set where ceremony isn't worth it | Any production multi-team system — the manifest is what makes skills searchable, versionable, and permission-checkable without an LLM reading every file (§12) |
| **Central registry vs. decentralized registry** | Org needs consistent security/lifecycle enforcement and cross-team resource reuse (the common production case) | Independent teams need to iterate on private resources with zero coordination overhead — even then, federate multiple registries behind one Router rather than truly decentralizing discovery, or reuse/duplication (§21) becomes unmanageable |
| **SQLite vs. PostgreSQL** | Single machine, single writer, <10⁵ resources, no need for concurrent multi-service access | Multiple services need concurrent write access, or resource count/query load exceeds single-machine comfort (§26.2 tiers) |
| **FAISS vs. Qdrant** | Embedded, single-process, no need for filtered search served over a network | Need filtered ANN as a first-class served capability, horizontal scaling, or multiple consumers querying the same index concurrently |
| **Filesystem vs. object storage** | Single machine, git-friendly versioning of source-controlled resources is valuable | Multi-region access, need for CDN-fronted public resource distribution, or filesystem durability/replication becomes the bottleneck |
| **LLM-based routing vs. deterministic routing** | Genuine ambiguity requiring judgment — e.g., ranking two close, valid candidates by nuanced fit (§9.1) | Anything resolvable by structured data — capability match, permission checks, version constraints — should never be delegated to an LLM call: it's slower, non-deterministic, costs tokens, and is a worse fit for exact-match problems than a SQL query or graph lookup |
| **Online learning vs. offline evaluation** | Narrow, bounded, reversible statistical updates (reputation scores) that self-correct with more data | Anything with structural/lasting effect (capability graph edits, lifecycle promotions, ranking model changes) — must go through gated, reviewed offline evaluation to avoid feedback-loop failure modes (§18.3, §25.1) |

---

## 36. Non-Functional Requirements

| Requirement | Target |
|---|---|
| **Availability** | Registry read path ≥99.9% uptime; degraded-mode operation (cached L0/L1, stale-but-serviceable) tolerated during write-path outages |
| **Consistency** | Strong consistency for permission/policy data (never serve a stale, overly-permissive check); eventual consistency acceptable for reputation scores and search index freshness (seconds-to-minutes lag tolerable) |
| **Latency** | p50 <150ms, p95 <500ms for `search`+`resolve` at 100K resources (§33) |
| **Auditability** | Every `execute` call traceable end-to-end (§24) for a minimum retention period (e.g. 1 year) sufficient for compliance/incident review |
| **Security** | Least-privilege enforced structurally (§20), not advisory; zero standing credentials in LLM context |
| **Extensibility** | New resource type addable by defining a type schema + a thin Type Handler, without touching Registry/Router/Retrieval core |
| **Multi-tenancy** | Strict project/org isolation at the sandbox, memory, and permission layers (§13.3, §15) |
| **Portability** | Minimal tier (§27) runs with zero external service dependencies, enabling local/offline development parity with production topology |

---

## 37. Acceptance Criteria

| Dimension | Quantitative target |
|---|---|
| Resource Discovery | ≥95% of registered active resources reachable via at least one realistic query within top-20 results |
| Capability Matching | ≥90% of manually-labeled (task → correct capability) eval pairs resolve correctly |
| Tool Selection | ≥85% first-choice selection accuracy (no fallback needed) on labeled eval set (§25.2) |
| Retrieval Precision@5 | ≥0.85 on held-out eval queries |
| Retrieval Recall@20 | ≥0.90 on held-out eval queries |
| Context Efficiency | <5% of total task tokens spent on resource metadata (L0–L2) for typical single-resource tasks |
| Token Efficiency | Median task token cost within budget table (§32.3) ±20% |
| Latency | Meets §36 targets at declared scale tier |
| Reliability | ≥99% of `execute` calls terminate in success/clean-failure (not hang/undefined state) |
| Security | Zero permission-boundary violations in red-team testing; 100% of `high`-risk operations gated per policy |
| Isolation | Zero cross-project data leakage in isolation testing |
| Versioning | 100% of dependency edges resolve to a version-compatible target or report `unresolved` explicitly (never silently mismatched) |
| Dependency Resolution | Cycle detection catches 100% of injected test cycles; resolution completes in <100ms for graphs up to 50 nodes |
| Fault Recovery | ≥95% of injected transient-failure scenarios recover via fallback without human escalation |
| Observability | 100% of executions produce a complete, reconstructable trace |
| Scalability | Meets §33 targets at each declared resource-count tier |
| Maintainability | New resource type onboarding requires no core-module changes (schema + handler only) |

---

## 38. Implementation Roadmap

1. **Phase 0 — Foundation (weeks 1–4)**: Resource model + schema (§5), minimal-tier storage (§27: SQLite+FTS5+FAISS+filesystem), basic Registry CRUD + structured-filter search. No ranking sophistication yet — get identity, metadata, and L0–L2 loading working end-to-end for a small (~100 resource) hand-curated set.
2. **Phase 1 — Retrieval & Router (weeks 4–8)**: Full hybrid pipeline (§9: BM25+vector+RRF+rerank), Resource Router with all seven verbs (§10), capability graph + taxonomy (§6) for one domain (e.g. software-development) as a proof case.
3. **Phase 2 — Security & Lifecycle (weeks 8–12)**: Policy Engine + sandboxing (§20), full lifecycle state machine + health checks (§19), dependency graph resolution (§17). This phase gates before any production execution against real credentials/repos.
4. **Phase 3 — ContextOS, MemoryOS, ProjectOS (weeks 12–16)**: Context budgeting/assembly (§14), tiered memory (§15), project isolation (§13). Enables genuinely multi-step, stateful agent tasks.
5. **Phase 4 — Observability & Reputation (weeks 16–20)**: Full tracing (§24), reputation system with anti-feedback-loop safeguards (§18), initial offline evaluation harness (§25).
6. **Phase 5 — Composition & Self-Improvement (weeks 20–26)**: Workflow composition (§22), failure recovery graphs (§23), online/offline learning loop with shadow-testing gates (§25).
7. **Phase 6 — Scale-out (ongoing, triggered by measured need)**: Migrate storage tiers per §26.2 only when the minimal tier's actual bottleneck is measured (not anticipated) — Postgres+pgvector+Redis first, distributed vector/search services only once resource count or query volume genuinely demands it.

Each phase should ship against a growing labeled evaluation set (§37) so regressions in precision/accuracy are caught before the next phase builds on top of a degraded foundation.

---

## 39. Risks

| Risk | Mitigation |
|---|---|
| **Capability graph sprawl** — every new resource inventing its own vocabulary, defeating the taxonomy's purpose | Approval gate on new capability nodes (§6.3); periodic pruning of unused nodes |
| **Popularity feedback loops entrenching mediocre resources** | Bayesian-smoothed, context-bucketed reputation + exploration budget (§18.3) |
| **Registry becomes a bottleneck at write-heavy scale** (many concurrent registrations/health-check updates) | Async event pipeline decoupling writes from the synchronous query path (§26.2 tier 3); structured-filter-first query design keeps reads cheap regardless |
| **Sandbox escape / permission-model gap** | Least-privilege by default, deny-by-default network/filesystem policy, regular red-team testing against the acceptance criteria in §37 |
| **Silent quality degradation** (a resource's external dependency changes upstream, output subtly wrong) | Scheduled health checks + freshness decay in reputation (§18.2) + integration test re-runs on a cadence, not just at registration |
| **Context budget starving reasoning** (metadata/reference bloat crowding out the model's own output space) | Hard floor reserved for reasoning/output in the allocator (§14.3–14.4), never encroached regardless of category pressure |
| **Over-engineering for scale not yet needed** | Explicit scale-driven technology selection (§34) — minimal tier is the default; every heavier tier requires a measured trigger, not anticipation |
| **Human review bottleneck on gated high-risk operations** | Trust-tier calibration reviewed periodically so review load matches actual risk, not blanket caution that trains operators to rubber-stamp |

---

## 40. Final Reference Architecture

```
                         ┌──────────────────────┐
                         │       USER TASK       │
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   TASK / INTENT       │
                         │      ENGINE           │
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    CAPABILITY OS      │   (taxonomy, graph, aliases — §6)
                         └──────────┬────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   RESOURCE ROUTER     │   (search/inspect/resolve/load/
                         └──────────┬────────────┘    activate/execute/release — §10)
                                    │
                    ┌───────────────┼────────────────┐
                    ▼               ▼                 ▼
               Structured        Vector             Graph
                 Search          Search             Search
              (§9 step 2)      (§9 step 4)       (§9 step 5, §17)
                    │               │                 │
                    └───────────────┼─────────────────┘
                                    ▼
                              RERANKER              (§9 steps 6, 12)
                                    │
                                    ▼
                              POLICY ENGINE          (§20 — authZ, sandbox rules)
                                    │
                                    ▼
                           RESOURCE RESOLVER          (§17.2 — dependency resolution)
                                    │
                                    ▼
                           CONTEXTOS / MEMORYOS        (§14, §15 — budgeted assembly)
                                    │
                                    ▼
                               LLM AGENT
                                    │
                                    ▼
                              EXECUTION OS              (§20 — sandbox, MCP, scripts)
                                    │
                                    ▼
                              OBSERVABILITY              (§24 — full trace)
                                    │
                                    ▼
                              EVALUATION                  (§25 — offline gated)
                                    │
                                    ▼
                           FEEDBACK / LEARNING
                                    │
                                    └───────────────┐
                                                     ▼
                                          RESOURCE RANKING UPDATE
                                        (bounded, reversible, online — §25.1)
```

**Summary of the architectural bet**: identity is cheap and always resident; capability is the unit the agent reasons in; content is expensive and loaded only once selection has already narrowed the field by orders of magnitude; policy is enforced structurally, never by the model's own good behavior; and every structural change to ranking or capability taxonomy passes through an offline, gated, reviewable path so the system can improve continuously without the popularity or drift failure modes that plague naive "just let it learn online" designs. This is what lets the same architecture serve 10 resources and 1,000,000 resources without a rewrite — only the storage tier (§26.2) and index technology change; the model, the pipeline stages, and the safety guarantees do not.
