# The Security World Model
## Architecture for a Cybersecurity Knowledge System Powering an Autonomous Defensive Security Agent

**Scope of this document:** authorized defensive security engineering, vulnerability management, detection engineering, incident response, and controlled/authorized security validation. Every execution boundary in this design assumes explicit authorization scoping — the system is a knowledge and reasoning substrate, not an execution substrate, and the two are architecturally separated by design (see §21, §30).

---

## 1. Executive Summary

Most "cybersecurity RAG" systems fail for the same reason: they treat security knowledge as unstructured prose to be chunked and embedded, which destroys the one thing that makes security knowledge useful — its *relational and causal structure*. A CVE means nothing without the CWE it instantiates, the product/version it affects, the technique it enables, the telemetry that exploitation produces, and the detection rule that covers it. A vector index cannot represent "requires," "enables," "detects," "mitigates," or "contradicts." A knowledge graph can.

This document specifies a **Security World Model**: a layered system in which raw security information is normalized into a formal ontology, resolved into entities and typed relations, backed by evidence with provenance and confidence, stored across complementary indexes (graph, vector, keyword, relational, time-series), and exposed to a set of specialized reasoning agents through a policy-gated capability layer. The system is explicitly built so that **knowledge, permission, and execution are three separate planes** — an agent can *know* how a technique works without being *authorized* to run it, and being authorized does not mean *unsupervised* execution against production.

The architecture is designed to answer causal, temporal, and evidentiary questions ("what changed," "why do we believe this," "how confident are we," "what's missing") — not just similarity questions ("what documents look like this query").

---

## 2. Design Principles

1. **Structure over similarity.** Relational and causal structure (graph) is the primary substrate. Vector and keyword search are retrieval accelerants over that structure, not the source of truth.
2. **Evidence is mandatory, not optional.** No claim enters the graph without a `Source`, `Evidence`, and `Confidence` triple. Ungrounded claims are represented as *hypotheses*, never as facts.
3. **Time is first-class.** Every entity and relation carries validity intervals. "Was true" and "is currently believed true" are different queries, never conflated.
4. **Deterministic where possible, LLM where necessary.** Parsing, deduplication, graph algorithms, and policy enforcement are conventional code. LLMs are reserved for semantic understanding, ambiguous entity resolution, and hypothesis generation — where they are cheap in tokens and irreplaceable in capability.
5. **Knowledge ≠ Permission ≠ Execution ≠ Production Access.** These are four separate authorization gates, enforced outside the LLM, never inferred from what the LLM "decided."
6. **Untrusted content cannot rewrite policy.** Anything ingested from the internet, a repo, a tool output, or a prompt is data. Data cannot grant capabilities, no matter how it's phrased.
7. **No agent is its own judge.** Every conclusion that leads to an action passes through an independent Security Judge with separate evidence-review logic.
8. **Explainability is a query, not an afterthought.** Every recommendation must be traceable: `Claim → Evidence → Source → Confidence → Reasoning path` must be reconstructable after the fact.
9. **Conflicting sources are represented, not silently resolved.** `CONTRADICTS` is a first-class edge. The system surfaces disagreement rather than averaging it away.
10. **Scale down before scaling up.** The reference design must run credibly on a single machine (Postgres + pgvector + MinIO) and migrate cleanly to a distributed enterprise stack without a redesign — only a re-deployment.

---

## 3. System Architecture (Layered View)

```text
┌───────────────────────────────────────────────────────────────────────┐
│                            SECURITY AGENTS                             │
│   Orchestrator · Red Agent · Blue Agent · SecEng Agent · ThreatIntel   │
│                         Agent · Security Judge                         │
└───────────────────────────────┬────────────────────────────────────────┘
                                 │  (capability-gated tool calls only)
┌───────────────────────────────┴────────────────────────────────────────┐
│                         REASONING PLANE                                │
│  Intent Classifier · Attack-Defense Graph Reasoner · Risk Engine ·      │
│  Causal Engine · Query Planner · Confidence Propagator                 │
└───────────────────────────────┬────────────────────────────────────────┘
                                 │
┌───────────────────────────────┴────────────────────────────────────────┐
│                         KNOWLEDGE PLANE                                │
│  Knowledge Graph (Neo4j) · Vector Index (pgvector/Qdrant) ·             │
│  Keyword/BM25 Index (OpenSearch) · Relational Store (Postgres) ·        │
│  Time-series Telemetry (ClickHouse)                                    │
└───────────────────────────────┬────────────────────────────────────────┘
                                 │
┌───────────────────────────────┴────────────────────────────────────────┐
│                         EVIDENCE PLANE                                 │
│  Source Registry · Provenance Graph · Object Storage (raw artifacts) · │
│  Ingestion Pipeline · Extraction Pipeline · Knowledge Compiler          │
└───────────────────────────────┬────────────────────────────────────────┘
                                 │
┌───────────────────────────────┴────────────────────────────────────────┐
│               POLICY / CAPABILITY / SANDBOX PLANE                      │
│  Policy Engine · Capability Broker · Risk/Approval Gate · Sandbox ·     │
│  Audit Log (immutable) · Human-in-the-loop Escalation                  │
└──────────────────────────────────────────────────────────────────────┘
```

Each plane is independently deployable, independently testable, and communicates through typed interfaces (§28 Event Architecture, §29 API Architecture) rather than shared mutable state. The Policy/Capability plane sits **underneath** the agents, not inside them — an agent cannot bypass it by reasoning around it, because the agent never holds the credentials or execution path directly.

---

## 4. Security Ontology

The ontology is organized into six top-level domains. Each entity type below is a graph node label; each carries a common base schema plus domain-specific fields.

### 4.1 Common Base Schema (every node)

```json
{
  "id": "uuid",
  "type": "EntityType",
  "name": "string",
  "aliases": ["string"],
  "description": "string",
  "created_at": "iso8601",
  "updated_at": "iso8601",
  "valid_from": "iso8601",
  "valid_to": "iso8601|null",
  "status": "active|deprecated|superseded|revoked|disputed",
  "confidence": 0.0,
  "evidence_ids": ["uuid"],
  "source_ids": ["uuid"],
  "version": "string"
}
```

### 4.2 Threat Domain
`ThreatActor`, `Campaign`, `Malware`, `Ransomware`, `Botnet`, `Attack`, `Tactic`, `Technique`, `SubTechnique`, `TTP`, `ThreatIntelReport`, `Indicator`, `IOC`, `IOA`.

Key fields beyond base: `ThreatActor.motivation`, `ThreatActor.sophistication`, `ThreatActor.attribution_confidence`; `Malware.family`, `Malware.capabilities[]`; `Indicator.ioc_type` (hash/ip/domain/url/mutex), `Indicator.ttl`, `Indicator.first_seen`, `Indicator.last_seen`.

### 4.3 Vulnerability Domain
`CVE`, `CWE`, `CVSSScore`, `Vulnerability`, `Exploit`, `ExploitabilityAssessment`, `Exposure`, `Misconfiguration`, `SecurityWeakness`, `AttackSurfaceElement`.

`Vulnerability` is distinct from `CVE`: a `CVE` is the identifier/record; `Vulnerability` is the graph entity that binds a `CVE` to `AffectedProduct`/`AffectedVersionRange` and carries the *locally assessed* state (§19 distinguishes Vulnerable / Exposed / Exploitable / Actively Exploited / Successfully Exploited as separate boolean-ish fields, never collapsed into one).

### 4.4 Asset Domain
`Host`, `Server`, `Endpoint`, `VM`, `Container`, `K8sWorkload`, `CloudResource`, `Database`, `WebApplication`, `API`, `Service`, `NetworkSegment`, `Identity`, `Account`, `Credential`, `Secret`, `Certificate`, `Package`, `Dependency`, `Repository`, `Artifact`.

`Asset` is an abstract supertype all of the above inherit from, carrying `criticality (1-5)`, `environment (prod/staging/dev)`, `owner`, `data_classification`, `exposure_level (internal/dmz/internet)`.

### 4.5 Control Domain
`Firewall`, `WAF`, `EDR`, `IDS`, `IPS`, `SIEM`, `IAM`, `PAM`, `MFA`, `DLP`, `CSPM`, `CWPP`, `VulnerabilityScanner`, `SecurityPolicy`, `DetectionRule` (with subtypes `SigmaRule`, `YaraRule`, `SuricataRule`, `SIEMQuery`, `EDRQuery`), `SecurityConfiguration`.

`DetectionRule.coverage[]` links to `Technique` nodes it is asserted (and separately, *validated*) to cover — see §17.

### 4.6 Operations Domain
`Detection`, `Alert`, `Investigation`, `ThreatHunt`, `Incident`, `ContainmentAction`, `EradicationAction`, `RecoveryAction`, `HardeningAction`, `RemediationAction`, `Patch`, `ValidationRun`.

### 4.7 Evidence Domain
`Log`, `Event`, `Packet`, `PCAPRef`, `ProcessTreeNode`, `NetworkFlow`, `FileHash`, `RegistryEvent`, `AuthEvent`, `CloudEvent`, `EndpointTelemetryRecord`, `CodeArtifact`, `ConfigArtifact`, `Screenshot`, `SecurityReport`, `Advisory`, `Commit`, `TestResult`, `Evidence` (abstract wrapper), `Source`.

---

## 5. Entity Model — Concrete Node Examples

```json
{
  "id": "cve-2024-3094",
  "type": "CVE",
  "name": "CVE-2024-3094",
  "cvss_v3_1": { "base_score": 10.0, "vector": "AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H" },
  "cwe_ids": ["CWE-506", "CWE-912"],
  "published_at": "2024-03-29T00:00:00Z",
  "affected_products": [{ "vendor": "xz", "product": "liblzma", "version_range": ">=5.6.0,<5.6.1" }],
  "fixed_version": "5.6.1",
  "exploit_maturity": "poc",
  "actively_exploited": false,
  "confidence": 0.98,
  "source_ids": ["src-nvd", "src-cisa-kev"]
}
```

```json
{
  "id": "tech-t1059-001",
  "type": "SubTechnique",
  "name": "PowerShell",
  "parent_technique": "T1059",
  "tactic": ["TA0002"],
  "required_privileges": "user",
  "required_access": "local_shell",
  "target_types": ["Windows Host"],
  "observable_behaviors": ["process_creation:powershell.exe", "script_block_logging"],
  "relevant_logs": ["Sysmon EventID 1", "PowerShell EventID 4104"],
  "detection_opportunities": ["command-line argument anomaly", "encoded command detection"],
  "mitigations": ["M1042 Disable/Remove Feature", "AppLocker constrained language mode"],
  "confidence": 0.95,
  "source_ids": ["src-mitre-attack"]
}
```

---

## 6. Relation Model

Relations are typed, directed, evidence-backed, and time-scoped edges. Minimum relation schema:

```json
{
  "id": "uuid",
  "type": "RELATION_TYPE",
  "source_node": "uuid",
  "target_node": "uuid",
  "confidence": 0.0,
  "valid_from": "iso8601",
  "valid_to": "iso8601|null",
  "evidence_ids": ["uuid"],
  "status": "active|disputed|superseded"
}
```

Core relation types and their semantics:

| Relation | Meaning | Example |
|---|---|---|
| `AFFECTS` | Vulnerability → Asset/Product | CVE-2024-3094 `AFFECTS` liblzma@5.6.0 |
| `EXPLOITS` | Technique/Exploit → Vulnerability | Exploit-X `EXPLOITS` CVE-2024-3094 |
| `ENABLES` | Vulnerability/Weakness → Technique | Weak IAM policy `ENABLES` T1078 |
| `REQUIRES` | Technique → Precondition | T1003 `REQUIRES` local admin |
| `TARGETS` | ThreatActor/Attack → Asset type | APT29 `TARGETS` Identity Providers |
| `OBSERVES` | Detection/Telemetry → Behavior | Sysmon `OBSERVES` process injection |
| `GENERATES` | Technique → Telemetry | T1059.001 `GENERATES` EventID 4104 |
| `DETECTS` | DetectionRule → Technique | Sigma rule `DETECTS` T1059.001 |
| `MITIGATES` | Control → Technique/Vulnerability | AppLocker `MITIGATES` T1059.001 |
| `PATCHES` | Patch → Vulnerability | KB5034123 `PATCHES` CVE-2024-xxxx |
| `RELATED_TO` | generic association | — |
| `SUPPORTED_BY` | Claim → Evidence | — |
| `CONTRADICTS` | Claim/Source → Claim/Source | Source A `CONTRADICTS` Source B |
| `SUPERSEDES` | new knowledge → old knowledge | — |
| `VALIDATED_BY` | Hypothesis → ValidationRun | — |

---

## 7. Attack Knowledge Model

The attack layer is intentionally framework-*agnostic* internally, with MITRE ATT&CK as the default normalization target (because it has the widest interoperability), while every technique node retains a `source_framework` field so D3FEND, OWASP, CAPEC, or internal taxonomies can coexist without collision.

```text
Tactic → Technique → SubTechnique → Prerequisite → AttackCondition → Action → Observable → Telemetry
```

`Technique` node — full field set:

```json
{
  "id": "tech-t1190",
  "name": "Exploit Public-Facing Application",
  "description": "...",
  "preconditions": ["network reachability to public service", "unpatched vulnerable component"],
  "required_privileges": "none",
  "required_access": "network",
  "required_tooling": ["exploit framework or custom PoC"],
  "target_types": ["WebApplication", "API", "Service"],
  "typical_execution_context": "remote, pre-authentication",
  "observable_behaviors": ["anomalous HTTP payload", "unexpected child process of web server"],
  "relevant_logs": ["WAF logs", "web server access logs", "EDR process telemetry"],
  "relevant_telemetry": ["HTTP request body", "process creation events"],
  "detection_opportunities": ["WAF signature match", "process-lineage anomaly (webserver spawning shell)"],
  "mitigations": ["patch management", "WAF virtual patching", "network segmentation"],
  "countermeasures": ["rate limiting", "input validation"],
  "related_vulnerabilities": ["cve-*"],
  "related_attack_paths": ["path-uuid-*"],
  "related_incidents": ["incident-uuid-*"],
  "confidence": 0.9,
  "evidence_ids": ["ev-*"],
  "version": "ATT&CK v15",
  "last_updated": "2025-04-23T00:00:00Z"
}
```

---

## 8. Defensive Knowledge Model

The defensive graph is the structural mirror of the attack graph, enabling bidirectional reasoning:

```text
Attack → Behavior → Observable → Telemetry → Detection → Alert → Investigation
       → Containment → Eradication → Recovery → Hardening → Validation
```

Bidirectional query patterns the model must support natively (graph traversal, not LLM inference):

- **Forward:** `Technique → GENERATES → Telemetry` (what logs *should* exist if this happened)
- **Backward:** `Telemetry → GENERATES⁻¹ → Technique` (what could have produced this telemetry — a candidate set, not a single answer)
- **Alert explanation:** `Alert → OBSERVES⁻¹ → Behavior → part_of⁻¹ → Technique` (candidate techniques ranked by confidence)
- **Exploitation forecasting:** `Vulnerability → ENABLES → Technique → GENERATES → Telemetry` (what would exploitation look like on the wire/host)
- **Coverage check:** `DetectionRule → DETECTS → Technique`, intersected against the org's actual `Telemetry` availability, yields *actual* vs *claimed* coverage
- **Gap analysis:** `Technique NOT IN (Technique ← DETECTS ← DetectionRule)` for techniques relevant to the org's asset/tactic profile → the detection backlog

This backward/forward symmetry is why the model is a **graph**, not a document store: "what could explain this" is a graph query (`MATCH (t:Telemetry {id:$x})<-[:GENERATES]-(tech:Technique) RETURN tech`), not a semantic-similarity guess.

---

## 9. Attack-Defense Graph

Unified traversal surface combining §7 and §8 into one queryable structure:

```text
Asset → Exposure → Vulnerability → Technique → Behavior → Telemetry → Detection → Response → Mitigation → Patch
```

Representative Cypher (Neo4j) for the canonical questions in the prompt:

```cypher
// "What can attack this asset?"
MATCH (a:Asset {id:$assetId})<-[:AFFECTS]-(v:Vulnerability)<-[:EXPLOITS]-(t:Technique)
RETURN t, v ORDER BY v.cvss_score DESC;

// "What attack paths reach this asset?" (bounded-depth path search)
MATCH p = (entry:Asset {exposure_level:'internet'})-[:REACHES|ENABLES|GRANTS*1..6]->(target:Asset {id:$assetId})
RETURN p ORDER BY reduce(risk=0, r IN relationships(p) | risk + r.risk_weight) DESC LIMIT 10;

// "Which detection rules cover this technique?"
MATCH (r:DetectionRule)-[:DETECTS]->(t:Technique {id:$techId})
WHERE r.status = 'active'
RETURN r;

// "Which attacks are currently undetected?"
MATCH (t:Technique)
WHERE t.id IN $relevantTechniqueIds
  AND NOT (t)<-[:DETECTS]-(:DetectionRule {status:'active'})
RETURN t AS undetected_technique;

// "Which controls break this attack path?"
MATCH p = (entry)-[rels*]->(target:Asset {id:$assetId})
UNWIND rels AS r
MATCH (c:Control)-[:MITIGATES]->()
WHERE r.enabled_by IN [(c)-[:MITIGATES]->(x) | x.id]
RETURN DISTINCT c;

// "Shortest path to a critical asset"
MATCH p = shortestPath((entry:Asset {exposure_level:'internet'})-[*..8]->(critical:Asset {criticality:5}))
RETURN p;
```

`REACHES` / `ENABLES` / `GRANTS` are derived, materialized edges computed by the Attack Path Engine (§10) from lower-level `AFFECTS`/`EXPLOITS`/`REQUIRES` chains — they are not hand-authored, to avoid drift between raw facts and derived reachability.

---

## 10. Attack Path Model

Infrastructure graph:

```text
Internet → PublicService → Application → Identity → Credential → InternalService → PrivilegedAccount → CriticalAsset
```

### 10.1 Algorithms

- **Shortest attack path:** Dijkstra/BFS over the reachability graph, edge weight = 1 (hop count) or = exploit-difficulty score.
- **Highest-risk attack path:** modified Dijkstra where edge weight = `-log(P(traverse))`, so shortest path = highest joint probability path (standard attack-graph technique from prior academic work — MulVAL-style probabilistic attack graphs).
- **Privilege escalation path:** subgraph search restricted to edges tagged `privilege_gain=true`.
- **Lateral movement path:** subgraph search restricted to edges tagged `movement=true` with same-or-lower privilege requirement.
- **Credential exposure path:** path search seeded from `Credential`/`Secret` nodes with `exposure_level != internal`.
- **Blast radius:** reverse BFS from a compromised node bounded by trust-boundary edges (`NetworkSegment`, `IAM boundary`) — count of reachable `CriticalAsset` nodes weighted by `criticality`.
- **Attack-path centrality:** betweenness centrality over the attack graph — nodes/edges that appear on the most weighted shortest paths are the highest-leverage choke points for defense investment.
- **Control coverage:** for each edge on a path, check `MITIGATES` edges from active `Control` nodes; an uncovered edge is a coverage gap.
- **Attack-path disruption:** for each control candidate, simulate removal of the edges it mitigates and recompute shortest/highest-risk path; rank controls by Δrisk — this directly answers "which control gives the greatest risk reduction."

### 10.2 Risk Model

The prompt's naive formula (`Σ NodeRisk + Σ EdgeRisk − Σ ControlEffectiveness`) is linearly additive, which is wrong for two reasons: (1) risk along a path is *conjunctive* (all steps must succeed — multiplicative in probability, not additive), and (2) controls don't subtract a flat amount, they multiplicatively reduce the *probability* of traversing the edge they cover. Recommended formulation:

```text
P(path succeeds) = Π over edges e in path of  P_base(e) × (1 − ControlEffectiveness(e))

Risk(path) = P(path succeeds) × Impact(target_asset)

Impact(asset) = f(criticality, data_classification, business_downtime_cost)
```

`P_base(e)` is itself decomposed from exploit maturity, required privilege level, and public exposure (calibrated from historical validation data in Episodic Memory, §25, not guessed). This gives a probabilistically coherent ranking and makes "greatest risk reduction" a well-defined optimization: choose the control(s) that minimize `max over paths of Risk(path)` (a min-max / vertex-cover-like problem over the attack graph — solvable with a greedy set-cover heuristic in practice, exact ILP for small graphs).

---

## 11. Evidence Model & Provenance

```text
Claim → Evidence → Source → Timestamp → Confidence
```

```json
{
  "claim_id": "claim-001",
  "statement": "T1059.001 is detectable via PowerShell Script Block Logging (Event 4104)",
  "evidence": [
    { "evidence_id": "ev-101", "source_id": "src-mitre-attack", "source_type": "framework", "excerpt_ref": "internal-note-not-verbatim", "published_at": "2024-10-01", "retrieved_at": "2025-08-01" },
    { "evidence_id": "ev-102", "source_id": "src-lab-validation-44", "source_type": "experimental_validation", "published_at": "2025-06-12", "retrieved_at": "2025-06-12" }
  ],
  "confidence": 0.93,
  "status": "active"
}
```

Provenance graph: every `Evidence` node links `SUPPORTED_BY` to exactly one `Source`; every derived `Claim`/relation links `SUPPORTED_BY` to one-or-more `Evidence`. This makes "why do you believe this" a two-hop graph query, not a re-derivation.

Source registry entries include `source_type ∈ {framework, vendor_advisory, cve_db, cert, research, repo, tool_output, incident_record, internal_telemetry, patch, commit, detection_rule, lab_experiment}`, each with a base **reliability prior** (see §12) used in confidence scoring.

---

## 12. Knowledge Confidence Model

Confidence is decomposed, never asserted as a single opaque number pulled from an LLM:

```text
Confidence = w1·SourceReliability + w2·EvidenceQuality + w3·Recency
            + w4·CrossSourceAgreement + w5·ExperimentalValidation − w6·ModelUncertainty
```

- **SourceReliability**: static prior per `source_type` (e.g., CISA KEV = 0.95, unverified blog = 0.4), adjustable by historical accuracy tracking.
- **EvidenceQuality**: structured evidence (CVE record, signed advisory, lab log) > unstructured prose > single unverified claim.
- **Recency**: exponential decay `e^{-λ·(now - published_at)}`, λ tuned per domain (exploit intel decays fast; CWE taxonomy barely decays).
- **CrossSourceAgreement**: fraction of independent sources asserting the same claim without a `CONTRADICTS` edge.
- **ExperimentalValidation**: boolean/graded boost when a `ValidationRun` (§28) empirically confirmed the claim in a lab/controlled environment — this is the strongest evidence class and is tracked separately from "theoretically true per a document."
- **ModelUncertainty**: penalty applied when an LLM performed extraction/inference rather than deterministic parsing (§14) — LLM-derived claims start at a confidence ceiling below deterministic extraction until corroborated.

Confidence **propagates** through multi-hop reasoning as the product of the confidences of each edge/claim used in the chain (independence assumed as a conservative approximation), so a conclusion built on five weak links cannot present as strong as one built on a single well-validated fact. The reasoning engine (§40) is required to report the weakest link in the chain alongside the final confidence.

---

## 13. Temporal Knowledge Model

Every node/edge carries `created_at, updated_at, published_at, discovered_at, fixed_at, deprecated_at, revoked_at, valid_from, valid_to, version, affected_version_range, fixed_version, source_freshness, evidence_freshness`.

Query modes, implemented as distinct graph query parameters (not separate systems):

```cypher
// "Currently believed true" — default view
MATCH (n) WHERE n.valid_to IS NULL AND n.status = 'active' RETURN n

// "As of a point in time" — historical/bitemporal query
MATCH (n) WHERE n.valid_from <= $asOf AND (n.valid_to IS NULL OR n.valid_to > $asOf) RETURN n

// Versioned / deprecated knowledge
MATCH (n)-[:SUPERSEDES]->(old) WHERE old.status = 'deprecated' RETURN old, n

// Conflicting knowledge
MATCH (a)-[:CONTRADICTS]->(b) RETURN a, b

// Emerging knowledge — high rate of new evidence, not yet high confidence
MATCH (n) WHERE n.created_at > $recentWindow AND n.confidence < 0.7 RETURN n
```

This bitemporal design (`valid_from/valid_to` = when the *fact* was true in the world; `created_at/updated_at` = when *we learned it*) is required for questions like "was this host vulnerable last March" versus "is this host vulnerable now," which are different queries with potentially different answers if telemetry or patch state changed in between.

---

## 14. Knowledge Ingestion Pipeline

```text
Internet / Internal Sources → Crawler/API Collector → Document Parser → Normalizer → Deduplication
  → Security Entity Extraction → Relation Extraction → Ontology Mapping → Evidence Validation
  → Knowledge Graph + Vector Index + Search Index
```

- **Collectors** are source-specific and scheduled independently (NVD API poller, CISA KEV feed, vendor advisory RSS, MITRE ATT&CK STIX bundle, internal SIEM export, internal ticketing export). Each collector emits a `RawDocument` with a stable `source_id` + `retrieved_at` and writes the raw bytes to object storage before any parsing — the raw artifact is immutable ground truth for later re-processing.
- **Format support:** HTML, Markdown, PDF, JSON/JSONL, CSV, STIX/TAXII, XML, YAML, source code, config files, log lines, PCAP metadata (never raw packet payloads with sensitive content beyond metadata unless explicitly authorized and access-controlled), SBOM (CycloneDX/SPDX).
- **Normalizer** converts each format into a common `NormalizedDocument` IR (title, body segments, structured tables, code blocks, metadata) — deterministic, format-specific parsers (e.g., `stix2` library for STIX, `cvelib`-style parsers for NVD JSON), no LLM involved at this stage.
- **Deduplication** is content-hash + fuzzy-similarity (MinHash/SimHash) based, run before extraction to avoid wasting extraction cost on duplicates, and again after extraction on the resulting entities (two documents describing the same CVE should not create two `Vulnerability` nodes).
- **Incremental & resumable:** every collector maintains a durable cursor (last-seen ID/timestamp) in Postgres; ingestion runs are idempotent — re-running with an existing cursor produces no duplicate writes (upsert on `(source_id, external_id)`).

Failure handling: a collector or parser failure quarantines the raw document with an error record rather than dropping it silently, and retries with backoff; a poison document (repeatedly fails parsing) is flagged for human review, never repeatedly re-attempted forever.

---

## 15. Knowledge Extraction Pipeline

Hybrid, cost-aware, deterministic-first:

```text
Regex + Parser + Rule Engine   → structured fields (CVE IDs, IPs, hashes, versions, CVSS vectors)
NER + Entity Linking           → named entities (product names, threat actor names) resolved to canonical graph nodes
Embedding                      → semantic vectors for retrieval, not for fact extraction
LLM                            → relation extraction from prose, ambiguous entity disambiguation, hypothesis generation
```

**Rule of thumb enforced by the pipeline design:** if a field can be extracted with a regex or a known schema parser (CVE IDs, CVSS vectors, file hashes, IP/CIDR, MITRE technique IDs), it *must* be — LLM extraction for these is banned by policy because it is strictly worse (slower, costlier, non-deterministic) for a solved problem. LLM extraction is reserved for: resolving "this blog post's vague description maps to which CWE," extracting a causal relation from a paragraph of prose, or disambiguating "Apache" (the HTTP server vs. Apache Struts vs. Apache Kafka) using surrounding context.

Every LLM-extracted relation is written with `extraction_method: "llm"` and a lower confidence prior (§12), and is queued for either cross-source corroboration or human review before being promoted to `status: active` if it feeds a high-impact conclusion.

---

## 16. Security Knowledge Compiler

A deliberate "compiler" framing because the transformation from raw text to graph facts should be as reproducible and debuggable as compiling source code:

```text
Security Documents → Lexer/Parser → Security AST → Knowledge IR → Entity Resolution
  → Relation Resolution → Graph Construction → Validation → Indexes
```

- **Security AST**: a document-level parse tree — sections, tables, code blocks, CVE mentions, version strings — independent of ontology mapping. Built once per document, cacheable.
- **Knowledge IR**: AST nodes mapped to *candidate* ontology entities/relations, each with an extraction-method tag and raw provenance pointer, before resolution against the existing graph.
- **Entity resolution**: candidate entities are matched against existing graph nodes by canonical ID (CVE ID, CPE string) first, then by normalized-name + type + fuzzy match, then (last resort, LLM-assisted) by contextual disambiguation. Unmatched candidates become new nodes; matched candidates trigger an update-or-merge.
- **Relation resolution**: candidate relations are checked against existing relations of the same type/endpoints; a new relation with the same semantics is merged (evidence appended, confidence recomputed) rather than duplicated.
- **Conflict resolution**: if a new relation contradicts an existing active relation (e.g., new source claims "not detectable" where an active claim says "detectable"), the compiler does **not** silently overwrite — it creates a `CONTRADICTS` edge and flags both for confidence re-evaluation (§32).
- **Version resolution**: superseding knowledge (e.g., ATT&CK v16 replacing v15 technique description) creates a `SUPERSEDES` edge and marks the old node `deprecated` rather than deleting it — history is preserved for temporal queries (§13).
- **Validation** stage runs schema validation (every node/edge matches its ontology type schema), referential integrity (no dangling edges), and policy checks (no node/edge can grant a `Capability`, see §21) before committing to the graph and indexes atomically.

---

## 17. Hybrid Retrieval Architecture

Vector search alone is rejected as the primary retrieval mechanism because security queries are frequently exact-match (a specific CVE ID, technique ID, IP address) or relational ("what detects this technique") — neither of which vector similarity handles well.

```text
User Query → Intent Classification → Entity Extraction → Query Expansion
  → [Keyword Retrieval | Vector Retrieval | Graph Retrieval] (parallel)
  → Metadata Filtering → Reranking → Evidence Validation → Context Construction → Security Reasoning
```

**When each method fires:**

| Method | Best for | Example |
|---|---|---|
| Keyword/BM25 | exact identifiers, rare tokens | "CVE-2024-3094", "T1059.001" |
| Dense vector | conceptual/semantic similarity, paraphrase | "how do attackers steal cloud credentials from metadata services" |
| Graph traversal | relational/multi-hop questions | "what detects techniques enabled by this vulnerability" |
| Metadata filter | scoping | environment=prod, severity>=high, published after date X |
| Entity linking | grounding free text to canonical nodes | resolves "the xz backdoor" → CVE-2024-3094 |
| Reranking | precision on top-k | cross-encoder rerank of the union of candidate sets |

Intent classification is a lightweight deterministic/small-model classifier (not the main LLM) mapping the query to one of a fixed set of query templates (§27 Query Language) — "attack path," "detection coverage," "vulnerability lookup," "incident investigation," "free-form research" — which determines which retrieval branches are invoked at all (a CVE-ID-shaped query skips vector search entirely and goes straight to keyword+graph).

Evidence validation is a post-retrieval filter: any candidate context chunk lacking a resolvable `Source`/`Evidence` link is either dropped or explicitly labeled "unverified" before being handed to the reasoning engine — this is the primary defense against the LLM presenting retrieval noise as fact.

---

## 18. Security Knowledge Query Language (SKQL)

A small DSL that compiles deterministically to graph/vector/SQL calls, so agents (and humans) issue structured intent rather than free-text that has to be re-interpreted every time.

```text
FIND attack_paths
FROM asset:production-api
WHERE risk > 0.6 AND privilege_escalation = true
ORDER BY risk DESC
LIMIT 10
```
compiles to the shortest/highest-risk path Cypher of §9/§10 with `risk` computed via §10.2's formula.

```text
FIND detections
FOR technique:T1190
WHERE telemetry_available = true
```
compiles to: `MATCH (r:DetectionRule)-[:DETECTS]->(t:Technique{id:'T1190'}) WHERE r.status='active' AND EXISTS { (t)-[:GENERATES]->(:Telemetry)<-[:INGESTS]-(:TelemetrySource {available:true}) } RETURN r`.

```text
FIND vulnerabilities
FOR asset:web-app-7
WHERE actively_exploited = true
```
compiles to a join across `Vulnerability`→`AFFECTS`→`Asset` filtered on the KEV-sourced `actively_exploited` flag (a deterministic field, never LLM-guessed).

Grammar sketch:
```text
query      := "FIND" target ("FROM" scope)? ("FOR" scope)? ("WHERE" predicate)? (order)? (limit)?
target     := "attack_paths" | "detections" | "vulnerabilities" | "assets" | "incidents" | "evidence" | ...
predicate  := comparison (("AND"|"OR") comparison)*
comparison := field op value
```
Each `target` has a registered compiler function mapping to Cypher/SQL/vector-filter combinations; adding a new query type means registering a new compiler, not touching the LLM prompt.

---

## 19. Agent Architecture

```text
                     Security Orchestrator
        ┌────────────────┬──────────────────┬────────────────┐
        ▼                ▼                  ▼                ▼
   Threat Intel      Red Agent          Blue Agent       SecEng Agent
      Agent                            (SOC Agent)     (AppSec/CloudSec)
        └────────────────┴──────────────────┴────────────────┘
                                  ▼
                           Security Judge
                                  ▼
                          Knowledge Updater
```

| Agent | Responsibilities | Tools (capability-scoped) | Knowledge access | Trust boundary |
|---|---|---|---|---|
| Orchestrator | decomposes user/system goals into sub-tasks, routes to specialists, aggregates results | none directly execution-capable | full read | cannot itself invoke high-risk tools |
| Threat Intel | ingests/correlates external intel, tracks actors/campaigns | search, fetch (read-only) | full read, write to Threat domain (queued for Judge) | no execution capability |
| Red Agent | plans and (only under explicit authorization) executes controlled validation tests | scoped scanner/exploit-validation tools in sandbox only | Attack + Asset domain read, Red playbook write | **no production execution**; sandbox-only by default, production requires human approval token (§21) |
| Blue Agent (SOC) | detection engineering, alert triage, threat hunting, incident investigation | SIEM/EDR query (read), detection-rule deployment (write, gated) | Defense + Evidence domain read/write | rule deployment to production requires approval |
| SecEng Agent | AppSec/CloudSec reviews, remediation recommendations, hardening plans | code/config read, PR creation (gated) | Vulnerability + Control domain read/write | cannot merge/deploy without human approval |
| Security Judge | independent verification of any conclusion feeding an action | read-only across all domains + evaluation tools | full read | cannot be bypassed; cannot be the same process/context as the producing agent |
| Knowledge Updater | commits validated conclusions back into the graph via the Compiler (§16) | graph write (via Compiler validation) | full read/write, but only through the compiler's conflict/validation gate | cannot skip Judge sign-off for high-impact updates |

Each agent operates in its own context/session with only the memory partitions (§24) and capabilities (§21) it needs — least privilege applies to agents exactly as it applies to human operators.

---

## 20. Red Team Architecture

Explicit separation the prompt demands, enforced structurally rather than by prompt instruction alone:

```text
Knowledge  →  Planning  →  Simulation  →  Validation  →  Execution
```

- **Knowledge**: the Red Agent can *read* the full attack knowledge model (techniques, exploits, attack paths) at all times — knowing how T1190 works is not a privileged operation.
- **Planning**: producing a proposed test plan (which techniques, against which sandboxed/authorized target, expected telemetry) is also unprivileged — it's a document, not an action.
- **Simulation**: dry-run / tabletop execution against a modeled (non-live) representation of the environment — no real tool invocation, used to sanity-check a plan before spending a real capability grant.
- **Validation**: execution against an explicitly authorized, scoped, non-production sandbox environment, gated by a `Capability` grant (§21) with a defined TTL and target allowlist.
- **Execution**: the only stage that can touch anything resembling production, and only ever under a human-approved, time-boxed, fully audited capability grant with defined rollback — this stage does not exist for the Red Agent by default in this architecture; it is an explicit, rare, human-escalated exception path, never the default flow.

Domain coverage: reconnaissance, asset discovery, service enumeration, vulnerability assessment, attack-path analysis, privilege analysis, identity security review, AppSec testing, cloud security assessment, container security assessment, network security assessment, adversary simulation planning, controlled exploit validation (sandbox only), security-control validation — all represented as `Playbook` nodes in Procedural Memory (§24), each tagged with the minimum stage (Knowledge/Planning/Simulation/Validation/Execution) it requires, so the policy engine can gate at the playbook level.

---

## 21. Blue Team Architecture

```text
Asset Discovery → Security Monitoring → Detection Engineering → Threat Hunting → Alert Triage
  → Incident Investigation → Containment → Eradication → Recovery → Threat Intelligence
  → Hardening → Validation
```

Telemetry sources modeled as first-class `TelemetrySource` nodes (SIEM, EDR, NDR, IDS/IPS, WAF, IAM logs, cloud audit logs, endpoint telemetry, auth logs, DNS logs, proxy logs, firewall logs, process telemetry, network flow telemetry), each with an `availability` flag and `retention_days` — this is what makes the "telemetry_available = true" predicate in SKQL (§18) meaningful rather than assumed.

**Alert triage → investigation loop (hypothesis-driven, §22):** an `Alert` is linked via `OBSERVES⁻¹` to candidate `Behavior`/`Technique` nodes; the Blue Agent opens an `Investigation` carrying a ranked hypothesis list, and each investigative action (query a log source, pull a process tree, check an IOC) either strengthens or weakens specific hypotheses — this is a Bayesian-flavored triage loop, not a single LLM guess.

---

## 22. Detection Knowledge Graph

```text
Technique → Behavior → TelemetrySource → Field → DetectionLogic → DetectionRule → Alert → InvestigationPlaybook
```

Formats supported as structured `DetectionRule` subtypes: Sigma, YARA, Suricata, SIEM query (Splunk SPL / KQL), EDR query, cloud-native detection (GuardDuty/Defender rule refs). Rule content is stored as an opaque artifact (object storage) plus structured metadata (`technique_coverage[]`, `telemetry_dependencies[]`, `false_positive_notes`, `last_validated_at`) so coverage queries never need to parse rule syntax at query time.

Coverage metrics computed as graph queries, not estimates:

```text
TechniqueCoverage   = |{t ∈ RelevantTechniques : ∃ active DetectionRule DETECTS t}| / |RelevantTechniques|
TelemetryCoverage   = |{s ∈ RequiredTelemetrySources : s.availability = true}| / |RequiredTelemetrySources|
DetectionCoverage   = TechniqueCoverage × TelemetryCoverage   (a rule with no telemetry backing it is not real coverage)
FalsePositiveRisk   = historical_fp_count / alert_count over trailing window, per rule
DetectionBlindSpot  = RelevantTechniques − (Technique with active, telemetry-backed DetectionRule)
```

`DetectionCoverage` deliberately multiplies rather than treats rule-existence alone as coverage — a Sigma rule with no matching log source ingested is a paper rule, and the model must say so explicitly rather than reporting false confidence.

---

## 23. Incident Response Knowledge Model

```text
Incident → Initial Evidence → Hypothesis → Investigation → Scope → Containment → Eradication → Recovery
  → Lessons Learned → Knowledge Update
```

Hypothesis tracking structure (maintained per active investigation, queryable at any point):

```json
{
  "hypothesis_id": "h-1",
  "statement": "Initial access via T1190 against public API, CVE-2024-xxxx",
  "evidence_for": ["ev-201", "ev-204"],
  "evidence_against": ["ev-207"],
  "confidence": 0.62,
  "next_investigation_step": "pull process tree from EDR for host web-03 in window T-2h..T+1h"
}
```

Multiple hypotheses are tracked concurrently (never collapsed to one prematurely); each investigative action is logged against the hypothesis(es) it targets, and the Security Judge reviews the final hypothesis-to-conclusion mapping before an incident is closed with a root-cause determination — root cause is a claim like any other, requiring evidence and confidence, not asserted from a single LLM pass.

---

## 24. Vulnerability Intelligence Layer, AppSec, Cloud, Container/K8s, Supply Chain

### 24.1 Vulnerability Graph
```text
CVE ↕ CWE ↕ CVSS ↕ AffectedProduct ↕ AffectedVersion ↕ Exploitability ↕ Technique ↕ Detection ↕ Mitigation ↕ Patch
```
Five distinct, non-equivalent states tracked as **separate boolean/graded fields** on the local `Vulnerability` assessment node (never collapsed):
```json
{
  "vulnerable": true,          // affected version present
  "exposed": true,             // reachable given current network/access controls
  "exploitable": true,         // a working exploit path exists given current mitigations
  "actively_exploited": false, // exploited in the wild per threat intel (e.g., CISA KEV)
  "successfully_exploited": false // exploited against *this* environment, per incident evidence
}
```
This directly answers the prompt's requirement — a host can be `vulnerable` (unpatched) but not `exposed` (firewalled off), or `exposed`+`exploitable` but with no evidence of `actively_exploited`/`successfully_exploited` — and the reasoning engine must never conflate these when producing risk statements.

### 24.2 Application Security
```text
CodePattern → Weakness (CWE) → Vulnerability → AttackScenario → Detection → FixPattern → RegressionTest
```
Covers: authN/authZ, session management, input validation, injection, XSS, SSRF, CSRF, path traversal, insecure deserialization, API security, business-logic flaws, cryptography misuse, secrets management, dependency/supply-chain weaknesses. Each `FixPattern` links to a `RegressionTest` template so remediation validation (§28) is concrete and re-runnable, not a one-off claim.

### 24.3 Cloud Security
Domains: IAM, networking, storage, compute, containers, Kubernetes, serverless, secrets, instance-metadata services, logging, configuration, identity federation, cloud privilege escalation, cloud-specific attack graphs (e.g., `Role → AssumeRole → Role → S3:GetObject` chains modeled the same way as on-prem attack paths in §10, just with cloud-specific edge types `ASSUMES_ROLE`, `HAS_POLICY`, `GRANTS_PERMISSION`).

### 24.4 Container / Kubernetes
```text
Image → Package → Vulnerability → Container → Pod → ServiceAccount → RBAC → Node → Cluster
```
SBOM ingestion (§14) populates `Image → Package` edges; RBAC bindings populate `ServiceAccount → RBAC → Node` reachability, feeding the same attack-path engine (§10) so a container escape path is just another attack path with cluster-specific edge types.

### 24.5 Supply Chain
```text
Repository → Build → Dependency → Package → Artifact → ContainerImage → Deployment
```
Concepts modeled explicitly: SBOM (CycloneDX/SPDX ingestion), dependency graph (transitive closure), provenance (SLSA-style build attestations as `Evidence`), signing/verification status as a `ConfigArtifact` field, artifact integrity (hash chain), known-malicious package matching (against a maintained `MaliciousPackage` list, deterministic lookup not LLM judgment), build-compromise indicators, and CI/CD pipeline configuration as a first-class `Asset` subtype with its own exposure/criticality scoring.

---

## 25. Security Tool Registry

```json
{
  "tool_id": "tool-nmap",
  "purpose": "network/service discovery",
  "input_schema": {"target_cidr": "string", "ports": "string"},
  "output_schema": {"open_ports": "array", "services": "array"},
  "capabilities": ["network.scan"],
  "required_privileges": "network access to target",
  "risk_level": "low-medium",
  "supported_platforms": ["linux", "macos"],
  "safe_usage_constraints": ["target must be in authorized_scope allowlist", "rate-limited"],
  "detection_footprint": "generates connection/SYN telemetry on target-side IDS",
  "evidence_produced": ["ScanResult artifact linked as Evidence"]
}
```

Tool *knowledge* (the registry entry above) is always readable by any agent that needs to reason about what a tool does. Tool *permission* (whether this session/agent/user is allowed to invoke it) is a separate Capability grant (§21). Tool *invocation* is the actual call, always mediated by the Capability Broker, never a direct agent→tool connection. Tool *result* is written back as `Evidence` with full provenance, not silently consumed and discarded. Registry entries and their outputs are treated as **data**, never as instructions — a tool's output text cannot itself grant capabilities or alter policy (§27).

---

## 26. Security Judge

An independent verification stage — architecturally a separate process/context from whichever agent produced a conclusion, so it cannot inherit that agent's reasoning bias or blind spots.

Checks performed before any conclusion is allowed to (a) update the knowledge graph as `active`, or (b) trigger a downstream action:

- **Factual correctness** — do cited evidence nodes actually say what the claim says (spot-check against `Source`, not just presence of an evidence link).
- **Evidence quality** — is the evidence class strong enough for the claim's stakes (e.g., a production remediation claim needs more than a single unverified blog post).
- **Reasoning consistency** — does the chain of graph hops actually support the conclusion, or does it contain a non-sequitur (e.g., technique relevance inferred from an unrelated CWE).
- **Attack-path validity** — does the proposed path respect precondition edges (`REQUIRES`) at every hop, not just connectivity.
- **Detection/remediation validity** — does the proposed detection rule reference telemetry that is actually available; does the remediation plan address the root cause, not just the symptom.
- **Confidence calibration** — does the reported confidence match the evidence decomposition in §12, or was it inflated.
- **Policy compliance & authorization scope** — is the conclusion within the requester's authorized scope (asset allowlist, environment).

A failed Judge review routes back to the producing agent with the specific failure reason (not a generic rejection), and repeated failures on the same conclusion escalate to human review rather than looping indefinitely.

---

## 27. Policy, Capability, and Permission Architecture

```text
LLM → Intent → Policy Engine → Capability Check → Risk Engine → Sandbox → Tool Execution
```

The LLM never holds credentials, never directly opens a network socket, and never directly writes to production stores. It emits a structured **Intent** (tool name + parameters); everything after that is conventional software.

Capability namespace (least-privilege, explicit grants only):
```text
filesystem.read        filesystem.write
network.egress         network.scan
git.read                git.write
container.run
cloud.read              cloud.deploy
secret.use
detection.deploy        detection.read
production.access       sandbox.access
```

Four separate authorization planes, checked independently — **holding one never implies another**:
```text
Knowledge Permission   — can this agent/session read this part of the graph?
Tool Permission        — can this agent/session invoke this tool at all?
Execution Permission   — is there an active, scoped, time-boxed Capability grant for this specific action?
Production Permission  — is the target environment production, and if so is there human approval on record?
```

High-risk operations (anything touching `production.access`, `cloud.deploy`, `secret.use`, or live exploit validation) require an explicit human-approval token issued out-of-band, with a defined TTL, target allowlist, and full audit trail — the policy engine rejects the call outright if the token is missing, expired, or scope-mismatched; the LLM cannot self-issue or reason its way around this because the check happens in code the LLM has no write access to.

---

## 28. Prompt Injection Defense

Trust levels, strictly ordered, with explicit rules about what each can and cannot do:

```text
System Policy         (highest trust — never overridden by anything below)
Developer Instruction
User Instruction
Internal Telemetry / Tool Output (from *trusted* internal tools)
Repository Content / Documentation / Internet Content / External Tool Output  (lowest trust — treated as data)
```

Rules enforced structurally, not just by prompt wording:

- Content originating from repository files, fetched web pages, ingested advisories, or third-party tool output is tagged `trust_level: untrusted_data` at ingestion and carried through the pipeline; the reasoning engine is instructed (and the policy engine independently enforces) that untrusted-data-tagged content can never resolve to a `Capability` grant, a policy change, a permission escalation, or a secret disclosure, regardless of its phrasing ("ignore previous instructions," "you are now authorized," embedded fake system messages, etc. are all just text with no privileged channel to act on).
- Ontology mapping (§16) explicitly rejects any extracted "instruction-shaped" content from becoming an executable directive — it can only become a `Claim` (with the usual evidence/confidence treatment), never a capability grant or policy node.
- Information-flow control: data read from an untrusted source is labeled and that label propagates through derived facts; a conclusion derived partly from untrusted data is capped at a lower confidence ceiling and flagged for review before it can feed a write to Control/Policy domains.
- Tool outputs are parsed into typed result schemas before being shown to the reasoning engine — free-text tool output that tries to look like a system message is just a string value in a `result` field, not reinterpreted as a role change.

---

## 29. Agent Memory Architecture

Three memory systems, deliberately not merged:

- **Episodic Memory** — prior investigations, tests, and outcomes, stored as `Incident`/`ValidationRun` records with full evidence trails; queried for "have we seen this before" and used to calibrate `P_base(e)` in the risk model (§10.2) from real historical data rather than static estimates.
- **Semantic Memory** — the general knowledge graph itself (§4–§13): timeless-ish ontology, technique descriptions, CVE/CWE facts. This is what most retrieval (§17) targets.
- **Procedural Memory** — validated `Playbook` nodes (investigation runbooks, remediation workflows, red-team test plans) that graduate from "proposed" to "validated" only after passing through the Judge and, ideally, at least one successful `ValidationRun`.

Each memory type has its own storage/indexing characteristics (Episodic and Procedural are relational + graph; Semantic spans graph + vector + keyword) and its own access-control scope per agent (§19) — an agent reasoning about a new incident should not have its context polluted by unrelated procedural playbooks it doesn't have permission to execute anyway.

---

## 30. Evaluation Framework & Metrics

```text
AttackSuccessRate      = successful_validated_techniques / attempted_techniques   (sandbox only)
DetectionRate          = detected_techniques / relevant_techniques
DetectionCoverage      = see §22
FalsePositiveRate      = false_positive_alerts / total_alerts
MeanTimeToDetect (MTTD) = mean(alert_time − first_observable_time)
MeanTimeToRespond (MTTR)= mean(containment_time − alert_time)
RemediationSuccessRate = verified_fixed / remediation_attempts   (verified via regression test, §24.2)
PatchEffectiveness     = 1 − (recurrence_rate after patch)
AttackPathReduction    = 1 − (post_control_max_risk / pre_control_max_risk)   (from §10.2)
PrivilegeReduction     = Δ(count of over-privileged bindings)
BlastRadiusReduction   = Δ(critical assets reachable from a compromised node)
TelemetryCoverage      = see §22
TechniqueCoverage      = see §22
KnowledgeConfidence    = mean(confidence) over relevant subgraph
KnowledgeFreshness     = mean(e^{-λ(now − updated_at)}) over relevant subgraph
```

Benchmark design covers: knowledge retrieval accuracy (precision/recall against a curated gold set of Q/A pairs), entity linking accuracy, threat classification, attack-path reasoning correctness (does the proposed path actually respect preconditions), vulnerability analysis correctness, detection-engineering quality (does a proposed Sigma rule actually match relevant, and not irrelevant, telemetry samples), incident-investigation quality (hypothesis convergence against a labeled synthetic incident), remediation correctness, security-architecture review quality, evidence-attribution accuracy (does every claim in an answer actually trace to real evidence), temporal reasoning (does the system correctly distinguish "was" vs "is"), adversarial robustness, and prompt-injection resistance (a dedicated red-team suite of injected documents that attempt to escalate capability, exfiltrate secrets, or override policy — success rate must be tracked as zero-tolerance).

Hallucination / unsupported-claim rate is measured directly: sample generated answers, check what fraction of factual assertions carry a resolvable `SUPPORTED_BY` evidence edge versus being generated without graph backing — this is the single most important regression metric for the system, tracked per release.

---

## 31. Continuous Learning Loop

```text
Red Agent → Controlled Security Test (sandbox, authorized) → Telemetry → Blue Agent → Detection
  → Response → Evaluation → Security Judge → Knowledge Update → Red Agent (next cycle)
```

Every `ValidationRun` writes a structured result — technique attempted, environment, detected (y/n), detection latency, telemetry produced — as `Evidence` with `source_type: lab_experiment`, the highest-trust evidence class in §12. Over successive cycles, claims migrate from `"theoretically detectable per framework X"` (confidence ~0.5–0.7, single-source) to `"validated in environment Y under conditions Z on <date>"` (confidence 0.9+, experimentally-backed, `VALIDATED_BY` edge to the specific `ValidationRun`). This is the mechanism by which the world model's confidence in its own defensive claims becomes grounded in reality rather than in documentation alone — and it's also how the system detects *drift*: a previously-validated detection that stops firing in a later validation run is flagged as a regression, not silently left at its old confidence.

---

## 32. Storage & Database Architecture

| Store | Purpose | Recommended | Alternative |
|---|---|---|---|
| Graph DB | ontology, entities, relations, attack-defense graph, path algorithms | Neo4j (mature Cypher, path algorithms via GDS library) | Memgraph (in-memory, faster for smaller graphs) |
| Vector DB | semantic retrieval over document/claim embeddings | Qdrant (dedicated, fast filtering) | pgvector (co-located with Postgres, fewer moving parts) |
| Keyword/Search | BM25, exact-ID lookup, faceted filtering | OpenSearch | Typesense/Meilisearch (lighter weight) |
| Relational | source registry, capability/policy state, audit log, structured CVE/asset tables | PostgreSQL | — |
| Time-series | telemetry (log volume, alert rates, metrics) | ClickHouse | TimescaleDB (Postgres-native) |
| Object storage | raw ingested documents, PCAP metadata refs, tool output artifacts | MinIO (S3-compatible, self-hostable) | S3 directly (enterprise) |
| Cache | hot query results, session state | Redis | — |
| Event bus | ingestion events, agent coordination events | Kafka (enterprise) | NATS (lighter weight) |

**Recommended stack (mid-size, self-hosted):** Postgres (system-of-record + relational) + Neo4j (graph reasoning) + Qdrant (vector) + OpenSearch (keyword) + ClickHouse (telemetry) + MinIO (objects) + Redis (cache) + NATS (events).

**Enterprise stack:** same components, horizontally scaled/clustered, with Kafka replacing NATS for durability/throughput at scale, and a managed cloud equivalent for each (e.g., managed Postgres, Neo4j Aura, managed OpenSearch) where operational burden matters more than cost.

**Low-resource stack (single weak machine):** PostgreSQL + pgvector (folds vector search into the same DB, one fewer service) + a lightweight graph layer implemented as adjacency tables in Postgres with recursive CTEs for path queries (full Neo4j is heavy for a laptop) + MinIO + FastAPI + a small local embedding model (e.g., a compact sentence-embedding model runnable on CPU) + a local cross-encoder reranker. OpenSearch/ClickHouse/Kafka/Redis are dropped entirely at this tier — Postgres full-text search (`tsvector`) substitutes for keyword search, and telemetry volume at single-machine scale doesn't justify ClickHouse.

**Migration path:** Single Machine (Postgres does everything) → Small Server (split out Neo4j once the graph query patterns exceed what recursive CTEs handle well, typically once multi-hop path queries beyond 3–4 hops become common; add OpenSearch once keyword-search precision on large corpora becomes the bottleneck) → Distributed System (add Kafka, cluster Neo4j/OpenSearch, move telemetry to ClickHouse once ingestion volume exceeds what Postgres time-series tables handle comfortably). Each migration step is additive — schemas and APIs (§29) do not change, only the backing store behind a given API does.

---

## 33. Event Architecture

Event-driven backbone decouples ingestion, reasoning, and agent coordination — no component polls another synchronously for state it can instead subscribe to.

Core event types and schemas (published on the bus, consumed by relevant subsystems):

```json
{ "event": "VulnerabilityDiscovered", "vuln_id": "cve-2024-3094", "affected_assets": ["asset-77"], "severity": 10.0, "timestamp": "iso8601" }
{ "event": "AssetDiscovered", "asset_id": "asset-201", "asset_type": "WebApplication", "exposure_level": "internet", "timestamp": "iso8601" }
{ "event": "ThreatDetected", "detection_rule_id": "rule-44", "technique_id": "T1190", "asset_id": "asset-77", "confidence": 0.8, "timestamp": "iso8601" }
{ "event": "AttackObserved", "technique_id": "T1190", "source_ip": "redacted-or-scoped", "asset_id": "asset-77", "evidence_id": "ev-901", "timestamp": "iso8601" }
{ "event": "AlertCreated", "alert_id": "alert-501", "detection_rule_id": "rule-44", "severity": "high", "timestamp": "iso8601" }
{ "event": "IncidentCreated", "incident_id": "inc-9", "triggering_alert_id": "alert-501", "timestamp": "iso8601" }
{ "event": "PatchReleased", "patch_id": "patch-12", "cve_ids": ["cve-2024-3094"], "timestamp": "iso8601" }
{ "event": "DetectionUpdated", "rule_id": "rule-44", "change": "coverage_added:T1059.001", "timestamp": "iso8601" }
{ "event": "ExperimentCompleted", "validation_run_id": "vr-33", "technique_id": "T1190", "detected": true, "latency_seconds": 42, "timestamp": "iso8601" }
{ "event": "KnowledgeUpdated", "node_ids": ["tech-t1190"], "change_type": "confidence_revised", "timestamp": "iso8601" }
```

Consumers subscribe by event type and (optionally) filter predicate — e.g., the Attack Path Engine recomputes affected paths on `VulnerabilityDiscovered`/`AssetDiscovered`; the Detection Coverage service recomputes on `DetectionUpdated`/`KnowledgeUpdated`; the Knowledge Updater persists `ExperimentCompleted` results through the Compiler (§16). Every event also lands in the immutable audit log (§37) regardless of downstream processing outcome.

---

## 34. API Architecture

RESTful, resource-oriented, with a small number of purpose-built endpoints rather than one generic "ask anything" endpoint — this keeps permission checks (§27) precise per-capability.

```text
POST /v1/knowledge/search        { query, filters, mode: "keyword|vector|hybrid" }
GET  /v1/entities/{id}
POST /v1/graph/traverse          { start_id, relation_types[], max_depth, direction }
POST /v1/attack-paths/analyze    { target_asset_id, algorithm: "shortest|highest_risk|priv_esc|lateral", constraints }
GET  /v1/evidence/{claim_id}
POST /v1/threat-intel/query      { actor|campaign|indicator, filters }
POST /v1/vulnerabilities/search  { product, version, cve_id, asset_id }
POST /v1/detections/coverage     { technique_ids[], asset_scope }
POST /v1/incidents/{id}/hypotheses   { statement, evidence_for[], evidence_against[] }
POST /v1/knowledge/update        { entity|relation payload }   // routed through Compiler + Judge, never direct write
GET  /v1/agent-memory/{agent_id}/episodic|semantic|procedural
POST /v1/evaluation/run          { benchmark_id, agent_id }
```

Example response envelope (uniform across endpoints, so every answer is explainable by construction):

```json
{
  "data": { "...": "..." },
  "confidence": 0.87,
  "evidence": [{ "evidence_id": "ev-101", "source_id": "src-mitre-attack" }],
  "as_of": "2026-09-02T00:00:00Z",
  "warnings": ["telemetry for TelemetrySource X not confirmed available"]
}
```

Write endpoints (`/v1/knowledge/update`, rule deployment, remediation actions) always require a `capability_token` and are logged to the audit trail with the acting agent/user identity — there is no write path that bypasses the Policy Engine, including "internal" service-to-service calls.

---

## 35. Directory Structure (reference implementation)

```text
security-world-model/
├── ontology/                # entity/relation type definitions, JSON Schema per node type
├── ingestion/
│   ├── collectors/          # per-source collectors (nvd, cisa_kev, mitre_attack, internal_siem, ...)
│   ├── parsers/              # format-specific normalizers (html, pdf, stix, sbom, ...)
│   └── dedup/
├── extraction/
│   ├── deterministic/        # regex, rule-engine, known-schema parsers
│   ├── ner_linking/
│   └── llm_extraction/       # relation extraction, disambiguation prompts, cost-tracked
├── compiler/                 # AST -> IR -> entity/relation resolution -> validation -> commit
├── graph/                    # Neo4j schema migrations, Cypher query library, path algorithms
├── retrieval/                # keyword, vector, graph, reranker, intent classifier
├── skql/                     # query language grammar + compilers to Cypher/SQL/vector filters
├── reasoning/                # attack-defense reasoner, risk engine, causal engine, confidence propagation
├── agents/
│   ├── orchestrator/
│   ├── threat_intel/
│   ├── red/
│   ├── blue/
│   ├── seceng/
│   └── judge/
├── policy/                   # capability definitions, policy engine, risk/approval gate
├── sandbox/                  # isolated execution environment for Red Agent validation
├── memory/                   # episodic, semantic, procedural memory access layers
├── events/                   # event schemas, publishers, subscribers
├── api/                      # REST handlers, auth, capability_token verification
├── eval/                     # benchmark datasets, metric computation, regression tracking
├── audit/                    # immutable audit log writer/reader
└── deploy/
    ├── single-machine/
    ├── small-server/
    └── distributed/
```

---

## 36. Security Risks and Failure Modes

**Security risks inherent to the system itself** (not the attacks it studies): the knowledge graph is itself a high-value target — it maps every asset, weakness, and attack path across the org, so read-access to it must be scoped per-consumer (an intern's chatbot session should not see the full attack-path graph to crown-jewel assets); ingestion pipelines that pull from the public internet are an injection surface (§28) and must never have write access to policy/capability nodes; the Capability Broker and audit log are the two components whose compromise would be catastrophic and therefore get the narrowest access, strongest auth, and most aggressive monitoring of anything in the system; LLM components must never be given direct database credentials, cloud credentials, or secret material — only mediated tool calls.

**Failure modes and required behavior:**

| Failure | Required system behavior |
|---|---|
| Missing knowledge | respond "I don't know" with what's missing, not fabricated certainty |
| Conflicting sources | surface the `CONTRADICTS` edge and both positions, don't silently pick one |
| Outdated knowledge | flag freshness score below threshold, prefer re-verification over stale answer |
| Unknown asset/vulnerability | fall back to closest-match candidates with low confidence, flagged as unresolved |
| Insufficient telemetry | report coverage gap explicitly (§22), don't assert detection capability that doesn't exist |
| Insufficient privilege | Policy Engine rejects the tool call before it reaches execution, with a clear reason |
| Tool failure | quarantine + retry with backoff; surface failure to requester rather than silently omitting results |
| Network failure | degrade to cached/last-known-good knowledge with an explicit staleness warning |
| False positive/negative | tracked as evaluation metrics (§30), feeds back into rule/confidence tuning, never silently ignored |
| Agent reasoning failure | caught by Security Judge before it becomes an action or a graph write |

---

## 37. Observability

Every layer emits structured, correlated traces: `AgentDecision`, `ToolInvocation`, `PermissionCheck`, `KnowledgeRetrieval`, `GraphTraversal`, `EvidenceSelection`, `SecurityFinding`, `RiskDecision`, `HumanApproval`, `ExecutionResult`, `KnowledgeUpdate` — each tagged with a shared `trace_id` so a single user-facing answer can be replayed end-to-end: which retrieval calls fired, which graph paths were walked, which evidence was selected and why, which confidence inputs produced the final score, which capability checks passed or failed. The audit log is append-only (write-once storage or hash-chained records) and is itself a `Source` in the provenance graph — the system can answer "what did you do and why" using the exact same evidence machinery it uses for security claims.

---

## 38. Development Roadmap

1. **Foundation (weeks 1–4):** ontology schemas, Postgres + pgvector single-machine stack, deterministic extraction for CVE/CWE/CVSS/MITRE ATT&CK ingestion, basic Knowledge Compiler with entity resolution.
2. **Core reasoning (weeks 5–8):** graph queries for attack-defense traversal (§9), attack-path algorithms (§10) on a small synthetic asset graph, confidence model (§12), temporal queries (§13).
3. **Retrieval & agents (weeks 9–12):** hybrid retrieval pipeline (§17), SKQL (§18), Orchestrator + Blue Agent (detection coverage, alert triage) as the first two specialized agents — Blue before Red, since detection/analysis carries lower execution risk.
4. **Policy & safety (weeks 13–15):** Capability Broker, Policy Engine, sandbox environment, audit log — built and hardened *before* the Red Agent gets any execution path, not after.
5. **Red Agent + continuous learning loop (weeks 16–20):** Red Agent limited to Knowledge/Planning/Simulation stages initially; Validation-stage sandbox execution added only once the Judge and audit trail are proven reliable; continuous learning loop (§31) wired end-to-end.
6. **Judge & evaluation (weeks 21–24):** independent Security Judge, benchmark suite (§30), hallucination/unsupported-claim regression tracking as a release gate.
7. **Scale-out (weeks 25+):** migrate storage per §32's migration path as real query patterns and data volume demand it; add Threat Intel and SecEng agents; expand cloud/container/supply-chain domains (§24) as coverage priorities dictate.

---

## Closing Note

The single architectural decision that matters most in this design is the separation the prompt insisted on: **Knowledge ≠ Permission ≠ Execution ≠ Production Access.** Everything else — the graph schema, the retrieval pipeline, the confidence model — exists to make the *knowledge* half of the system as good as possible. But a knowledge system this capable is only safe to operate autonomously if the *action* half is deliberately, structurally dumber than the reasoning that feeds it: capability checks in plain code, human approval for anything irreversible, and a Judge that never trusts the agent that did the work.
