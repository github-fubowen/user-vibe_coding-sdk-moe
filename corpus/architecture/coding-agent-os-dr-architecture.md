# Coding Agent OS — Disaster Recovery & Fault-Tolerance Architecture

**A production-grade reliability architecture treating autonomous coding Agents as recoverable logical state machines, not irreplaceable processes.**

---

## Table of Contents

- A. Executive Summary
- B. Architecture Principles
- C. Complete Architecture (Diagrams)
- D. Component Architecture
- E. Data Model
- F. Recovery Algorithms
- G. Failure Matrix
- H. RPO/RTO Matrix
- I. Chaos Test Plan
- J. Acceptance Criteria & SLOs
- K. Technology Stack
- L. Implementation Roadmap
- M. Architectural Q&A Appendix

---

## A. Executive Summary

Coding Agent OS (CAOS) is an operating system for autonomous software-engineering Agents: long-running, non-deterministic, tool-using processes that read and write real Git repositories, call real APIs, spend real money, and take actions that are not always reversible (a pushed commit, a filed PR, a deployed service). Traditional application DR — "back up the database, fail over the VM" — does not address the central failure mode of this system: **an Agent can die at any instruction boundary, including the instant before or after an irreversible external action, and the system must know what to do about it without a human watching every step.**

The architecture rests on one governing invariant:

> **Any recoverable Agent task must be reconstructable from `Checkpoint + Event Log + Durable State + External Side-Effect Ledger`.**

and one governing goal:

> **Failure ≠ Task Loss.** A process, container, node, AZ, or region may disappear. The *logical* task — the thing the human or upstream system actually asked for — must survive whenever its declared durability tier permits it, and the system must never silently re-execute an external side effect it cannot prove did or didn't happen.

To achieve this, CAOS separates an **Agent's identity and logical state** (durable, checkpointed, replayable) from its **Agent Runtime** (a disposable process/container that merely executes that state for a while). Any runtime can pick up any agent's state and continue. This is the same idea that makes Kubernetes pods disposable and Kafka consumers replaceable — applied to a reasoning, tool-calling, code-modifying process instead of a stateless request handler.

Three subsystems make this possible:

1. **Event Sourcing** — every state transition (plan step, tool call, test result, human approval, commit) is an immutable, ordered, idempotent event. State is a fold over events, so it can always be rebuilt.
2. **Multi-level Checkpointing** — periodic, versioned snapshots of reconstructable state at Process, Agent, Task, Workflow, Workspace, and System levels, so recovery does not require replaying an agent's entire multi-day history.
3. **The Side-Effect Ledger** — a transactional-outbox/idempotency-key system that turns "did the git push actually happen?" from a guess into a lookup, giving CAOS **effectively-once** semantics for actions that are inherently at-least-once at the network layer.

Around this core, the **Agent Recovery Kernel** provides failure detection (heartbeats, leases, watchdogs, anomaly detection), classification (transient vs. corruption vs. security incident), and a formal recovery state machine (`RUNNING → SUSPECTED_FAILURE → ... → RESUMED`) that governs every recovery path from a single killed container up to a full region loss.

The design explicitly rejects two illusions common in naive agent frameworks: that "just retry the LLM call" is a recovery strategy, and that global ACID consistency is achievable across an LLM, a Git repo, a vector DB, and three external SaaS APIs. Instead it defines, component by component, exactly which consistency model applies, and makes every side effect either idempotent, ledgered, or human-gated.

---

## B. Architecture Principles

1. **An Agent is a logical state machine, not a process.** The process (Agent Runtime) is disposable; the state (identity, task, context, memory refs, pending actions) is durable and portable across runtimes.
2. **Checkpoint + Event Log + Side-Effect Ledger is the unit of recoverability.** Nothing is considered "safely recoverable" unless it can be reconstructed from these three sources plus externally-owned systems of record (Git, the database).
3. **Every external side effect is idempotent or ledgered before it is executed**, never after. If an operation cannot be made idempotent, it requires a human approval gate.
4. **Non-determinism is quarantined at the LLM boundary.** Everything downstream of a model call (plan, diff, tool arguments) is treated as untrusted input and is event-sourced verbatim so replay is deterministic even though generation is not.
5. **Recovery must distinguish "definitely happened," "definitely didn't happen," and "unknown"** for every pending action, and must never collapse "unknown" into either extreme without reconciliation.
6. **Git, the database, and object storage are systems of record; the vector DB, in-memory context, and derived indices are caches.** Losing a cache must never lose information — only latency.
7. **No component may resurrect itself from compromise.** A quarantined or suspected-malicious Agent requires explicit human/policy approval to resume; automatic recovery is disabled at the security boundary.
8. **Failure domains are bounded so one Agent cannot exhaust the system.** Budgets, concurrency limits, and circuit breakers apply per-agent, per-tenant, and globally, so a runaway agent cannot become a cluster-wide incident.
9. **Recovery is a first-class, tested, observable subsystem — not an operational afterthought.** The Recovery Kernel has its own metrics, its own SLOs, and its own chaos test suite.
10. **Checkpointing is layered by cost and scope**, so recovery time is proportional to blast radius: a crashed process resumes in seconds from an L0/L1 checkpoint; a lost region rebuilds in hours from Golden Snapshot + cross-region replicas.
11. **Duplicate execution is a correctness bug, not an acceptable side effect of retries.** Every retryable action carries an idempotency key scoped to the causing event.
12. **Human approval gates are durable state, not runtime state.** An approval request surviving a crash is a first-class checkpointed entity, not a lost in-memory prompt.
13. **Infrastructure and configuration are code.** Nothing that defines "what CAOS is" (agent definitions, policies, skill/tool/MCP registries, workflow definitions) may exist only inside a running cluster; it is reproducible from the Golden Snapshot and Git.
14. **Observability is causal, not just aggregate.** Every event, checkpoint, and side effect carries correlation IDs (agent, task, workflow) so that a single failure can be traced end-to-end across LLM calls, tool calls, and infrastructure events.
15. **Consistency guarantees are explicit and local, never assumed global.** Each subsystem states its own consistency model; cross-subsystem consistency is achieved through reconciliation, not distributed transactions.
16. **Every recovery path is chaos-tested before it is trusted.** A recovery mechanism that has not been exercised by fault injection is assumed broken.
17. **Degrade before you fail.** Backpressure, admission control, and graceful degradation (e.g., pause new task admission, keep in-flight tasks running) are preferred over hard outages.
18. **The system is designed to survive not existing.** A total cluster loss must be recoverable onto infrastructure that has never run CAOS before, using only IaC + Golden Snapshot + backups.

---

## C. Complete Architecture (Diagrams)

### C.1 Core Conceptual Model — Why State > Process

```text
Agent Identity  (stable UUID, never reused, survives every restart)
      │
      ▼
Logical Agent State  ── the ONLY thing that must survive a crash
      │
      ├── Task State            (what am I doing)
      ├── Workflow State         (where am I in the DAG)
      ├── Context                (prompt/context window contents, reconstructable)
      ├── Memory                 (references, not blobs — see Section D.5)
      ├── Tool State             (open sessions, in-flight calls)
      ├── Workspace State        (git ref + FS snapshot id, not the FS itself)
      ├── Pending Actions        (side effects requested but not confirmed)
      └── Policy State           (budgets, approvals, quarantine flags)
      │
      ▼
Checkpoint            (periodic, versioned, cheap-to-restore fold of the above)
      │
      +  (checkpoint is necessary but not sufficient — events since checkpoint matter)
      ▼
Event Journal          (append-only, ordered, causally linked, replayable)
      │
      +  (events tell you *what was attempted*, not *what external systems did*)
      ▼
Side-Effect Ledger     (ground truth for "did the git push actually land")
      │
      ▼
Recoverable Agent Task  = Checkpoint ⊕ Replay(Events since checkpoint) ⊕ Reconcile(Ledger, External Systems)
```

**Why this beats "just restart the process":** A restarted process has no memory of what it was doing, cannot tell a completed git push from a failed one, cannot resume a 6-hour refactor from step 340 instead of step 0, and — worst case — will retry the git push, opening a duplicate PR, or skip it, silently losing work. Restarting the *process* discards exactly the information (task position, side-effect outcomes, partial reasoning) that made the crash expensive in the first place. CAOS instead restarts a *runtime* against *state that already knows everything the dead process knew*, so the blast radius of a crash is bounded to "replay a bounded event tail," not "start over."

### C.2 Agent Recovery Kernel — Internal Architecture

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                         AGENT RECOVERY KERNEL                              │
│                                                                             │
│  ┌─────────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│  │ Failure Detection │  │ Classification    │  │ Recovery Policy Engine │  │
│  │ - Heartbeats       │→ │ - Transient        │→ │ - selects strategy per │  │
│  │ - Leases           │  │ - Recoverable      │  │   failure class        │  │
│  │ - Watchdogs         │  │ - Corruption       │  │ - consults budgets     │  │
│  │ - Anomaly detectors │  │ - Security          │  │ - consults SLO tier    │  │
│  │ - Circuit breakers  │  │ - Resource exhaust. │  └───────────┬────────────┘  │
│  └────────┬────────────┘  └──────────┬─────────┘              │               │
│           │                          │                        ▼               │
│           ▼                          ▼             ┌────────────────────────┐ │
│  ┌────────────────────┐   ┌──────────────────┐    │ Isolation / Quarantine │ │
│  │ Suspect Registry     │  │ Quarantine Gate   │←──┤ - revoke credentials    │ │
│  │ (suspected-failure    │  │ (security path)   │   │ - freeze workspace      │ │
│  │  agents, with TTL)    │  └──────────────────┘   │ - snapshot for forensics│ │
│  └────────┬─────────────┘                          └────────────────────────┘ │
│           ▼                                                                    │
│  ┌────────────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│  │ Checkpoint Selector  │→ │ State Reconstructor│→ │ Event Replay Engine    │  │
│  │ - latest VALID chkpt │  │ - deserialize state │  │ - fetch events after   │  │
│  │ - checksum verify     │  │ - rehydrate refs    │  │   checkpoint seq#      │  │
│  └────────────────────┘   └──────────────────┘   └───────────┬────────────┘  │
│                                                                 ▼               │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ Side-Effect Reconciler                                                   │  │
│  │ - for each pending action at crash time: query Side-Effect Ledger        │  │
│  │ - query external system of record (Git, PR API, DB) if ledger ambiguous  │  │
│  │ - classify: CONFIRMED_DONE / CONFIRMED_NOT_DONE / UNKNOWN → escalate      │  │
│  └───────────────────────────────────┬──────────────────────────────────────┘  │
│                                       ▼                                        │
│  ┌────────────────────┐   ┌──────────────────┐   ┌────────────────────────┐  │
│  │ Dedup / Idempotency  │  │ Health Verifier    │  │ Resume / Migration      │  │
│  │ Guard                │→ │ - post-recovery     │→ │ Coordinator             │  │
│  │ - blocks re-execution│  │   smoke checks      │  │ - binds new Runtime     │  │
│  │   of confirmed-done   │  └──────────────────┘   │ - releases lease        │  │
│  │   actions             │                          │ - schedules on Worker   │  │
│  └────────────────────┘                            └────────────────────────┘  │
│                                                                                 │
│  Cross-cutting: Checkpoint GC · Rollback Executor · Recovery Metrics Emitter   │
└───────────────────────────────────────────────────────────────────────────────┘
```

### C.3 Recovery State Machine

```text
        ┌─────────┐
        │ RUNNING │◄────────────────────────────────────────┐
        └────┬────┘                                          │
             │ missed heartbeat / lease expiry / anomaly      │
             ▼                                                │
   ┌────────────────────┐                                     │
   │ SUSPECTED_FAILURE    │── heartbeat resumes within grace ─┘
   └─────────┬────────────┘
             │ grace period exceeded / explicit crash signal
             ▼
   ┌────────────────────┐        malicious/compromise signal
   │ CONFIRMED_FAILURE    │─────────────────────────────┐
   └─────────┬────────────┘                             ▼
             │ normal failure                  ┌──────────────────┐
             ▼                                  │   QUARANTINED     │──► HUMAN_APPROVAL ──► (resume path) or PERMANENT_FAILURE
   ┌────────────────────┐                       └──────────────────┘
   │ CHECKPOINT_SELECTED  │
   └─────────┬────────────┘── checkpoint corrupt ──► ROLLBACK (older checkpoint) ──┐
             │ valid                                                               │
             ▼                                                                     │
   ┌────────────────────┐                                                         │
   │  STATE_RESTORED      │◄────────────────────────────────────────────────────┘
   └─────────┬────────────┘
             ▼
   ┌────────────────────┐── replay error / poison event ──► RETRY (bounded) ──► ESCALATE
   │  EVENTS_REPLAYED     │
   └─────────┬────────────┘
             ▼
   ┌────────────────────────┐── unknown side effect, no ledger match ──► HUMAN_APPROVAL
   │ SIDE_EFFECTS_RECONCILED │
   └─────────┬───────────────┘
             ▼
   ┌────────────────────┐── smoke check fails ──► ROLLBACK
   │  HEALTH_VERIFIED     │
   └─────────┬────────────┘
             ▼
        ┌─────────┐
        │ RESUMED │──► back to RUNNING (new Agent Runtime bound, lease acquired)
        └─────────┘
```

### C.4 Multi-Region Reference Architecture

```text
                                   GLOBAL CONTROL PLANE
                         (identity, policy, routing, Golden Snapshot registry)
                                          │
                     ┌────────────────────┼─────────────────────┐
                     │                    │                     │
               Region A: PRIMARY    Region B: WARM STANDBY  Region C: COLD BACKUP
               (active)             (active control plane,  (object storage +
                                     idle data plane)        Golden Snapshot only)
                     │                    │                     │
        ┌────────────┴───────────┐ ┌──────┴───────────┐         │
        │ Control Plane (HA,     │ │ Control Plane      │         │
        │ leader-elected)        │ │ (standby, replicated)│        │
        │  API GW / Scheduler /  │ │  same components,    │        │
        │  Agent Mgr / Workflow  │ │  read replicas warm   │        │
        │  Mgr / Recovery Mgr    │ └──────┬───────────────┘         │
        └────────────┬───────────┘        │                        │
                     │             (scaled to zero workers;         │
        ┌────────────┴───────────┐  promotes on regional failover)  │
        │ Data Plane (Agent      │        │                        │
        │ Runtimes, Task Workers,│        │                        │
        │ Sandboxes, CI Workers) │        │                        │
        └────────────┬───────────┘        │                        │
                     │                    │                        │
        ┌────────────┴────────────────────┴────────────────────────┴──────┐
        │                    DURABLE DATA LAYER                            │
        │  Postgres (state, sync replicated to B, async to C)              │
        │  Event Store / Kafka (mirrored to B via MirrorMaker/geo-replica) │
        │  Object Storage (S3 versioned + cross-region replication A→B→C) │
        │  Checkpoint Store (same object storage, CAS-addressed)          │
        │  Vector DB (rebuildable — replicated best-effort only)          │
        └───────────────────────────┬───────────────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │   RECOVERY KERNEL    │
                          │ Detect·Checkpoint·   │
                          │ Replay·Reconcile·    │
                          │ Resume·Migrate       │
                          │ (runs per-region,     │
                          │ coordinates via       │
                          │ global lease service) │
                          └──────────────────────┘
```

*Improvement over the naive reference diagram*: the original two-region "Primary/DR" sketch is upgraded to three tiers (Primary / Warm Standby / Cold Backup) because CAOS's true cost driver is data-plane compute (Agent Runtimes, sandboxes, CI workers), not control-plane state. Keeping Region B's control plane warm but its data plane scaled near zero gives fast failover for control decisions (stop admitting new tasks, resume in-flight ones) without paying for idle GPU/CI capacity — see Section C (Multi-Region Strategy) below for the Pilot-Light rationale.

---

## D. Component Architecture

### D.1 Agent State Model — What Is "The Agent"?

An Agent's recoverable state is partitioned by *how* it can be reconstructed, because that determines what must be checkpointed vs. what must be event-sourced vs. what should never be persisted at all.

| Category | Definition | Examples | Storage strategy |
|---|---|---|---|
| **Immutable state** | Set once at creation, never changes | Agent Identity (UUID), Agent Version, initial System Prompt, Task ID | Written once to Postgres; referenced everywhere by ID |
| **Mutable durable state** | Changes over time, must survive crashes | Current State/Step, Policy State (budgets, approvals), Human Approval State, Retry counters | Event-sourced + periodically checkpointed |
| **Derived state** | Computed from other durable state, cheap to recompute | Aggregated token spend, progress %, "is stuck" flag | Never checkpointed; recomputed on read or async projection |
| **Ephemeral state** | Meaningful only while a runtime is alive | Open socket handles, in-process caches, GPU memory buffers | Never persisted; recreated fresh on every runtime bind |
| **Reconstructable state** | Not stored directly; rebuilt from a source of truth | RAG context window contents, prompt assembled from templates + memory | Store the *recipe* (template ID + memory refs + retrieval query), not the assembled text |
| **Externally-owned state** | Source of truth lives outside CAOS | Git repository contents, deployed service state, third-party ticket status | CAOS stores *references* (commit SHA, PR URL, deployment ID) and reconciles against the external system, never treats its own copy as authoritative |

**Formal state schema** (see Section E for the full JSON Schema):

```text
Agent {
  identity            // immutable
  configuration       // immutable-per-version
  version             // immutable
  model_configuration // immutable-per-version (model, temperature, tool allowlist)
  system_prompt_ref   // immutable (template id + version, not raw text)
  task_ref            // immutable link
  workflow_ref        // immutable link
  current_state       // mutable, event-sourced
  current_step        // mutable, event-sourced
  context_recipe      // reconstructable (retrieval query + memory refs, not raw tokens)
  working_memory_ref   // externally-owned (points at memory store)
  long_term_memory_refs // externally-owned
  tool_state           // mutable, mostly ephemeral + a durable "in-flight call" record
  mcp_state             // mutable, ephemeral connection + durable session descriptor
  skill_state            // immutable-per-version reference into Skill Registry
  workspace_ref            // externally-owned (git remote + branch + last known commit + FS snapshot id)
  git_state                 // externally-owned, reconciled
  uncommitted_changes        // reconstructable from FS snapshot / CAS, not from event log
  environment                // reconstructable (declared, not captured live)
  pending_tool_calls           // mutable durable (this is what makes side-effect safety possible)
  pending_actions                // mutable durable
  human_approval_state             // mutable durable, first-class checkpointed entity
  policy_state                       // mutable durable (budgets, quarantine flag)
  security_context                     // immutable-per-session (identity, scopes, credentials by reference)
  resource_allocations                   // ephemeral, re-requested on resume
  timeouts / retries / timers / scheduled_actions  // mutable durable
}
```

**What should never be checkpointed** (Q3 in Section M expands on this): raw credential material, ephemeral runtime handles (sockets, file descriptors, GPU memory pointers), the full assembled prompt/context text (store the recipe instead — it's large, derivable, and would bloat checkpoints), and any state whose source of truth is external (don't checkpoint "the file contents of the repo" — checkpoint the commit SHA and let Git be Git).

### D.2 Event Sourcing Layer

Every state transition in the system is represented as an **immutable, ordered, causally-linked event**. State is never mutated directly — it is derived by folding events.

**Core event types** (non-exhaustive; new event types are additive and versioned):

```text
AgentCreated, AgentMigrated, AgentRecovered, AgentQuarantined
TaskCreated, TaskAssigned, TaskCompleted, TaskFailed, TaskCancelled
PlanGenerated, StepStarted, StepCompleted
ToolCallRequested, ToolCallStarted, ToolCallCompleted, ToolCallFailed
ArtifactCreated, CodeModified, CommitCreated, PushAttempted, PushConfirmed
TestStarted, TestCompleted, TestFailed
HumanApprovalRequested, HumanApprovalGranted, HumanApprovalDenied
DeploymentStarted, DeploymentCompleted, DeploymentFailed
CheckpointCreated, CheckpointValidated, CheckpointExpired
```

**Event envelope** (every event, regardless of type, carries this envelope):

```json
{
  "event_id": "evt_01J9Z...",          // ULID: sortable, unique, generated at write time
  "event_type": "ToolCallCompleted",
  "event_version": 2,                     // schema version of the payload
  "sequence_number": 48213,                // monotonic per-agent stream position
  "agent_id": "agt_7f1c...",
  "task_id": "tsk_9a02...",
  "workflow_id": "wf_44b1...",
  "correlation_id": "corr_c81e...",         // ties together a whole causal chain across agents
  "causation_id": "evt_01J9Y...",             // the event that directly caused this one
  "idempotency_key": "toolcall:agt_7f1c:step42:git_push:v1",
  "timestamp": "2026-09-07T09:14:02.114Z",
  "producer": { "runtime_id": "rt_88ab", "node_id": "node_12" },
  "payload": { "...": "type-specific fields" }
}
```

**Ordering & causality**: events are appended to a **per-agent stream** (partition key = `agent_id`) so per-agent ordering is a Kafka/JetStream partition guarantee, not an application-level lock. Cross-agent causality (agent spawns sub-agent, workflow step gates another workflow) is carried via `correlation_id`/`causation_id`, not via global ordering — CAOS never assumes a single global event order across agents, only within one.

**Idempotency keys** are deterministic functions of `(agent_id, step_id, action_type, action_target)` — *not* random — so that replaying the same logical step after a crash always derives the same key, which is what lets the Side-Effect Ledger detect "I've already done this."

**Versioning, retention, compaction, replay**:
- Event payloads are versioned (`event_version`); consumers/replayers must handle N and N-1 schema versions (expand-then-contract migration).
- Hot retention: full event log kept for the agent's active lifetime + a configurable tail (e.g., 30 days) in the event store.
- Cold retention: compacted/archived to object storage after the tail window — for audit and forensic replay, not fast recovery.
- **Compaction**: for recovery *speed*, events are periodically folded into checkpoints (Section D.3); compaction never deletes events needed to reconstruct a not-yet-checkpointed side effect or an unresolved approval.
- **Replay** is the mechanical process of `apply(checkpoint_state, event)` for each event after the checkpoint's sequence number, in order, using pure (side-effect-free) reducers — replay must never re-execute a tool call, only reconstruct *what the agent believed and decided*. Actual re-execution is a separate, ledger-gated decision made after replay (Section D.4).

**Interaction with snapshots**: a checkpoint is exactly "the fold of all events up to sequence N, cached so you don't have to refold them." This means checkpoints are *derived data* — they can always be regenerated by replaying from event 0 (or from an older checkpoint), which is the basis of checkpoint corruption recovery (Section C.3, ROLLBACK branch).

### D.3 Checkpoint Architecture

Checkpoints are layered so that recovery cost scales with blast radius, not with total system history.

```text
L0  Process Checkpoint    — in-memory reasoning scratchpad, tool-call-in-progress buffer
                             freq: every N seconds or every tool call; local disk / Redis
L1  Agent Checkpoint       — full Agent state model (Section D.1), minus context recipe expansion
                             freq: on every StepCompleted, or every 30–120s during long steps
L2  Task Checkpoint        — task-level rollup: which steps done, artifacts produced, test results
                             freq: on task state transitions
L3  Workflow Checkpoint    — DAG position across multiple agents/tasks
                             freq: on workflow node completion / fan-in/fan-out points
L4  Workspace Checkpoint   — git ref + filesystem snapshot id (Section D.6)
                             freq: before/after any workspace-mutating tool call
L5  System Checkpoint      — cluster-wide: control-plane config, registries, in-flight task index
                             freq: scheduled (e.g., every 15 min) + before/after deployments
```

- **Checkpoint triggers**: time-based (backstop), event-based (StepCompleted, before any irreversible side effect, before/after workspace mutation), and manual (before a bad-deployment rollback window).
- **Incremental vs. full**: L0/L1 checkpoints are incremental deltas against the last L1 (diff of state model fields) to keep them cheap and frequent; L4/L5 are always full-reference (a git SHA and a snapshot ID, not a diff of a filesystem) because filesystem-level CoW snapshots are already incremental at the storage layer (see D.6).
- **Copy-on-write**: L4 workspace checkpoints and L5 system checkpoints use CoW filesystem/volume snapshots (e.g., ZFS/Btrfs/EBS/Ceph RBD snapshots) so "checkpoint" is O(changed blocks), not O(workspace size).
- **Consistency**: an L1 checkpoint is only valid if taken at an **event-stream boundary** (i.e., `sequence_number` recorded in the checkpoint corresponds exactly to a committed event — never mid-event). Checkpoints are written with a checksum and the `sequence_number` they represent; validation recomputes the checksum and confirms `sequence_number` is monotonically ahead of the previous checkpoint before it is marked usable.
- **Versioning**: checkpoints carry `schema_version`; the Checkpoint Selector will skip a checkpoint whose schema version the current Recovery Kernel cannot deserialize and fall back to the next-older valid one, then replay forward through any format-migrating reducers.
- **Expiration & GC**: checkpoints are retained per a tiered policy — last N per agent kept indefinitely while the agent is active; on task/agent completion, checkpoints are retained for the audit window (e.g., 90 days) then garbage-collected, **except** any checkpoint referenced by an open forensic hold (Section D.13) or a not-yet-reconciled side effect.

**Checkpoint format (JSON, L1 Agent Checkpoint example):**

```json
{
  "checkpoint_id": "ckpt_01J9ZA...",
  "checkpoint_level": "L1",
  "schema_version": 3,
  "agent_id": "agt_7f1c...",
  "task_id": "tsk_9a02...",
  "sequence_number": 48213,
  "created_at": "2026-09-07T09:14:05.000Z",
  "checksum": "sha256:8f2a...",
  "trigger": "StepCompleted",
  "state": {
    "current_state": "AWAITING_TEST_RESULTS",
    "current_step": { "step_id": "step_42", "index": 42, "of": 87 },
    "context_recipe": {
      "template_id": "coder_agent_v4",
      "memory_refs": ["mem_ep_881a", "mem_sem_2210"],
      "retrieval_query_ref": "q_af13"
    },
    "workspace_ref": {
      "repo": "git@github.com:acme/service.git",
      "branch": "agent/agt_7f1c/fix-null-deref",
      "last_known_commit": "9c1f2ab",
      "fs_snapshot_id": "snap_0091ffa"
    },
    "pending_tool_calls": [
      {
        "call_id": "call_5521",
        "tool": "git_push",
        "idempotency_key": "toolcall:agt_7f1c:step42:git_push:v1",
        "status": "REQUESTED"
      }
    ],
    "human_approval_state": null,
    "policy_state": { "token_budget_used": 812345, "token_budget_limit": 2000000, "quarantined": false },
    "retries": { "step_42": 1 },
    "timers": [{ "id": "test_timeout", "fires_at": "2026-09-07T09:19:05.000Z" }]
  }
}
```

Checkpoint storage: content-addressable object storage (checkpoint blob keyed by its own checksum) + a Postgres index row (`checkpoint_id, agent_id, sequence_number, level, storage_key, checksum, status`) so lookup ("give me the latest valid L1 checkpoint for agent X") is a fast indexed query, while the payload itself lives cheaply in object storage.

### D.4 Deterministic Recovery & the "Unknown Side Effect" Problem

The fundamental problem: **an Agent can crash immediately before or immediately after an external side effect** (e.g., the `git push` network call succeeded on the server but the process died before it recorded the response). No amount of local checkpointing tells you which happened — you must ask the external system, or you must have written *intent* durably before attempting the action.

Recovery composes four sources:

```text
Latest Valid Checkpoint  → "what the agent believed as of sequence N"
        +
Unreplayed Events (N..crash) → "what the agent decided to do after that, deterministically"
        +
External State (Git, PR API, deployment system) → "what actually happened out there"
        +
Side-Effect Ledger → "what we have proof of attempting/completing, with idempotency keys"
        ↓
State Reconstruction  (replay events onto checkpoint)
        ↓
Pending Action Detection  (which actions were REQUESTED/STARTED but not COMPLETED/FAILED)
        ↓
Side-Effect Reconciliation  (for each pending action, resolve: DONE / NOT_DONE / UNKNOWN)
        ↓
Agent Resume  (only actions resolved DONE or NOT_DONE proceed automatically; UNKNOWN escalates)
```

**Classification logic** for a pending action at crash time:

| Ledger record | External system check | Classification | Action on resume |
|---|---|---|---|
| `COMPLETED` with result stored | — | **Definitely happened** | Use cached result, do not re-execute |
| No ledger record at all | External system shows no matching object (e.g., no commit with that idempotency trailer) | **Definitely did not happen** | Safe to execute (assign idempotency key, execute) |
| `REQUESTED`/`STARTED`, no `COMPLETED`/`FAILED` | External system shows a matching object (commit/PR/resource with the idempotency key embedded) | **Definitely happened, but ledger wasn't updated** | Reconcile ledger to COMPLETED using external evidence, do not re-execute |
| `REQUESTED`/`STARTED`, no `COMPLETED`/`FAILED` | External system check is inconclusive or the side effect is non-queryable (e.g., a webhook fired to a third party with no read-back API) | **Unknown — may have happened** | Must **not** be retried automatically; escalate to `HUMAN_APPROVAL` or, for safe-to-duplicate classes only, mark `MUST_RETRY` under an explicit at-least-once/idempotent-receiver contract |
| `FAILED` | — | **Definitely did not happen** | Safe to retry per policy (backoff, retry budget) |

This is why every side-effecting tool call is designed, at build time, to embed its idempotency key into the external artifact wherever the external API allows it (a `Idempotency-Key` header, a trailer line in a commit message, a client-supplied request ID for PR creation) — so "query the external system" is always possible, turning "unknown" into "definitely happened" as often as the API surface allows.

---

### D.5 Side-Effect Ledger

A dedicated durable store, separate from the Event Log, whose only job is answering "has this exact operation already happened, and with what result?"

**Schema:**

```json
{
  "operation_id": "op_9f21...",
  "idempotency_key": "toolcall:agt_7f1c:step42:git_push:v1",
  "operation_type": "git_push",
  "agent_id": "agt_7f1c...",
  "task_id": "tsk_9a02...",
  "status": "COMPLETED",           // REQUESTED | STARTED | COMPLETED | FAILED | UNKNOWN
  "attempt_count": 1,
  "request_payload_hash": "sha256:...",
  "result": { "commit_sha": "9c1f2ab", "remote_ref": "refs/heads/agent/agt_7f1c/fix-null-deref" },
  "external_evidence_ref": "https://github.com/acme/service/commit/9c1f2ab",
  "created_at": "2026-09-07T09:14:02.100Z",
  "completed_at": "2026-09-07T09:14:03.410Z",
  "compensation": null              // populated if a compensating action was later required
}
```

Covered operation classes: `git commit/push`, PR creation, issue creation, DB writes originating from agent actions, cloud resource creation, deployment triggers, package publication, email/webhook dispatch, any billed/payment-like external API call, file deletion, and infrastructure changes (Terraform apply, etc.).

**Pattern: transactional outbox + inbox.**
- *Outbox*: before calling an external system, the Agent Runtime writes a `REQUESTED` ledger row **in the same transaction** as the event that decided to perform the action (Postgres transaction covering both the `ToolCallRequested` event insert and the ledger row insert). A background dispatcher then picks up `REQUESTED` rows and performs the actual call — so a crash between "decide" and "call" leaves a durable, replayable intent, never a lost one.
- *Inbox*: for effects triggered *into* CAOS from outside (webhooks, CI callbacks, human approval responses), an inbox table deduplicates by the sender's idempotency key/delivery ID before the payload is turned into an event, so a redelivered webhook cannot double-apply.

**Result caching**: `COMPLETED` rows cache the operation's result so a legitimate replay (state reconstruction after crash) returns the same result to the agent's reasoning loop without re-invoking the external system — this is what makes an LLM's "did my push work?" question answerable deterministically instead of triggering a second push.

**Deduplication** happens at three layers for defense in depth: (1) the idempotency key itself, checked before dispatch; (2) receiver-side idempotency where the external API supports it (GitHub's ability to detect a no-op push, an `Idempotency-Key` header on APIs that support it); (3) a reconciliation pass that periodically diffs ledger `COMPLETED` operations against actual external state to catch drift.

**Compensation & rollback**: not all operations are undoable (an email cannot be unsent). Each operation type declares a compensation strategy at build time:
- *Undoable* (cloud resource creation, DB writes originating in CAOS's own schema): direct rollback/delete.
- *Semantically compensable* (a bad commit): revert commit, not history rewrite.
- *Not undoable* (email sent, payment-like call, webhook to a third party): no compensation — these operation classes are **required** to sit behind a Human Approval Gate (Section D.10) rather than fully autonomous execution, precisely because the Side-Effect Ledger can prevent duplication but cannot un-ring a bell.

**Why true exactly-once is not achievable, and what CAOS does instead**: exactly-once *execution* requires a single atomic action spanning "decide to act," "act," and "record having acted" — but the "act" step crosses a network boundary to a system CAOS does not control, so no local transaction can span it. What CAOS actually guarantees is **effectively-once**: at-least-once delivery (retries happen) combined with idempotency at the receiver (duplicate delivery collapses to a single effect) combined with the ledger's dedup guard (a crashed sender doesn't even attempt a duplicate delivery when it can determine, from the ledger, that dispatch already occurred). Where the external system offers no idempotency mechanism at all, CAOS falls back to human confirmation rather than pretending exactly-once is achieved.

### D.6 Coding Workspace Disaster Recovery

A coding Agent's workspace is the highest-value, most failure-prone piece of state: it mixes an externally-owned system of record (Git) with large amounts of derived/ephemeral filesystem content (build artifacts, caches, uncommitted edits) that Git does not track.

**Layered strategy:**

```text
Git                       →  commits, branches — the durable, versioned source of truth for code
      +
Filesystem Snapshot (CoW)  →  point-in-time image of the *entire* sandbox filesystem, including
                                uncommitted changes, untracked generated files, build/test artifacts
      +
Object Storage              →  durable off-node copy of filesystem snapshots + large artifacts
      +
Content-Addressable Storage   →  dedup layer: identical file blobs (deps, base images, generated
                                  boilerplate) stored once, referenced by hash from many snapshots
```

| Item | Source of truth | Recovery mechanism |
|---|---|---|
| Git commits / branches | Git remote (GitHub/GitLab/self-hosted) | Clone/fetch — always recoverable if the remote exists; CAOS also mirrors to a secondary Git remote for remote-outage DR |
| Uncommitted changes | Filesystem snapshot (CoW) | Restore snapshot by `fs_snapshot_id` recorded in the last L4 checkpoint; if no snapshot post-dates last commit, uncommitted work since that snapshot is genuinely lost and is reported, not silently dropped |
| Generated/deleted files | Filesystem snapshot + CAS | Restore snapshot; CAS lets identical generated files (e.g., `node_modules`) rehydrate from content hash instead of re-downloading |
| Build/test artifacts, logs, temp files | Object storage (artifact bucket), keyed by task/step | Not part of the "must recover" workspace state — re-generable by re-running the step; retained for debugging only |
| Package caches, dependency state | CAS-backed shared cache | Rebuildable from lockfiles (deterministic); cache is an optimization, never a dependency for correctness |
| Environment variables | Declared config (Skill/Task definition), not captured from a live process | Reconstructed from declaration at rehydration time; secrets pulled fresh from Secrets Manager, never snapshotted |
| Container filesystem / sandbox state | Ephemeral, rebuilt from image + snapshot overlay | Container is recreated from its declared image; only the CoW overlay (workspace) is restored on top |

**Reconstructing an exact workspace after node/container loss:**

1. Recovery Kernel reads the Agent's last L4 (Workspace) checkpoint → `{repo, branch, last_known_commit, fs_snapshot_id}`.
2. New sandbox is scheduled on any available node; container is created from the Agent's declared base image (immutable, versioned).
3. `git clone`/`fetch` to `last_known_commit` (or the branch tip, then hard-reset to the commit) reconstructs all *committed* state exactly.
4. If `fs_snapshot_id` is non-null and post-dates `last_known_commit`, the CoW snapshot is restored from object storage on top of the clean checkout, restoring uncommitted changes and untracked generated files byte-for-byte.
5. Replay any workspace-mutating events between the snapshot and the crash (from the Event Journal) to bring the workspace to the exact pre-crash state — these are deterministic filesystem operations (write file X, delete file Y) recorded verbatim in `CodeModified`/`ArtifactCreated` events, so replay does not re-invoke the LLM, it re-applies already-decided edits.
6. Side-Effect Reconciler checks whether a `git push`/commit was pending at crash time (Section D.4) before letting the agent proceed to avoid a duplicate commit or a lost one.

### D.7 Memory and Knowledge Recovery

**Source of truth vs. derived data** is the organizing principle:

```text
Source of Truth                          Derived Data (always rebuildable, never authoritative)
────────────────────                     ──────────────────────────────────────────────────────
Raw Documents (object storage, versioned) → Chunking → Embedding → Vector DB index
Episodic Memory log (event-sourced,       → Summarized/compacted episodic memory views
  append-only, in the Event Journal or a
  dedicated memory event stream)
Semantic facts as asserted (a durable      → Knowledge Graph edges/derived relations
  "memory write" record with provenance)
Procedural memory definitions (Skill        → Compiled/cached prompt fragments
  Registry entries, versioned)
```

- **Working memory** is reconstructable state (Section D.1): CAOS stores the *recipe* (which memory refs + retrieval query were used to assemble the current context window), not the assembled tokens. On recovery, the recipe is re-executed against current memory stores.
- **Episodic memory** (what happened in this task) is literally the Event Journal, or a derived, queryable projection of it — so it's automatically durable and replayable; it is never a separate unsynchronized store.
- **Semantic/long-term memory** writes are themselves events (`MemoryAsserted` with provenance pointing at the source task/step), stored durably in Postgres/object storage; the **Vector DB is purely a derived index over these**, rebuildable at will.
- **Reconstruction procedure after Vector DB loss**: (1) provision a fresh vector index; (2) stream all `Raw Documents`/`MemoryAsserted` records from the source-of-truth store; (3) re-chunk and re-embed (this is the expensive, but bounded and fully automatable, step — cost is proportional to corpus size, not to any lost history); (4) swap the new index in behind the retrieval service once a completeness check passes (row count reconciliation between source store and index). Because embeddings are a pure function of (chunk text, embedding model version), the same reconstruction procedure also handles **embedding model upgrades**, not just disaster recovery.
- **Knowledge Graph** entries are similarly derived from semantic memory assertions plus a deterministic extraction pipeline, and are rebuilt the same way.
- **Metadata** (tags, access-control on memory items, retention class) is stored alongside the source-of-truth record, not only in the derived index, so a rebuilt index inherits correct metadata automatically.

### D.8 Tool and MCP Disaster Recovery

The **Tool Gateway** is the reliability boundary between non-deterministic Agent reasoning and the outside world — every tool call and every MCP call passes through it, never directly from the Agent Runtime to an external endpoint.

```text
Agent Runtime → Tool Gateway → { local tool | MCP server | external API }
                    │
                    ├── enforces idempotency-key assignment (ties into Side-Effect Ledger)
                    ├── enforces per-tool timeout, retry policy, circuit breaker
                    ├── validates request against Tool Schema before dispatch
                    ├── validates response against expected schema before returning to Agent
                    ├── records ToolCallRequested/Started/Completed/Failed events
                    └── applies auth/credential injection from Secrets Manager (never from Agent state)
```

| Failure | Gateway behavior |
|---|---|
| Tool timeout | Mark `ToolCallFailed(reason=timeout)`; classify per D.4 (was the underlying action possibly still in flight? if the tool is side-effecting, treat as UNKNOWN, not FAILED, until reconciled) |
| Tool crash / process death | Gateway's own health check detects it; in-flight calls transition to UNKNOWN pending reconciliation, not silently retried |
| MCP disconnect | Gateway attempts reconnect with backoff; any call in flight at disconnect is UNKNOWN until the MCP session is re-established and can be queried, or until external-state reconciliation resolves it |
| Tool version mismatch | Gateway pins tool schema version per Agent Version at call time (from the immutable Tool Registry); mismatched responses are rejected before reaching the Agent, not silently coerced |
| Invalid tool response | Schema validation failure → `ToolCallFailed(reason=invalid_response)`, does not corrupt Agent state |
| External API outage | Circuit breaker opens after threshold failures; Gateway fails fast, Agent's plan step is marked blocked/retryable rather than hanging |
| Auth failure | Gateway attempts one credential refresh from Secrets Manager; persistent failure escalates to Recovery Kernel as a `NON_RECOVERABLE (external dependency)` class, not an agent-level fault |
| Rate limit | Gateway applies token-bucket backpressure per external endpoint, independent of any single agent's retry logic, preventing one agent's retries from starving others |
| Partial execution (e.g., tool wrote 3 of 5 files before dying) | Only relevant for non-atomic tools; such tools are required to declare partial-effect semantics, and the Gateway records exactly which sub-effects completed so recovery can resume mid-operation rather than re-running the whole tool |

The **Tool Registry / MCP Registry / Tool Credentials / Schemas** are themselves versioned, immutable-per-version records (Section D.14 Golden Snapshot) — a corrupted or misbehaving tool version is fixed by rolling the registry pointer back to the last known-good version, not by patching state in place.

### D.9 Durable Task Queue

```text
Queue (Kafka/JetStream/Postgres-backed) + Checkpoint (Section D.3) + Idempotent Tool Execution (D.5, D.8)
   = reliable autonomous task execution
```

- **At-least-once delivery** with consumer acknowledgement; a task message is not removed until the worker (Agent Runtime host) explicitly acks completion of the *step*, not the whole task.
- **Visibility timeout / lease**: a worker holds a time-bound lease on a task; if the lease expires without renewal (worker died), the task becomes visible again for another worker to claim — this is exactly the mechanism that lets a *new* Agent Runtime pick up where an old one died, because the task's durable state (checkpoint + events) is what actually gets resumed, not the queue message itself.
- **Retry / DLQ**: bounded retries with exponential backoff per task; exhausted retries route to a Dead Letter Queue for human triage, tagged with the last failure classification.
- **Priority & scheduling**: priority lanes (interactive/human-blocking tasks > background refactors) and delayed/scheduled delivery for timers (test timeouts, scheduled re-checks).
- **Worker failover**: lease expiry + Recovery Kernel's `recover_task()` (Section F) is the failover path — no separate "worker HA" mechanism is needed beyond making workers stateless with respect to task ownership.
- **Task deduplication**: task creation is itself idempotent (`TaskCreated` events carry a caller-supplied idempotency key), preventing duplicate task graphs from a retried upstream trigger (e.g., a webhook retry that would otherwise spawn the task twice).
- **Task cancellation**: a cancellation is an event (`TaskCancelled`) that any runtime holding the lease observes on its next checkpoint/poll boundary and honors cooperatively — CAOS does not rely on being able to forcibly kill a runtime mid-tool-call, because that is exactly the moment side-effect ambiguity is most dangerous; cancellation completes safely at the next safe point, with the Side-Effect Reconciler still running against whatever was in flight.
- **Task recovery** = `recover_task()` (Section F): checkpoint + replay + reconcile, invoked automatically on lease expiry.

---

### D.10 Control Plane Disaster Recovery

Control-plane services (API Gateway, Scheduler, Agent Manager, Workflow Manager, Task Manager, Resource Manager, Policy Engine, Skill Manager, Tool Manager, Model Router, Recovery Manager) are split by statefulness:

| Service | Statefulness | HA mechanism |
|---|---|---|
| API Gateway | Stateless | N replicas behind LB, no leader needed |
| Model Router | Stateless (routing rules cached from Postgres) | N replicas; cache invalidated via pub/sub on policy change |
| Scheduler | Stateful (owns task assignment decisions) | Leader-elected (etcd/Postgres advisory lock lease); only the leader assigns tasks, replicas are hot standbys |
| Agent Manager | Stateful (agent lifecycle transitions) | Leader-elected per shard (agents sharded by `agent_id` hash) so no single leader bottlenecks the whole fleet |
| Workflow Manager | Stateful (DAG progression) | Leader-elected per workflow shard |
| Task Manager | Backed by Durable Queue | Stateless coordinator over the queue; queue itself is the durable state |
| Resource Manager | Stateful (quota/allocation ledger) | Single leader + Postgres as source of truth; fast failover since state is externalized |
| Policy Engine | Stateless evaluator over versioned policy documents | N replicas, policy documents are immutable-per-version in Postgres/object storage |
| Skill/Tool Manager | Stateless reader over Registries | N replicas |
| Recovery Manager (Recovery Kernel control loop) | Stateful (owns in-progress recovery jobs) | Leader-elected per shard; recovery jobs themselves are checkpointed (Section E.8) so a Recovery Manager failover resumes a recovery job, not restarts it |

- **Leader election & quorum**: via etcd/Kubernetes lease objects (or Postgres advisory locks for smaller deployments) — a leader holds a renewable lease with a short TTL; loss of renewal triggers new election within one TTL window.
- **Fencing**: every leader-only write (e.g., "assign task X to worker Y") is tagged with the leader's current lease epoch/fencing token; downstream stores (Postgres, queue) reject writes carrying a stale epoch, which is the actual split-brain prevention mechanism — election alone does not prevent split-brain, fencing tokens do.
- **Distributed locks**: used sparingly and only for short critical sections (e.g., "claim this task"); CAOS prefers optimistic concurrency (conditional writes with version checks) over long-held locks wherever possible, since long-held locks are themselves a failure-detection burden.
- **Split-brain scenario**: network partition isolates a stale leader from the quorum store; the stale leader's lease expires and it cannot renew (partitioned from etcd/Postgres too), so it self-demotes on next lease-check failure; any writes it attempts after that point are fenced off by the epoch check even if self-demotion is delayed.

### D.11 Data Plane Disaster Recovery

Data-plane components (Agent Runtime, Worker, Sandbox, Container, VM, GPU Worker, CI/Build/Test Worker) are treated as **cattle, not pets** — this is the direct application of Principle 1 to infrastructure.

- **Agent Migration**: triggered by `recover_agent()` (Section F) — a new Agent Runtime, on any healthy node, acquires the agent's lease, restores state (checkpoint + replay + reconcile), and continues. No live migration of process memory is attempted; cold-restart-from-state is preferred because it is testable and deterministic, whereas live migration of an LLM-driven process introduces its own failure surface for little benefit given checkpoint intervals are already short (seconds).
- **Worker Replacement**: identical mechanism at the queue level (Section D.9 lease expiry) — a replacement worker is just a consumer that claims the now-visible task.
- **Task Reassignment**: automatic on lease expiry; manual override available for stuck-but-not-crashed tasks (Section D.12 "Task Stuck" detection) via forced lease revocation + quarantine review.
- **Sandbox Reconstruction**: Section D.6 — image + CoW workspace snapshot.
- **Workspace Reconstruction**: Section D.6.
- **Resource Reallocation**: the Resource Manager treats a failed node's allocations as immediately released (once confirmed dead via failure detection, Section D.12) and re-admits replacement requests through normal admission control (Section D.13), so a node failure cannot itself bypass concurrency/budget limits.

### D.12 Failure Detection

```text
┌───────────────┐   ┌───────┐   ┌─────────┐   ┌────────────┐
│ Heartbeat      │   │ Lease  │   │ Timeout  │   │ Health Check│
│ (liveness ping,│   │ (owner-│   │ (per-op, │   │ (deep check,│
│  every few sec)│   │  ship, │   │  per-step│   │  dependency │
│                │   │  TTL)  │   │  bound)  │   │  probes)    │
└───────┬────────┘   └───┬────┘   └────┬─────┘   └──────┬─────┘
        └────────────────┴─────────────┴────────────────┘
                             │
                    ┌────────┴────────┐
                    │ Watchdog          │  (per-agent: is progress being made at all?)
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │ Anomaly Detection │ (token-rate, tool-call-rate, cost-rate,
                    │                    │  loop-detection via repeated-state hashing)
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      ┌───────────┐  ┌────────────┐  ┌──────────────┐
      │ Circuit    │  │ Bulkhead    │  │ SUSPECTED_    │
      │ Breaker    │  │ (isolate    │  │ FAILURE state  │
      │ (per       │  │  failure    │  │ (Section C.3)  │
      │  dependency)│  │  domain)    │  │                │
      └───────────┘  └────────────┘  └──────────────┘
```

Detected conditions map to signals as follows:

| Condition | Primary signal |
|---|---|
| Process failure | Heartbeat miss + lease expiry |
| Agent failure (crash, unhandled exception) | Heartbeat miss; runtime-reported fatal event |
| Task stuck | Watchdog: no `StepCompleted`/progress event within policy-defined max step duration |
| Workflow stuck | No child task progress within policy window; DAG fan-in never satisfied |
| Tool failure | Tool Gateway timeout/error rate crosses circuit-breaker threshold |
| Model failure | Model Router error rate / latency SLO breach for a given provider |
| Node failure | Kubernetes node-not-ready + kubelet heartbeat loss |
| Storage failure | Volume I/O error rate, snapshot failures, replication lag alarms |
| Network failure | Partition detected via quorum-store connectivity loss, cross-AZ probe failures |
| Database failure | Connection pool exhaustion + replica lag + primary health probe failure |
| Queue failure | Broker unreachable, ISR (in-sync replica) count below minimum |
| Memory pressure | cgroup/OOM-killer signals, RSS trend anomaly |
| GPU failure | ECC error counts, driver reset events, NVML health checks |
| Deadlock | Watchdog: heartbeat present but zero state-transition events for N intervals (alive but not progressing) |
| Livelock | Anomaly detector: high event/tool-call rate with no net task progress (repeated-state hash cycling) |
| Infinite agent loop | Repeated-state hashing across steps; identical (state, context-hash) tuple seen > threshold |
| Token explosion | Per-agent token-rate anomaly vs. budget-derived expected rate |
| Cost explosion | Real-time cost accumulator vs. Policy Engine budget, checked pre-emptively before each expensive call, not just after |

### D.13 Failure Classification & Cascading Failure Prevention

**Failure taxonomy and per-class handling:**

| Class | Detection | Isolation | Recovery | Retry | Rollback | Escalation |
|---|---|---|---|---|---|---|
| Transient (network blip, brief API 5xx) | Timeout/error-rate | None needed | Automatic | Yes, bounded exponential backoff | No | Only if retry budget exhausted |
| Recoverable (worker crash, node loss) | Heartbeat/lease | Quarantine the dead worker's lease, not the agent | `recover_agent`/`recover_task` | N/A (state-level resume, not action retry) | To last valid checkpoint if replay fails | If recovery fails twice, escalate to human |
| Non-recoverable (checkpoint chain fully corrupted, no valid checkpoint exists) | Checkpoint validation failure across all retained levels | Freeze agent | Manual reconstruction from event log from genesis, or task marked lost | No | Full replay from sequence 0 | Always — human decides whether to rebuild from scratch or abandon |
| Corruption (bad data in checkpoint/config/skill) | Checksum mismatch, schema validation failure | Quarantine the corrupted artifact (checkpoint/skill/config version) | Roll back to last known-good version | No | Yes, to prior version | If corruption is repeated/systemic, escalate as possible deployment bug |
| Byzantine-like (tool returns plausible-but-wrong results, model hallucination causing bad plans) | Response schema validation, cross-check against test results, anomaly in output distribution | Sandbox the affected tool/agent, do not treat its output as trusted for side effects | Human review of affected artifacts; do not auto-resume side-effecting steps | No | Revert any commits/actions taken on bad output | Always route through human approval before any external effect proceeds |
| External dependency (3rd-party API outage) | Circuit breaker open | Bulkhead — isolate to that dependency, other tools unaffected | Wait + backoff; degrade task to blocked state | Yes, once dependency health check passes | N/A | If SLA-breaching duration exceeded, escalate |
| Human error (bad approval, wrong config pushed by an operator) | Config diff / anomaly vs. previous known-good | Revert config version | Roll forward once corrected | N/A | Yes, config rollback is a first-class op | Notify affected task owners |
| Security incident (compromised agent, malicious tool, leaked credential) | Policy Engine / anomaly detection / external alert | **Hard quarantine**, credential revocation | Manual only — see Section D.15 | Never automatic | Preserve snapshot for forensics, do not roll back before capture | Always, immediately, to security on-call |
| Resource exhaustion (token/cost/queue/memory explosion) | Anomaly detection, budget breach | Admission control blocks new work in that domain | Backpressure until pressure subsides | Limited, budget-gated | N/A | If sustained, escalate to capacity/cost owner |
| Logic failure (agent plan is internally consistent but wrong — e.g., fixes the wrong bug) | Test failures, human review, downstream verification | None at infra level — this is a task-quality issue | Re-plan step, possibly with a different model/strategy | Yes, bounded | Revert produced artifacts | If repeated across retries, escalate to human |

**Cascading failure prevention** (Coding Agents can spawn sub-agents and retries at a rate no human operator would):

- **Rate limiting & concurrency limits**: per-agent, per-tenant, and global caps on tool calls/sec, spawned sub-agents, and open tasks.
- **Budgets**: hard token/cost/time budgets enforced *pre-emptively* by the Policy Engine before an expensive call is dispatched, not just monitored after the fact.
- **Circuit breakers & bulkheads**: per external dependency and per failure domain (a Tool Gateway breaker tripping for one MCP server does not affect others; one tenant's storm does not throttle another tenant).
- **Backpressure & admission control**: the Durable Task Queue and Agent Manager reject/delay new task admission once in-flight counts, queue depth, or resource pressure cross thresholds, rather than accepting unbounded work and failing later.
- **Quotas**: per-tenant hard ceilings on concurrent agents, sub-agent depth (recursion limit on agent spawning), and total spend.
- **Priority scheduling**: human-blocking/interactive tasks preempt background batch/refactor tasks under contention.
- **Resource isolation & failure domains**: tenants/agents are scheduled into isolated node pools/namespaces where feasible, so a single tenant's runaway workload degrades its own domain first, buying time before it becomes cluster-wide.

### D.14 Security Disaster Recovery

A compromised or malicious Agent must **never** be able to auto-restore itself indefinitely — this is a deliberate exception to "automatic recovery is good."

```text
Suspected compromise signal (anomalous tool use, policy violation, external abuse report)
        ↓
QUARANTINE (Section C.3) — immediate, automatic:
   - revoke the agent's credentials/tokens at the Secrets Manager (not just locally)
   - freeze the workspace (mark sandbox read-only, block further tool dispatch via Tool Gateway)
   - preserve a forensic snapshot (L1 + L4 checkpoint, plus full event tail) BEFORE any further
     mutation, rollback, or GC can touch it
        ↓
FORENSIC CAPTURE — audit logs, event journal, tool call history exported to an immutable,
  access-controlled forensic store; chain-of-custody metadata recorded
        ↓
HUMAN APPROVAL REQUIRED — no automatic path back to RUNNING exists from QUARANTINED;
  a human/security-role principal must explicitly review and approve resumption, deletion,
  or escalation
```

Additional controls: **credential rotation** is routine (short-lived, scoped tokens per agent session, minted per task rather than long-lived per agent); **KMS** encrypts secrets and backups at rest, with key rotation independent of data rotation; **least privilege** — an agent's security context grants only the scopes its declared tool/skill set requires, computed from the immutable Skill/Tool Registry, not requested ad hoc; **token revocation** is push-based (Secrets Manager notifies the Tool Gateway) so a revoked agent cannot use cached credentials; **supply-chain attack** surface (malicious skill/tool/dependency) is mitigated by treating Skill/Tool Registry entries as signed, versioned, immutable artifacts with a rollback path identical to a bad deployment; **backup tampering / ransomware** is mitigated via immutable, versioned, and where appropriate air-gapped backups (Section D.16) so a compromised control plane cannot rewrite history in the backup store itself; **audit logs** are append-only and shipped off-cluster in near-real-time so a compromised node cannot retroactively erase its own trail.

### D.15 Consistency Model

CAOS does **not** claim global ACID consistency — that would be false. Each subsystem's guarantee is explicit:

| Subsystem | Consistency model | Notes |
|---|---|---|
| Agent state (Postgres projection) | Strong (single-writer per agent, via leader/lease) | Reads may hit a replica (eventual) for dashboards; writes always strong |
| Event Store | Strong ordering within a partition (per-agent stream); at-least-once append with idempotent event IDs | Cross-agent ordering is not guaranteed or needed |
| Checkpoint Store | Strong (checkpoint is valid or invalid, no partial reads — object storage's atomic PUT semantics) | — |
| Side-Effect Ledger | Strong for the ledger row itself (transactional outbox in Postgres); eventual/reconciled for agreement with the *external* system | This is the crux of D.4 — ledger-external agreement is achieved via reconciliation, not a distributed transaction |
| Durable Queue | At-least-once delivery, idempotent consumers | Never exactly-once at the transport layer; exactly-once *effect* achieved via D.5 |
| Workspace (Git) | Strong (Git's own object model) | CAOS treats Git as authoritative and never overrides it locally |
| Tool execution | At-least-once request, effectively-once effect (D.5) | — |
| Working/episodic memory | Strong (event-sourced) | — |
| Vector DB | Eventual (derived index, D.7) | Never a source of truth; staleness is acceptable, loss is not permanent |
| Object storage | Strong read-after-write for a given key (S3-class guarantee); versioned | — |

Where genuine cross-system consistency is required (e.g., "the checkpoint and the ledger row agree"), CAOS uses **compensation and reconciliation passes**, not two-phase commit across heterogeneous stores — this is a deliberate trade-off: reconciliation is slower to detect drift but does not introduce a distributed-transaction coordinator as a new single point of failure.

### D.16 Observability

| Category | What's captured |
|---|---|
| Metrics | Per-agent/task/workflow counters and histograms (see SLO list, Section J) |
| Logs | Structured, correlation-ID-tagged logs from every component |
| Traces | Distributed traces spanning LLM call → tool call → external API, using `correlation_id`/`causation_id` as trace context |
| Events | The Event Journal itself is a first-class observability source, not just a recovery source — queryable for "what did this agent do" |
| Audit Logs | Immutable, append-only, off-cluster shipped; covers every policy decision, approval, credential use |
| Recovery Metrics | Emitted by the Recovery Kernel on every recovery attempt (Section J for the metric list) |

Key metrics (defined precisely in Section J): **MTTD, MTTR, RPO, RTO, Checkpoint Latency, Checkpoint Failure Rate, Replay Latency, Recovery Success Rate, Duplicate Side-Effect Rate, Task Recovery Rate, Agent Recovery Rate, Data Loss Rate, False Failure Detection Rate.**

### D.17 Backup Architecture & Golden Snapshot

**3-2-1-style strategy** (3 copies, 2 media/locations, 1 offsite/immutable) applied per data class:

| Data class | Local (fast restore) | Remote/cross-region | Immutable/air-gapped |
|---|---|---|---|
| Database (Postgres) | Continuous WAL streaming + hourly snapshot | Cross-region async replica + daily snapshot copy | Weekly snapshot to write-once object storage, retained 90+ days |
| Event Store | In-cluster replication (3x) | Geo-replicated mirror | Periodic compacted archive to immutable storage |
| Object Store (artifacts, checkpoints, workspace snapshots) | Multi-AZ replication (native to S3-class storage) | Cross-region replication | Versioning + object-lock (WORM) on a retention-tiered subset (checkpoints referenced by open forensic holds, Golden Snapshots) |
| Configuration / Registries (Skill/Tool/MCP/Model/Policy) | Git (source of truth) | Git remote mirror | Signed release tags, immutable by design |
| Secrets metadata (not secret values) | KMS-backed vault replication | Cross-region vault replica | Sealed/offline root-key backup |
| Knowledge (raw documents) | Object storage | Cross-region replication | Immutable archive tier |

**Encryption**: at rest via KMS-managed keys (separate key per data class, rotated independently); in transit via TLS everywhere, including intra-cluster.
**Retention**: tiered — hot (fast restore) for the SLO-driven window, cold/archive for compliance/audit windows, with legal/forensic holds overriding normal expiry.
**Integrity verification**: every backup write includes a checksum; a scheduled verification job restores a sample into an isolated environment and validates checksums + application-level smoke tests (not just "the file exists").
**Restoration testing**: DR drills (Section I) periodically perform a *real* restore of each data class into an isolated environment and validate against acceptance criteria — an untested backup is treated as equivalent to no backup.

**AgentOS Golden Snapshot** — the artifact that lets CAOS be rebuilt on infrastructure that has never run it before:

```text
Golden Snapshot {
  os_version, runtime_version                     // versioned container images / base OS
  agent_definitions, agent_policies                // from Git (IaC-adjacent repo)
  skill_registry, tool_registry, mcp_registry       // versioned registry exports
  model_registry                                     // provider configs, routing rules
  workflow_definitions, prompt_templates               // from Git
  rbac, security_policies                               // from Git / Policy Engine export
  infrastructure_code                                     // Terraform/Helm/K8s manifests, in Git
  database_snapshot_ref                                    // pointer to latest verified DB backup
  event_store_snapshot_ref                                  // pointer to latest verified archive
  object_store_manifest                                      // bucket/key inventory + checksums
  checkpoint_metadata_index                                   // index only, not payload — payloads
                                                                 // are recovered from object storage
  knowledge_metadata                                            // document manifest + versions
}
```

Golden Snapshots are produced on a schedule (e.g., nightly) and before every production deployment, stored immutably, and versioned so "reconstruct CAOS as of Tuesday" is a well-defined operation.

### D.18 Infrastructure Reconstruction & Multi-Region Strategy

**Infrastructure-as-Code**: Terraform provisions cloud resources; Kubernetes + Helm define the runtime topology; GitOps (e.g., ArgoCD) continuously reconciles the live cluster to the Git-declared state, so "the cluster drifted" self-heals and "the cluster is gone" is fixed by pointing ArgoCD at a fresh cluster. Container images are immutable and content-addressed. Secrets are never stored in Git; Terraform/Helm reference Secrets Manager/KMS paths, and actual secret material is restored from the vault's own cross-region replica, not from the Golden Snapshot.

**Reconstruction procedure (cluster is gone, infra doesn't exist)**:
1. Terraform apply against a fresh cloud account/region → base infra (network, K8s cluster, managed DB, object storage buckets).
2. Bootstrap GitOps controller pointed at the infra-code repo → K8s manifests reconcile (control plane, data plane, storage classes).
3. Restore Database from latest verified backup (Section D.17).
4. Point Event Store consumers/producers at a fresh broker; restore compacted archive as the event history baseline.
5. Attach/replicate Object Storage (or restore from cross-region replica if the bucket itself is gone).
6. Apply Golden Snapshot: load registries (Skill/Tool/MCP/Model), policies, workflow/prompt definitions from Git into the freshly-provisioned control plane.
7. Recovery Kernel comes up last and runs a full reconciliation pass (Section F `recover_cluster`) before admitting new task traffic.

**Multi-region strategy comparison:**

| Strategy | Cost | Failover time | Fit for CAOS? |
|---|---|---|---|
| Active-Active | Highest (2x+ compute, cross-region data plane) | Near-zero | Overkill for most CAOS deployments — agent tasks are not latency-critical enough to justify doubling GPU/CI worker cost, and cross-region strong consistency for Agent state would hurt the leader-election model |
| Active-Passive (fully warm data plane standby) | High | Minutes | Reasonable for mission-critical tiers (Section J) but expensive to idle a full data plane |
| **Warm-Standby / Pilot-Light (recommended)** | Moderate | Tens of minutes to a few hours, dominated by data-plane scale-up | **Best fit**: control plane kept warm (fast decision-making, fast "stop admitting new work" / "resume in-flight work" capability) in the standby region; data plane (expensive Agent Runtimes, GPU/CI workers) scaled near zero and scaled up on failover; durable data layer continuously replicated |
| Cold-Standby | Low | Hours to a day | Acceptable only for the lowest SLO tier / dev environments, or as the third (backup) region tier |

**Recommendation**: Region A **Primary** (full active), Region B **Warm-Standby/Pilot-Light** (control plane warm, data plane scaled to near-zero, continuously data-replicated), Region C **Cold-Backup** (object storage + Golden Snapshot only, for the "Region A and B both gone" tail case). This matches CAOS's actual cost driver (compute-heavy, bursty data plane) and its actual recovery need (fast *decisions*, e.g., "which in-flight tasks are recoverable and where," more urgently than fast *compute*).

---

## E. Data Model

### E.1 Agent

```json
{
  "agent_id": "agt_7f1c...",
  "agent_version": "coder-agent:4.2.0",
  "created_at": "2026-09-05T02:11:00Z",
  "task_id": "tsk_9a02...",
  "workflow_id": "wf_44b1...",
  "model_configuration": {
    "provider": "model-router",
    "model_ref": "primary-coding-model:v7",
    "fallback_model_ref": "secondary-coding-model:v3",
    "temperature": 0.2,
    "tool_allowlist": ["git", "shell_sandboxed", "test_runner", "mcp:jira"]
  },
  "system_prompt_ref": { "template_id": "coder_agent_v4", "version": 4 },
  "current_state": "AWAITING_TEST_RESULTS",
  "current_step": { "step_id": "step_42", "index": 42, "of": 87 },
  "context_recipe": { "template_id": "coder_agent_v4", "memory_refs": ["mem_ep_881a"], "retrieval_query_ref": "q_af13" },
  "workspace_ref": { "repo": "git@github.com:acme/service.git", "branch": "agent/agt_7f1c/fix-null-deref", "last_known_commit": "9c1f2ab", "fs_snapshot_id": "snap_0091ffa" },
  "policy_state": { "token_budget_used": 812345, "token_budget_limit": 2000000, "cost_used_usd": 4.12, "cost_limit_usd": 25.00, "quarantined": false, "max_sub_agent_depth": 2, "current_sub_agent_depth": 0 },
  "security_context": { "identity": "svc-agent-agt_7f1c", "scopes": ["repo:write:acme/service", "jira:comment"], "credential_lease_id": "cred_lease_991" },
  "lease": { "runtime_id": "rt_88ab", "node_id": "node_12", "expires_at": "2026-09-07T09:14:35Z" },
  "last_checkpoint": { "checkpoint_id": "ckpt_01J9ZA...", "sequence_number": 48213 }
}
```

### E.2 Task

```json
{
  "task_id": "tsk_9a02...",
  "idempotency_key": "task:jira-ISSUE-4471:v1",
  "workflow_id": "wf_44b1...",
  "created_at": "2026-09-05T02:10:55Z",
  "status": "IN_PROGRESS",
  "priority": "normal",
  "sla_tier": "critical_production",
  "spec": { "repo": "acme/service", "issue_ref": "JIRA-4471", "description_ref": "doc_2291" },
  "assigned_agent_id": "agt_7f1c...",
  "lease": { "worker_id": "wrk_55", "expires_at": "2026-09-07T09:14:35Z" },
  "budget": { "token_limit": 2000000, "cost_limit_usd": 25.00, "wall_clock_limit_hours": 12 },
  "steps_completed": 42,
  "steps_total_estimate": 87,
  "human_approval_state": null
}
```

### E.3 Workflow

```json
{
  "workflow_id": "wf_44b1...",
  "definition_ref": { "workflow_def_id": "feature-delivery-v2", "version": 2 },
  "status": "IN_PROGRESS",
  "dag_position": {
    "completed_nodes": ["plan", "implement", "unit_test"],
    "in_progress_nodes": ["integration_test"],
    "pending_nodes": ["human_review", "deploy"]
  },
  "child_task_ids": ["tsk_9a02...", "tsk_9a03..."],
  "fan_in_state": { "integration_test": { "expected": 3, "completed": 2 } }
}
```

### E.4 Event

(see D.2 for the full envelope; example payload for `ToolCallCompleted`)

```json
{
  "event_id": "evt_01J9Z...", "event_type": "ToolCallCompleted", "event_version": 2,
  "sequence_number": 48213, "agent_id": "agt_7f1c...", "task_id": "tsk_9a02...",
  "correlation_id": "corr_c81e...", "causation_id": "evt_01J9Y...",
  "idempotency_key": "toolcall:agt_7f1c:step42:run_tests:v1",
  "timestamp": "2026-09-07T09:13:58.900Z",
  "payload": { "tool": "test_runner", "call_id": "call_5519", "result": { "passed": 214, "failed": 1 }, "duration_ms": 41221 }
}
```

### E.5 Checkpoint

See D.3 for the full L1 example. Index row (Postgres):

```json
{ "checkpoint_id": "ckpt_01J9ZA...", "agent_id": "agt_7f1c...", "level": "L1",
  "sequence_number": 48213, "storage_key": "checkpoints/agt_7f1c/ckpt_01J9ZA.json",
  "checksum": "sha256:8f2a...", "status": "VALID", "created_at": "2026-09-07T09:14:05Z",
  "expires_at": "2026-12-06T09:14:05Z" }
```

### E.6 Tool Operation

```json
{
  "call_id": "call_5521", "tool": "git_push", "agent_id": "agt_7f1c...",
  "idempotency_key": "toolcall:agt_7f1c:step42:git_push:v1",
  "request": { "remote": "origin", "branch": "agent/agt_7f1c/fix-null-deref" },
  "status": "COMPLETED", "attempt_count": 1,
  "requested_at": "2026-09-07T09:14:02.100Z", "completed_at": "2026-09-07T09:14:03.410Z",
  "result_ref": "op_9f21..."
}
```

### E.7 Side Effect (Ledger Entry)

See D.5 for the full schema.

### E.8 Recovery Job

```json
{
  "recovery_job_id": "rjob_7788...",
  "target_type": "agent",
  "target_id": "agt_7f1c...",
  "trigger": "lease_expired",
  "state": "EVENTS_REPLAYED",
  "started_at": "2026-09-07T09:15:00Z",
  "selected_checkpoint_id": "ckpt_01J9ZA...",
  "replayed_event_count": 3,
  "pending_actions_reconciled": [
    { "call_id": "call_5521", "classification": "CONFIRMED_DONE", "resolved_via": "external_evidence" }
  ],
  "health_check_results": null,
  "assigned_runtime_id": null,
  "escalations": []
}
```

Recovery jobs are themselves checkpointed at each state-machine transition (Section C.3), so a Recovery Manager failover resumes the *recovery* from where it left off rather than restarting the whole recovery from scratch — recovery is recursively made recoverable.

---

## F. Recovery Algorithms

```text
function recover_agent(agent_id):
    lock = acquire_recovery_lock(agent_id)          # fencing token, prevents two recoveries racing
    if lock is None:
        return ALREADY_RECOVERING                    # idempotent no-op; another job owns this

    job = create_or_resume_recovery_job(agent_id)
    job.transition(CONFIRMED_FAILURE)

    if is_quarantine_signal(agent_id):
        job.transition(QUARANTINED)
        revoke_credentials(agent_id)
        freeze_workspace(agent_id)
        capture_forensic_snapshot(agent_id)
        request_human_approval(agent_id, reason="security")
        return job                                    # halts here until human acts

    checkpoint = select_latest_valid_checkpoint(agent_id)
    if checkpoint is None:
        job.transition(ESCALATE)
        notify_human("no valid checkpoint for agent", agent_id)
        return job

    job.transition(CHECKPOINT_SELECTED, checkpoint.id)
    state = deserialize(checkpoint)
    job.transition(STATE_RESTORED)

    events = fetch_events_after(agent_id, checkpoint.sequence_number)
    try:
        for event in events:
            state = apply(state, event)               # pure reducer, no side effects
    except PoisonEventError as e:
        if job.retry_count < MAX_REPLAY_RETRIES:
            job.retry_count += 1
            return recover_agent(agent_id)              # bounded retry of replay itself
        job.transition(ESCALATE)
        notify_human("replay failed", agent_id, e)
        return job

    job.transition(EVENTS_REPLAYED)

    for action in state.pending_actions:
        classification = reconcile_side_effect(action)   # Section D.4 table
        if classification == UNKNOWN:
            job.transition(HUMAN_APPROVAL, pending=action)
            request_human_approval(agent_id, action)
            return job                                     # halt on any unresolved action
        apply_classification(state, action, classification)

    job.transition(SIDE_EFFECTS_RECONCILED)

    runtime = schedule_new_runtime(agent_id, state)
    health = run_health_checks(runtime, state)
    if not health.ok:
        job.transition(ROLLBACK)
        return recover_agent_from(agent_id, older_checkpoint(checkpoint))

    job.transition(HEALTH_VERIFIED)
    bind_lease(agent_id, runtime)
    job.transition(RESUMED)
    release_recovery_lock(lock)
    return job


function recover_task(task_id):
    # A task may span multiple agents (sub-agents); recover each, then reconcile the task rollup
    agent_ids = get_agents_for_task(task_id)
    for agent_id in agent_ids:
        if is_failed_or_stuck(agent_id):
            recover_agent(agent_id)
    reconcile_task_rollup(task_id)                    # recompute derived progress state
    return get_task_state(task_id)


function recover_workflow(workflow_id):
    tasks = get_tasks_for_workflow(workflow_id)
    for task in tasks:
        if is_failed_or_stuck(task.id):
            recover_task(task.id)
    reconcile_dag_position(workflow_id)                 # re-evaluate fan-in/fan-out satisfaction
    unblock_ready_nodes(workflow_id)
    return get_workflow_state(workflow_id)


function recover_node(node_id):
    agents_on_node = get_agents_scheduled_on(node_id)
    mark_node_unschedulable(node_id)                     # stop new admission, race-safe
    for agent_id in agents_on_node:
        # leases for this node's agents will expire naturally; force-expire to speed recovery
        force_expire_lease_if_owner_matches(agent_id, node_id)
        recover_agent(agent_id)
    release_node_resource_allocations(node_id)
    return NODE_DRAINED


function recover_cluster(cluster_id):
    fence_old_control_plane_if_reachable(cluster_id)      # prevent stale writes during rebuild
    provision_infra_if_missing(cluster_id)                # Terraform/GitOps, Section D.18
    restore_database(latest_verified_backup())
    restore_event_store(latest_verified_archive())
    attach_or_restore_object_storage()
    load_golden_snapshot(latest_verified_golden_snapshot())
    bring_up_control_plane()
    bring_up_recovery_kernel()
    for agent_id in list_agents_with_status(RUNNING_OR_UNKNOWN):
        recover_agent(agent_id)                            # bulk recovery pass
    run_full_reconciliation_pass()                          # ledger vs. external systems, cluster-wide
    resume_task_admission()
    return CLUSTER_RECOVERED


function recover_region(region_id):
    assert region_id != current_active_region()
    promote_standby_control_plane(target_region=region_id)   # Section D.18 warm-standby
    scale_up_data_plane(target_region=region_id)
    redirect_traffic(target_region=region_id)                 # DNS/global LB cutover
    recover_cluster(cluster_id_for(region_id))                 # same pass as above, in new region
    return REGION_RECOVERED
```

**Race-condition handling**: every `recover_*` call acquires a fencing-tokened recovery lock keyed by target ID before mutating anything, so two concurrent triggers (e.g., a missed heartbeat *and* a manual operator-initiated recovery) collapse into one job rather than racing to reassign the same agent to two runtimes. Lease binding at the end of `recover_agent` uses a compare-and-swap on the lease record (expected old lease epoch → new epoch) so that if the "dead" runtime was actually alive but partitioned (a false failure detection) and tries to renew its old lease after recovery already bound a new one, the CAS fails and the old runtime is told to self-terminate rather than continue operating with two live runtimes against one agent's state ("zombie fencing").

---

## G. Failure Matrix

| # | Failure | Detection | Isolation | Recovery Mechanism | Data Loss Risk |
|---|---|---|---|---|---|
| 1 | Agent process crash | Heartbeat/lease miss | Lease revoked, task re-visible | `recover_agent` (checkpoint+replay+reconcile) | None (bounded by checkpoint interval) |
| 2 | Agent runtime corruption | Health check / schema validation failure on state | Runtime marked unhealthy, drained | New runtime scheduled; `recover_agent` | None |
| 3 | Model/API failure | Model Router error-rate SLO breach | Circuit breaker opens for that provider | Fallback model route; step retried under new provider | None (idempotent step retry) |
| 4 | Tool failure | Tool Gateway error/timeout | Circuit breaker + bulkhead per tool | Retry per tool policy; if side-effecting, D.4 reconciliation first | Possible UNKNOWN side effect, escalated |
| 5 | MCP server failure | Connection health probe | MCP session isolated, other MCPs unaffected | Reconnect with backoff; reconcile in-flight calls | Possible UNKNOWN side effect, escalated |
| 6 | Task worker failure | Lease expiry | Task re-visible in queue | `recover_task` | None |
| 7 | Container failure | Kubelet/container health check | Pod rescheduled | Sandbox reconstruction (D.6) + `recover_agent` | Uncommitted work since last L4 checkpoint, if any |
| 8 | Sandbox failure | Filesystem/process health check inside sandbox | Sandbox marked tainted, replaced | Workspace reconstruction (D.6) | Uncommitted work since last snapshot |
| 9 | Node failure | Node-not-ready | Node drained, unschedulable | `recover_node` | None beyond in-flight, uncheckpointed work |
| 10 | AZ failure | Multi-AZ health probes fail as a group | Traffic/scheduling shifted away from AZ | Control plane re-elects leader outside AZ; data plane rescheduled to healthy AZs | None (data replicated cross-AZ) |
| 11 | Database failure | Primary health probe + replica lag | Failover to replica | Promote replica (automatic, seconds) or restore from backup (if total loss) | Seconds (sync replica) to backup interval (full loss) |
| 12 | Queue failure | Broker unreachable / ISR below min | Producers/consumers reconnect to healthy brokers | Broker replacement; consumer offsets resume from last committed | None if replication factor ≥ 3 |
| 13 | Object storage failure | Write/read error rate, replication lag | Fail over to cross-region replica for reads | Restore from replica; rehydrate cache | None (versioned, replicated) |
| 14 | Vector DB failure | Query error rate / index health | Retrieval degrades to source-of-truth full-text fallback | Full reconstruction from source documents (D.7) | None (derived data) — latency impact only |
| 15 | Event store failure | Broker/partition health | Isolate affected partitions | Restore from replicated broker / archive | None if replicated; bounded by archive interval otherwise |
| 16 | Network partition | Quorum-store connectivity loss | Fencing prevents split-brain writes | Partition heals → CAS-fenced reconciliation | None (fencing prevents divergent writes) |
| 17 | Control-plane failure | Leader lease expiry | New leader elected | Leader failover (seconds); in-flight leader-only ops retried by callers | None (idempotent control ops) |
| 18 | Kubernetes/cluster failure | Cluster API unreachable cluster-wide | Declare cluster down, invoke `recover_cluster` | Full cluster reconstruction from IaC + Golden Snapshot + backups | Bounded by backup/replication interval |
| 19 | Entire-region failure | Regional health aggregate failure | Fence region, `recover_region` | Promote warm-standby region | Bounded by cross-region replication lag |
| 20 | Configuration corruption | Config schema validation / anomaly vs. prior version | Quarantine the bad config version | Roll back to last known-good version (config is versioned/immutable) | None |
| 21 | Skill/plugin corruption | Registry checksum/schema validation | Quarantine that skill version | Roll back Skill Registry pointer | None |
| 22 | Bad deployment | Canary/health-check regression post-deploy | Halt rollout, isolate new version | Automated rollback to prior deployed version | None |
| 23 | Data corruption | Checksum mismatch on read | Isolate corrupted object/row | Restore from backup / recompute from event log | Bounded by backup/checkpoint interval |
| 24 | Accidental deletion | Absence detected on expected-present check, or explicit report | N/A | Restore from versioned object storage / point-in-time DB restore | Bounded by backup interval, often near-zero (soft-delete + versioning) |
| 25 | Malicious/destructive operation | Policy Engine anomaly, Side-Effect Ledger audit | Hard quarantine (D.14) | Human-gated forensic review; restore from immutable/air-gapped backup | None to the immutable backup tier |
| 26 | Cascading agent failures | Anomaly detection (storm patterns, D.13) | Admission control + circuit breakers + bulkheads engage automatically | Backpressure until pressure subsides; affected agents individually recovered | None to durable state; degraded throughput during event |

---

## H. RPO/RTO Matrix

Assumptions stated explicitly: (a) checkpoint interval for L1 Agent Checkpoints is 30–120 seconds during active steps; (b) database uses synchronous replication within-region and asynchronous cross-region; (c) event store replication factor is 3 within-region, mirrored cross-region with typically sub-minute lag; (d) "RTO" below is *system/component* recovery time, not necessarily the time for every in-flight agent task to fully resume (large numbers of agents recovering in bulk after a cluster/region event are rate-limited by admission control, Section D.13, to avoid a recovery-induced storm).

| Level | Failure | Mechanism | RPO | RTO | Notes |
|---|---|---|---|---|---|
| L0 | Process crash | `recover_agent` from L0/L1 checkpoint | 0–120s of agent progress (bounded by checkpoint interval) | Seconds to ~1 min | Dominant cost is replay of the small unreplayed event tail |
| L1 | Agent/task failure | `recover_agent`/`recover_task` | Same as L0 | 1–5 min | Includes side-effect reconciliation round-trip to external systems |
| L2 | Node failure | `recover_node`, worker/sandbox reconstruction | Uncheckpointed workspace changes since last L4 snapshot (typically < a few min of edits) | 5–15 min | Dominated by sandbox/container cold-start + workspace reconstruction |
| L3 | AZ failure | Cross-AZ control-plane re-election + data-plane reschedule | Near-zero (synchronously replicated within-region) | 10–30 min | Assumes multi-AZ was already the deployed topology, not a migration |
| L4 | Cluster/K8s failure (single region, infra intact) | `recover_cluster` against existing infra | Seconds to minutes (replication-based) | 30–90 min | Time dominated by control-plane bring-up + bulk agent recovery pass |
| L5 | Region failure | `recover_region`, promote warm-standby | Minutes (cross-region replication lag) to the last successful async replication cycle | 1–4 hours | Time dominated by data-plane scale-up in standby region, not data restore |
| L6 | Total disaster (region + backups' primary path affected; rebuild from Golden Snapshot + immutable/cross-region backups on new infra) | `recover_cluster` on freshly provisioned infra, full Golden Snapshot restore | Up to the last verified backup/Golden Snapshot cycle (target: ≤ 24h for full snapshot, much lower for incrementally-replicated stores) | 4–24 hours, workload-dependent | This is the "prove you can rebuild from nothing" drill (Section I); realistic time is dominated by infra provisioning and bulk data restore, not CAOS logic itself |

These are engineering targets to design and test against, not guarantees to a specific customer SLA — actual achieved numbers must be validated by the chaos/DR drills in Section I before being published as commitments (Section J separates "SLO we test for" from "SLA we might sell").

---

## I. Chaos Test Plan

Each experiment follows: **Hypothesis → Failure Injection → Expected Behavior → Recovery Mechanism → Acceptance Criteria.**

| # | Experiment | Hypothesis | Injection | Expected Behavior | Recovery Mechanism | Acceptance Criteria |
|---|---|---|---|---|---|---|
| 1 | Kill Agent | Agent resumes from checkpoint with no duplicate side effects | SIGKILL the Agent Runtime process mid-tool-call | Task transitions to SUSPECTED_FAILURE within one missed heartbeat, then recovers | `recover_agent` | Task resumes within L0/L1 RTO target; zero duplicate side effects in Ledger audit |
| 2 | Kill Worker | Task reassigns to a new worker | SIGKILL the worker process holding a task lease | Lease expires, task becomes visible, new worker claims it | Queue lease expiry + `recover_task` | Task completes; no message loss; exactly one worker executes each step |
| 3 | Kill Node | All agents on the node recover elsewhere | Terminate a node instance | Node marked NotReady, agents recovered on other nodes | `recover_node` | 100% of affected agents resume within L2 RTO; node resources released |
| 4 | Kill Database (primary) | Automatic failover to replica with bounded loss | Kill the Postgres primary | Replica promoted; control plane reconnects | DB failover automation | RTO within L1 (control-plane) target; RPO within sync-replication bound |
| 5 | Drop Network (partition control plane from quorum store) | No split-brain writes occur | iptables-drop traffic between a control-plane replica and etcd/Postgres | Isolated replica self-demotes; no fenced writes succeed from it | Leader lease expiry + fencing tokens | Zero writes accepted from a fenced/stale leader, verified via audit log |
| 6 | Delay Network | System degrades gracefully, doesn't false-positive on failure | Inject 2–5s latency between Tool Gateway and an MCP server | Circuit breaker does NOT trip prematurely; timeouts scale appropriately | Timeout tuning, health check hysteresis | False-failure-detection rate stays under target (Section J) |
| 7 | Corrupt Checkpoint | Recovery falls back to older valid checkpoint | Flip bits in a stored L1 checkpoint blob | Checksum validation fails; Selector picks next-older valid checkpoint, replays forward | Checkpoint validation + ROLLBACK branch | Agent resumes correctly from older checkpoint + replay; no crash loop |
| 8 | Delete Workspace | Workspace fully reconstructs from Git + snapshot | Delete the sandbox filesystem out from under a running agent | Sandbox failure detected; reconstruction from D.6 pipeline | `recover_agent` + workspace reconstruction | Reconstructed workspace is byte-identical (hash-verified) to expected state at last snapshot + replayed edits |
| 9 | Kill MCP | In-flight MCP calls reconcile correctly, no silent loss | Kill an MCP server process mid-call | Call transitions to UNKNOWN, reconciled on MCP reconnect or external check | Tool Gateway reconnect + D.4 reconciliation | Zero calls silently dropped or silently duplicated |
| 10 | Break Tool | Bad tool version isolated without corrupting agent state | Deploy a tool version that returns malformed responses | Schema validation rejects responses; agent step marked failed, not corrupted | Tool Registry rollback | Agent state remains valid (passes schema validation) throughout |
| 11 | Break Model API | Fallback model takes over transparently | Return 500s from primary model provider | Circuit breaker opens; Model Router switches to fallback | Model Router fallback routing | Task continues without human intervention within SLO error budget |
| 12 | Duplicate Event | Idempotent processing prevents double-apply | Redeliver an already-processed event to a consumer | Event is recognized as already-applied via event_id/idempotency key | Idempotent reducers / inbox dedup | State identical to single-delivery case |
| 13 | Reorder Event | Per-agent ordering guarantee holds despite broker-level reordering elsewhere | Deliver two unrelated agents' events out of relative order | Per-agent stream order unaffected; only same-partition order matters | Partitioning by agent_id | No agent's own event order is violated |
| 14 | Duplicate Tool Call | Side-Effect Ledger prevents a second git push | Force a retry of an already-COMPLETED tool call | Ledger lookup short-circuits before dispatch | Side-Effect Ledger dedup guard | Exactly one push lands in Git; Duplicate Side-Effect Rate = 0 for this run |
| 15 | Corrupt Vector Index | Retrieval degrades, not fails; full recovery possible | Corrupt the vector DB index | Retrieval falls back / flags staleness; reconstruction job triggered | D.7 reconstruction from source documents | Index fully rebuilt with 100% document coverage verified by count reconciliation |
| 16 | Corrupt Configuration | Bad config auto-rolled-back | Push a config version that fails schema validation post-deploy | Deployment halts / rolls back automatically | Config versioning + rollback | No agent observes the corrupted config; rollback completes within L4-equivalent RTO |
| 17 | Expire Credential | Agent doesn't fail hard; refreshes or gracefully blocks | Force-expire a tool credential mid-task | One refresh attempt; on persistent failure, task blocks (not corrupts) pending new credential | Tool Gateway credential refresh path | Task resumes automatically once credential is renewed, with zero corrupted state |

Chaos experiments run continuously in a dedicated non-production environment against production-representative topology, and a curated safe subset runs in production under strict blast-radius controls (single-tenant, off-peak, auto-abort on SLO breach).

---

## J. Acceptance Criteria & SLOs

### Disaster Recovery Acceptance Test Matrix (pass/fail)

| Test | Pass Criteria |
|---|---|
| Agent crash | Agent resumes with correct `current_step`; zero duplicate side effects; RTO within L0/L1 target |
| Agent migration | Agent resumes on a different node/runtime with identical logical state (hash-comparable state fields match pre-crash checkpoint + replay) |
| Task recovery | Task completes with correct final artifacts; no step re-executed with a different (non-idempotent) result than originally intended |
| Workflow recovery | DAG fan-in/fan-out state correctly reconciled; no child task double-spawned |
| Node loss | 100% of agents on the lost node recovered within L2 RTO; zero resource-allocation leaks |
| AZ loss | Control plane re-elects and data plane reschedules within L3 RTO; zero split-brain writes (verified via fencing-token audit) |
| Database loss | Failover/restore completes within L4-equivalent RTO; data loss ≤ declared RPO, verified by comparing last-committed sequence numbers |
| Queue loss | Zero message loss at replication factor ≥ 3; consumers resume from last committed offset |
| Vector DB loss | 100% document coverage rebuilt (row-count reconciliation); zero permanent knowledge loss |
| Object storage loss | Restored from cross-region replica with zero object loss (versioned); checksum-verified |
| MCP failure | All in-flight calls resolved to DONE/NOT_DONE/escalated — zero left silently UNKNOWN after reconciliation window |
| Tool timeout | Task step marked failed/retried per policy; zero corrupted agent state |
| External API failure | Circuit breaker opens within configured error-rate threshold; task blocks rather than hangs indefinitely |
| Network partition | Zero fenced-leader writes accepted (audit-verified) |
| Control-plane failure | New leader elected within lease-TTL-bound window; zero duplicate task assignments |
| Region failure | Standby promoted within L5 RTO; RPO within cross-region replication bound |
| Corrupted checkpoint | Fallback to older valid checkpoint succeeds; agent state after recovery matches expected via replay-verification |
| Duplicate side effect | Ledger dedup guard blocks re-execution 100% of the time in test corpus |
| Partial external execution | Reconciliation correctly classifies DONE/NOT_DONE/UNKNOWN in 100% of test corpus with known ground truth |
| Bad deployment | Automated rollback triggers within canary-window and restores prior good version with zero manual steps |
| Security compromise | Quarantine engages automatically; zero automatic path back to RUNNING without human approval, verified by policy audit |

### Engineering SLOs

| Metric | Normal Production | Critical Production | Mission-Critical Agent |
|---|---|---|---|
| Agent Recovery Success Rate | ≥ 99.0% | ≥ 99.5% | ≥ 99.9% |
| Task Recovery Success Rate | ≥ 99.0% | ≥ 99.5% | ≥ 99.9% |
| Data Durability (durable stores) | ≥ 99.999% (11 9s object storage baseline) | same | same |
| RPO | ≤ 5 min | ≤ 1 min | ≤ 30 sec (sync replication tier) |
| RTO (agent/task level, L0/L1) | ≤ 5 min | ≤ 2 min | ≤ 1 min |
| Checkpoint Availability | ≥ 99.9% (checkpoint write succeeds) | ≥ 99.95% | ≥ 99.99% |
| Event Durability | ≥ 99.999% (replicated) | same | same |
| Side-Effect Safety (Duplicate Side-Effect Rate) | ≤ 0.01% of side-effecting ops | ≤ 0.001% | 0% (any duplicate is a Sev-1) |
| Control Plane Availability | ≥ 99.9% | ≥ 99.95% | ≥ 99.99% |
| Recovery Automation Rate (% of recoveries requiring zero human action) | ≥ 90% | ≥ 95% | ≥ 98% (excluding security-gated recoveries, which are *intentionally* manual) |

**MTTD / MTTR / other operational metrics** are tracked continuously and reviewed against these SLOs monthly; **False Failure Detection Rate** is tracked as a guardrail metric (a system that "recovers" agents that weren't actually failed is itself a reliability bug) with a target of < 0.5% of all triggered recoveries.

---

## K. Technology Stack

For each component: **Why / Alternative / Trade-off / Failure Mode / Scaling Limit / Operational Complexity.**

| Component | Recommended | Why | Alternative | Trade-off | Failure Mode | Scaling Limit | Op Complexity |
|---|---|---|---|---|---|---|---|
| Container orchestration | **Kubernetes** | De facto standard for scheduling disposable Agent Runtimes/sandboxes; rich node-failure and rescheduling primitives | Nomad | Nomad is operationally simpler but has a smaller ecosystem for GPU scheduling / sandboxing patterns | Control-plane etcd quorum loss | Thousands of nodes; multi-cluster needed beyond that | High (but industry-standard, tooling mature) |
| Relational state store | **PostgreSQL (HA, e.g., via Patroni)** | Strong consistency for Agent/Task/Workflow projections and the Side-Effect Ledger outbox; mature backup/PITR tooling | CockroachDB / Spanner-class | Distributed SQL gives easier multi-region strong consistency at higher operational and latency cost | Primary failure; replication lag under heavy write load | Vertical scaling limits, then read-replica fanout; sharding by tenant beyond that | Moderate (Patroni/HA setup) to High (self-managed at scale) |
| Coordination / quorum | **etcd** (or Kubernetes' own etcd) | Leader election, leases, fencing tokens — proven for exactly this role | Consul, ZooKeeper | Consul offers built-in service mesh; ZooKeeper is heavier operationally | Quorum loss (need odd-numbered majority) | Small keyspace by design — not a general data store | Moderate |
| Event streaming | **Kafka** (or **Redpanda** for lower-latency/ops-simpler ops) | Partitioned, ordered, replicated log matches the per-agent-stream event-sourcing model exactly | NATS JetStream | JetStream is lighter-weight, simpler to run, good fit for the low-resource profile; weaker ecosystem for large-scale compaction/replay tooling | Broker/partition unavailability if replication factor too low | Very high (proven at massive scale) for Kafka; JetStream scales well for small-to-mid deployments | High (Kafka) vs. Low-Moderate (Redpanda/JetStream) |
| Durable task queue | **Kafka/JetStream topics + consumer-group leases**, or **Temporal** for workflow-level durable execution | Temporal directly models "durable, replayable, checkpointed long-running workflow" — a very close match to the Agent Recovery Kernel's own model | Plain Postgres-backed queue (e.g., via `SKIP LOCKED`) | Temporal adds a new dependency and its own operational surface but removes a large amount of hand-built recovery-kernel code; a Postgres queue is simplest for the low-resource profile | Temporal cluster failure; queue broker failure | Temporal scales to large workflow counts; Postgres-queue approach scales to moderate throughput | Temporal: Moderate-High; Postgres queue: Low |
| Object storage | **S3-compatible (S3 / GCS) in cloud; MinIO on-prem/dev** | Versioning, cross-region replication, object-lock (WORM) natively support checkpoint/backup/immutability needs | Ceph (RGW) | Ceph gives full control and on-prem flexibility at higher operational burden | Bucket-level outage (rare, region-scoped for cloud providers) | Effectively unbounded for cloud S3-class; Ceph scales with cluster size | Low (cloud S3) vs. High (self-hosted Ceph) |
| Vector database | **Any managed/self-hosted vector DB treated as a cache** (e.g., pgvector for small deployments, a dedicated vector DB for scale) | Since D.7 treats it as fully derived/rebuildable, the specific choice matters far less than the reconstruction pipeline around it | pgvector (colocate with Postgres) | pgvector avoids a new system for smaller deployments at the cost of scaling ceiling | Index corruption, query-node failure | Depends on chosen engine; irrelevant to durability since it's derived | Low (pgvector) to Moderate (dedicated cluster) |
| Observability: metrics | **Prometheus + Grafana** | Standard, pull-based, integrates with Kubernetes and custom Recovery Kernel metrics | Datadog/managed | Managed reduces ops burden at direct cost | Local Prometheus data loss is acceptable (metrics are not a durability-critical store) | Federation needed at very large scale | Low-Moderate |
| Observability: logs | **Loki** (or managed equivalent) | Pairs naturally with Prometheus/Grafana, cost-efficient for high log volume | ELK/OpenSearch | OpenSearch gives richer full-text search at higher resource cost | Ingest pipeline backpressure | Scales with storage; ingestion rate limits need sizing | Moderate |
| Observability: traces | **OpenTelemetry** (collector + a backend, e.g., Tempo/Jaeger) | Vendor-neutral instrumentation standard, matches the correlation-ID model directly | Vendor-specific APM | Vendor APM often has richer UI at lock-in cost | Collector overload | Scales with sampling strategy | Moderate |
| IaC | **Terraform** | Cloud-agnostic, mature state-management model fits "reconstruct from nothing" requirement | Pulumi | Pulumi offers general-purpose language IaC at a smaller ecosystem | Terraform state corruption (mitigate with remote state + locking) | N/A (declarative) | Moderate |
| GitOps / deployment | **ArgoCD** | Continuous reconciliation to Git-declared state directly implements "config is code, cluster self-heals to it" | Flux | Comparable; ArgoCD's UI/multi-cluster tooling is more mature for this use case | ArgoCD controller failure (recoverable, it's stateless-reconciling) | Scales to many clusters/apps | Moderate |
| Secrets / KMS | **Vault + cloud KMS** | Vault gives dynamic, short-lived credential leases matching the "credential per agent session" security model; KMS anchors encryption keys outside the app | Cloud-native secrets manager only | Simpler ops, less dynamic-lease flexibility | Vault unseal/quorum event | Scales well; unseal process needs careful DR planning itself | Moderate-High |
| Version control | **Git** (with a mirrored secondary remote for DR) | Non-negotiable source of truth for code; already how the domain works | N/A | N/A | Remote provider outage (mitigated by secondary mirror) | N/A | Low |

**Deliberately not blindly chosen**: Kafka is *not* automatically the right event store for a small/dev deployment — its operational weight outweighs its benefit below a certain scale, which is why Section K's low-resource profile substitutes NATS JetStream. Similarly, a dedicated vector DB cluster is not justified until corpus size and query load actually require it; pgvector alongside the existing Postgres HA setup avoids a new failure domain for smaller deployments.

### Low-Resource Deployment Profiles

Both profiles share the same **logical** architecture (Agent Recovery Kernel, Event Sourcing, Checkpointing, Side-Effect Ledger, the state model) — only the physical technology binding changes.

**Development / Single Node**
```text
Docker Compose:
  - PostgreSQL          (state, side-effect ledger, checkpoint index)
  - NATS JetStream       (event stream + durable queue, single-node mode)
  - MinIO                 (object storage: checkpoints, workspace snapshots, artifacts)
  - Agent Runtime(s)        (containerized, disposable, as many as the box supports)
  - Recovery Manager          (single instance; leader election degenerates to "only instance")
  - pgvector extension          (co-located with Postgres for RAG)
```
Recovery semantics are *identical in kind* to production (checkpoint + replay + reconcile) — only the RTO/RPO numbers differ, since there is no cross-node/cross-AZ/cross-region redundancy. This profile is explicitly a development/small-team environment, not a production DR target; its acceptance tests (Section I) validate the *logic*, not the *availability*.

**Production / Distributed**
```text
Kubernetes (multi-node, multi-AZ):
  - HA PostgreSQL (Patroni)         — state, ledger, checkpoint index
  - Kafka/Redpanda (replicated)      — event stream; Temporal optional for workflow durability
  - S3-class object storage (replicated cross-region) — checkpoints, snapshots, backups
  - Distributed workers (Agent Runtime, CI/build/test workers, GPU workers as node pools)
  - Multi-AZ within Region A, Warm-Standby Region B, Cold-Backup Region C
  - Vault + KMS, Prometheus/Grafana/Loki/OTel, Terraform + ArgoCD
```

The shared logical architecture is what makes the migration path from dev to production a matter of swapping infrastructure bindings (NATS→Kafka, single Postgres→Patroni HA, MinIO single-node→S3 multi-region) rather than rewriting the Recovery Kernel, event schema, or checkpoint format.

---

## L. Implementation Roadmap

| Phase | Features | Dependencies | Risks | Acceptance Tests |
|---|---|---|---|---|
| **1 — Local Recovery** | Agent State Model (D.1) defined and implemented; L0/L1 checkpointing; single-node Recovery Kernel skeleton (detect → checkpoint → restart) | None (foundation phase) | Under-scoping the state model forces breaking schema changes later — invest real time in D.1/E.1 before writing checkpoint code | Kill Agent (Chaos #1) passes on single node |
| **2 — Agent Checkpoint** | Full multi-level checkpoint hierarchy (L0–L5); checkpoint validation, versioning, GC; checkpoint format finalized (Section D.3/E.5) | Phase 1 state model | Checkpoint format churn if event schema isn't stable yet — freeze event envelope (D.2) before finalizing checkpoint schema | Corrupt Checkpoint (Chaos #7) passes; checkpoint GC verified to never delete a referenced checkpoint |
| **3 — Event Sourcing** | Full event journal (all event types from D.2); deterministic replay engine; idempotency-key derivation standardized | Phase 1/2 (state and checkpoint reducers must exist to be replay targets) | Non-deterministic reducers (accidentally calling out to a live system during replay) silently break recovery — enforce via lint/test that reducers are pure | Duplicate Event (#12), Reorder Event (#13) pass |
| **4 — Side-Effect Safety** | Side-Effect Ledger; transactional outbox/inbox; Tool Gateway idempotency enforcement; D.4 reconciliation logic | Phase 3 (events drive ledger writes) | This is the highest-risk phase for silent data-integrity bugs — under-test here shows up as production duplicate PRs/commits later | Duplicate Tool Call (#14), Kill MCP (#9), Partial External Execution acceptance test |
| **5 — Cluster HA** | Control-plane leader election + fencing (D.10); Durable Task Queue with lease-based failover (D.9); `recover_node`/`recover_task` implemented | Phases 1–4 | Fencing token misuse (forgetting to check the epoch somewhere) reintroduces split-brain — audit every leader-only write path | Kill Worker (#2), Kill Node (#3), Drop Network (#5) pass |
| **6 — Multi-AZ** | Multi-AZ data-plane scheduling; cross-AZ replication for DB/event store/object storage; `recover_node`/AZ-level failure detection | Phase 5 | Cost/latency trade-offs from synchronous cross-AZ replication need real load testing, not assumption | AZ loss acceptance test (Section J) passes under realistic load |
| **7 — Multi-Region** | Warm-standby Region B; Golden Snapshot pipeline (D.17); `recover_region`; cross-region replication for all durable stores | Phase 6 | Region promotion runbooks must be drilled, not just documented — an untested failover procedure is the single biggest real-world DR risk | Region failure drill (Chaos + full `recover_region`) meets L5 RTO/RPO targets |
| **8 — Autonomous Chaos Recovery** | Full chaos engineering framework (Section I) running continuously in non-prod and a safe subset in prod; security quarantine automation (D.14); cascading-failure protections (D.13) tuned from real traffic patterns | Phases 1–7 | Automating too much recovery too early can mask real bugs — this phase should *increase* automation only as Recovery Success Rate metrics (Section J) prove out under chaos | Full acceptance-test matrix (Section J) passes continuously in CI-style chaos runs; SLOs met over a sustained observation window before declaring GA |

Each phase's acceptance tests must pass, and its SLO-relevant metrics must be observed under real or chaos-injected load, before the next phase begins layering additional infrastructure — this is deliberate: Phase 7/8 infrastructure investment is wasted if Phase 1–4's core state/checkpoint/ledger model has latent correctness bugs, since every later phase depends on those primitives being trustworthy.

---

## M. Architectural Q&A Appendix

**1. What exactly is an Agent?**
A logical state machine — an identity plus a durable, reconstructable state (task, workflow position, context recipe, memory references, pending actions, policy state) — that happens to be *executed* by a disposable runtime process for a while. The Agent is the state; the runtime is a rented, replaceable compute lease.

**2. What is the minimum state required to reconstruct an Agent?**
The last valid checkpoint (Section D.3) plus the event tail since that checkpoint's sequence number, plus resolution of any pending actions against the Side-Effect Ledger and external systems (Section D.4). Nothing else is required — specifically, no live process memory, no runtime handles, and no re-derivation of context text (only its recipe) is needed.

**3. What should never be checkpointed?**
Raw credential material, ephemeral runtime handles (sockets, GPU pointers, in-process caches), fully-assembled prompt/context text (store the recipe), and anything whose source of truth is external (don't checkpoint file contents Git already owns — checkpoint the commit SHA).

**4. Which state should be event-sourced?**
Anything that represents a *decision or observed transition*: plan steps, tool call requests/results, test outcomes, human approvals, commits, deployments. This is state whose history matters for both replay and audit.

**5. Which state should be snapshotted?**
The *current fold* of event-sourced state, at multiple levels (D.3), purely as a performance optimization so recovery doesn't replay from genesis. Also: large externally-owned artifacts represented as CoW filesystem snapshots (workspace state), which are snapshots in the storage sense, not the event-sourcing sense.

**6. How can an Agent resume after a crash?**
Via `recover_agent` (Section F): select last valid checkpoint → replay unreplayed events (pure, no side effects) → reconcile pending actions against the Side-Effect Ledger and external systems → verify health → bind a new runtime and resume.

**7. How can we prevent duplicate tool execution?**
Deterministic, event-derived idempotency keys assigned before dispatch; a Side-Effect Ledger that records intent (`REQUESTED`) in the same transaction as the deciding event, checked before every dispatch attempt; and, where the external API supports it, embedding the idempotency key into the artifact itself so a post-hoc external check can confirm completion without re-executing.

**8. How can we recover from an external side effect whose result is unknown?**
Query the external system of record using the embedded idempotency key/evidence (Section D.4's classification table). If that resolves it, proceed accordingly. If it remains genuinely ambiguous (no read-back capability), the action is never silently retried or silently assumed done — it escalates to `HUMAN_APPROVAL`.

**9. How can we reconstruct an exact coding workspace?**
Git for committed history + a CoW filesystem snapshot for uncommitted/generated state + content-addressable storage for dedup + replay of any workspace-mutating events since the snapshot (Section D.6). The combination reconstructs the workspace byte-for-byte, not approximately.

**10. How can Vector DB loss be recovered?**
The Vector DB is never a source of truth (Section D.7) — it's rebuilt by re-chunking and re-embedding from the durable document/memory-assertion store. Cost is proportional to corpus size and is fully automatable; no permanent knowledge is lost, only temporary retrieval latency during rebuild.

**11. How can a whole cluster be reconstructed?**
`recover_cluster` (Section F): provision infra via IaC if it doesn't exist, restore the database and event store from verified backups, reattach/restore object storage, load the Golden Snapshot (registries, policies, definitions), bring up the control plane and Recovery Kernel, then run bulk agent recovery plus a full reconciliation pass before resuming task admission.

**12. How can a whole region be reconstructed?**
`recover_region`: promote the warm-standby region's control plane, scale up its data plane, redirect traffic, and run the same `recover_cluster` procedure targeting that region. The Pilot-Light/Warm-Standby strategy (Section D.18) means this is a scale-up and cutover, not a from-scratch build.

**13. How can a compromised Agent be quarantined?**
Immediately and automatically on suspicion: revoke credentials at the Secrets Manager, freeze the workspace, capture a forensic snapshot before any further mutation, and require explicit human approval before any path back to `RUNNING` — this is the one place in the system where automatic recovery is deliberately disabled (Section D.14).

**14. How do we prevent cascading failures?**
Layered admission control, per-agent/tenant/global concurrency and budget limits enforced pre-emptively, circuit breakers and bulkheads per dependency and failure domain, and backpressure that degrades throughput before it fails outright (Section D.13).

**15. What is the correct consistency model?**
There isn't one global model — each subsystem has an explicit, locally-appropriate guarantee (Section D.15): strong within a single agent's state and event stream, at-least-once with idempotent effects for external side effects, eventual for derived indices like the Vector DB, and reconciliation (not distributed transactions) across heterogeneous stores.

**16. What should be the source of truth?**
Git (code), the event-sourced Agent/Task/Workflow state in Postgres (logical progress), the Side-Effect Ledger (what external actions were attempted/confirmed), object storage (checkpoints, artifacts, backups), and the raw document/memory-assertion store (knowledge).

**17. What should be derived data?**
The Vector DB index, the Knowledge Graph, assembled prompt/context text, aggregated progress/cost metrics, and checkpoints themselves (a checkpoint is a cached fold of events — regenerable, never authoritative over the event log it was derived from).

**18. How can the architecture support autonomous software factories running tasks for days or weeks?**
By making the checkpoint interval and event granularity independent of total task duration — a week-long refactor is just a longer event stream with the same per-step checkpoint cost as a five-minute task. Multi-level checkpointing (D.3) bounds replay cost even after long runs; the Side-Effect Ledger bounds the blast radius of any single crash regardless of how many external actions preceded it; and cascading-failure controls (D.13) bound resource consumption over long horizons so a multi-week task cannot silently drift into a runaway cost or token spend. The task's durability guarantee comes from the invariant itself — `Checkpoint + Event Log + Durable State + Side-Effect Ledger` — which holds identically whether the task has run for five minutes or five weeks.

---

### Distinguishing Traditional Distributed-System DR from AgentOS DR

Traditional DR assumes deterministic, replayable request/response processing and typically treats "restart the process, replay the request" as sufficient. AgentOS DR must additionally account for: **non-deterministic generation** (an LLM call cannot be deterministically replayed — only its *recorded output* can be replayed as an event), **irreversible external side effects triggered autonomously** (a traditional web service rarely autonomously opens pull requests or deploys code without a human in the loop per request), **long-running, multi-day tasks** where the cost of losing progress is far higher than a typical request-scoped failure, **self-directed retry and debugging loops** that can amplify a failure into a storm faster than human operators can react, and **workspace state** (a mutable coding sandbox) that has no equivalent in stateless request-processing systems. This is why CAOS's architecture centers on the Side-Effect Ledger and the Checkpoint+Event+Ledger invariant rather than on the connection-pooling and stateless-retry patterns that dominate conventional DR literature.
