# Universal Computational System Architecture (UCSA)
### A minimal, composable substrate for OS, AgentOS, simulation, quant, game-engine, and software-factory systems

---

## 1. Executive Architectural Thesis

Every computational system that observes, decides, and acts can be built from the same six mechanisms:

**State, Event, Capability, Scheduler/Executor, Constraint Checkpoint, Clock.**

Everything else usually presented as a "primitive" — World, Goal, Policy, Memory, Evaluation, Agent — is a **derived construct**: a disciplined composition of the six primitives, not a new kind of mechanism. This is the central architectural claim of UCSA, and Section 34 proves it.

The design optimizes:

```
Generality + Composability + Determinism + Observability + FaultTolerance + Extensibility − Complexity
```

by refusing to add an abstraction unless removing it breaks at least two of the target domains (OS, AgentOS, coding agent, simulation, game engine, quant system, robotics, workflow automation, database system, distributed system, digital twin, scientific computing).

---

## 2. Formal Mathematical Model (revised)

The prompt's starting model conflates three distinct things: the *true* dynamics of the world, the system's *belief* about those dynamics, and the *policy* that acts on that belief. This conflation is the single most common defect in real agent/OS architectures (Section 31, Q3–Q6). UCSA corrects it explicitly.

**Ground truth (owned by World, may be partially unknown to the system):**

```
S_{t+1} = F(S_t, A_t, ξ_t)
```
`ξ_t` is exogenous noise / environment nondeterminism (market moves, hardware faults, other agents). `F` is never fully known to the system — it is only ever *approximated*.

**Perception (owned by Observation layer, not by Policy):**

```
O_t = Obs(S_t, ξ_t')            # a lossy, agent-specific projection of true state
Ŝ_t = Believe(Ŝ_{t-1}, O_t, M_t) # belief-state update, handles partial observability
```

**Model (an explicit, versioned approximation of F — never assumed to equal F):**

```
M_t = (Θ_t^M, predict)      predict: (Ŝ_t, A) → distribution over Ŝ_{t+1}
```

**Policy (a decision function, separate from both State and Model):**

```
A_t = π(Ŝ_t, G, M_t, Mem_t, Θ_t^π)
```

**Capability execution (the ONLY channel through which A_t becomes a real state transition):**

```
(S_{t+1}, Result_t) = Execute(Capability(A_t), S_t, Permissions, Budget)
```
This is the missing link in the original formula: `F` is not directly callable by anyone. `A_t` names a *Capability*; the Runtime is the only component permitted to invoke `Execute`, and only after a Constraint check.

**Evaluation and update (operate on parameters, never directly on ground-truth state):**

```
E_t = Eval(trajectory_{t-k:t}, G)
Θ_{t+1}^M, Θ_{t+1}^π = Update(Θ_t^M, Θ_t^π, E_t, Trace_t)
```

**Corrected closed loop:**

```
Observe → Believe → Retrieve(Memory) → Decide(Policy+Model) → Authorize(Constraints)
   → Execute(Capability via Runtime) → Log(Event) → Evaluate → Update(Model/Policy params) → Observe
```

The key correction vs. the prompt's version: **Update never mutates ground-truth State directly** — only Capability execution does that. Update only mutates `Θ^M` and `Θ^π` (learning), which is a completely different, slower, governed pathway. Collapsing these two update pathways is what causes runaway/uncontrolled agents in practice.

---

## 3. Universal System Meta-Model

Each abstraction is defined by what it **owns**, what it **must never own**, its **interface**, and its **invariant**. This table is intentionally terse — precision over prose.

| # | Abstraction | Purpose (why it exists) | Owns | Must NOT own | Core interface | Lifecycle | Invariant |
|---|---|---|---|---|---|---|---|
| 1 | **World** | Ground-truth container for everything that exists | Entities, Relationships, Rules, Environment, true `S_t` | Policy logic, Goals | `getEntity`, `applyEffect`, `snapshot` | Bootstrapped → Live → Frozen (checkpoint) → Restored | World never imports Policy or Goal packages |
| 2 | **Entity** | A distinct addressable "thing" in the world | Identity, own local state fields, relationships | Global state, other entities' data | `id`, `type`, `attrs`, `version` | Created→Active→Archived→Deleted(tombstone) | Entity ID is immutable once assigned |
| 3 | **State** | What is currently true | Current values, invariants, version | History, intent, beliefs | `get`, `commit(tx)`, `validate` | Init→Mutating(tx)→Committed→Snapshotted | Every commit is validated before becoming visible |
| 4 | **Event** | An immutable record that something happened | Payload, causality, timestamp, id | Interpretation/meaning (that's Evaluation's job) | `emit`, `subscribe`, `replay` | Emitted→Routed→Persisted→(Replayed) | Events are append-only; never mutated |
| 5 | **Observation** | Agent/subsystem-specific, possibly partial view of State | Projection function, visibility scope | Ground truth | `observe(entity, scope) → O_t` | Requested→Computed→Delivered | Observation ⊆ State, never > State |
| 6 | **Input** | External stimulus entering the system | Raw payload, source, arrival time | Validated semantics | `receive`, `normalize` | Received→Validated→Converted to Event | Input is untrusted until validated |
| 7 | **Goal** | Desired outcome, independent of how to get there | Target condition, deadline, priority, utility fn ref | Plan, execution mechanics | `isSatisfied(state)`, `utility(state)` | Declared→Active→Achieved/Abandoned/Expired | Goal is pure data + a pure evaluator function |
| 8 | **Policy** | Function selecting actions/plans | Decision function, its own parameters `Θ^π` | State, Capabilities' internals | `decide(Ŝ,G,M,Mem) → A|Plan` | Loaded→Deciding→Idle | Policy never mutates World directly |
| 9 | **Action** | A declared *intent* to invoke a Capability | Capability ref, params, intent id | Execution result | `{capability_id, params, issued_by}` | Proposed→Authorized→Dispatched→Resolved | Action is inert data until Runtime executes it |
| 10 | **Capability** | Universal unit of "something the system can cause to happen" | Contract: Input/Pre/Effect/Post/Permission/Cost | Scheduling, authorization decision | `validate`, `execute`, `rollback` | Registered→Discoverable→Invoked→Completed/RolledBack | Capability execution is the *only* path to a state mutation |
| 11 | **Model** | System's belief about world dynamics | `Θ^M`, `predict()` | Ground truth, Policy | `predict(Ŝ,A) → dist(Ŝ')` | Trained/Configured→Serving→Recalibrated | Model is explicitly versioned and never treated as ground truth |
| 12 | **Runtime** | Executes Actions under resource/time bounds | Scheduling, execution context, lifecycle | Decision-making, domain semantics | `submit(Action)`, `cancel`, `status` | See Section 9 | Runtime is domain-agnostic |
| 13 | **Resource** | Finite/constrained thing consumed by execution | Capacity, availability, cost | Business logic | `reserve`, `release`, `account` | Discovered→Reserved→Consumed→Reclaimed | Reservation never exceeds capacity |
| 14 | **Constraint** | A rule bounding what's allowed | Predicate, severity (hard/soft), scope | Enforcement mechanics (that's Runtime's job to call it) | `check(action, state) → allow|deny|penalty` | Registered→Active→(Versioned) | Hard constraints block; soft constraints only penalize the Objective |
| 15 | **Memory** | Retained internal record used *for future decisions* | Working/episodic/semantic/procedural stores | Ground truth, raw immutable log | `write`, `read`, `search`, `consolidate` | Section 13 | Memory is lossy/summarizable; History is not |
| 16 | **Evaluation** | Judges state/trajectory against Goal | Metrics, scorers, diagnosis | Remediation (that's Recovery's/Policy's job) | `evaluate(traj, G) → Score+Diagnosis` | Triggered→Scoring→Reported | Evaluation is read-only (a pure Capability) |
| 17 | **Feedback** | Routes Evaluation output back to Policy/Model update | Routing rules | Evaluation logic itself | `route(Score) → UpdateSignal` | Emitted→Delivered | Feedback never bypasses Update to touch state directly |
| 18 | **Scheduler** | Decides *when/where/in what order* Actions run | Queue, priority, placement policy | Whether the action is *allowed* (Constraint's job) | `enqueue`, `pick_next` | Section 9 | Scheduler never authorizes, only orders |
| 19 | **Executor** | Actually runs the Capability code | Execution context, sandbox, isolation | Scheduling policy | `run(Action) → Result` | Section 9 | Executor cannot exceed the Resource grant it was given |
| 20 | **Security/Permission** | Determines who/what may invoke which Capability | Identity, grants, capability tokens | Business rules (Domain Constraint's job) | `authorize(actor, capability) → grant|deny` | Section 17 | No ambient authority — every call is checked |
| 21 | **Persistence** | Durable storage substrate | Storage engine, durability guarantees | Business meaning of the data | `read`, `write`, `flush` | Section 6 | Committed data survives crash |
| 22 | **Recovery** | Restores system to a valid state after failure | Checkpoints, recovery plans | Root-cause business fixes | `detect`, `diagnose`, `recover`, `verify` | Section 16 | Recovery never silently swallows a Constraint violation |
| 23 | **Telemetry** | Makes every transition explainable | Logs, metrics, traces | Decision-making | `emit(span)`, `query` | Section 18 | Every Action/Event carries a trace id |

---

## 4. Layered Architecture (revised)

The prompt's L0–L10 stack is close but has one structural defect: it places **Governance/Security/Recovery** as a *top* layer (L10), implying it acts only after everything else. In practice a security or safety violation must be interceptable **before** a Capability executes, not after Policy has already decided. Putting governance "on top" is why so many agent frameworks bolt on safety as an afterthought.

**Fix: governance is a vertical spine, not a horizontal layer.** It has hook points at every layer boundary, especially just before L6 (Runtime execution).

```
                 ┌───────────────────────────────────────────┐
                 │   GOVERNANCE / SECURITY / RECOVERY /       │  ← cross-cutting
                 │   OBSERVABILITY  (hooks at every boundary) │     spine, not a layer
                 └───────────────────────────────────────────┘
L9  Evaluation / Feedback         (reads L2–L8, writes only to Update channel)
L8  Goal / Objective              (pure data + utility fns)
L7  Policy / Intelligence         (rules, planners, ML, LLM agents, controllers)
L6  Memory                        (working/episodic/semantic/procedural)
L5  Runtime / Execution           (scheduler, executor, lifecycle)
L4  Capability / Action           (the universal effect contract)
L3  Event / Observation           (routing, causality, replay)
L2  World / Domain Model          (entities, relationships, rules)
L1  State / Persistence           (StateStore, EventLog, SnapshotStore)
L0  Resource / Infrastructure     (CPU, RAM, GPU, network, capital, tokens...)
```

Note: **Memory is promoted to its own layer (L6)** — the original hierarchy buried it inside State, which caused the "everything is RAG" anti-pattern (Section 33). Memory is *derived from* State/Event but has distinct read/write/consolidation semantics and must be architecturally separable.

### Dependency rules

| From → To | Allowed? | Mode | Reason |
|---|---|---|---|
| L(n) → L(n−1) | ✅ Allowed | Sync or async | Standard downward composition |
| L(n) → L(n+1) | ❌ Forbidden (direct call) | — | Prevents upward coupling; use Events instead |
| L(n) → L(n+2..) via Event Bus | ✅ Allowed | Async only | Cross-layer notification without coupling |
| L7 Policy → L4 Capability directly | ❌ Forbidden | — | Must go through L5 Runtime, which enforces the Constraint checkpoint |
| L2 World → L7/L8 (Policy/Goal) | ❌ Forbidden | — | World must remain policy-agnostic so multiple policies/agents can share one world |
| L1 State → anything above L0 | ❌ Forbidden | — | State has zero outbound dependencies; it is pure data + invariants |
| Governance spine → any layer | ✅ Allowed (interception) | Sync, blocking | Must be able to veto before effect lands in State |
| L9 Evaluation → L1 State | ✅ Read-only | Sync | Evaluation reads trajectories, never writes state |

---

## 5. State ≠ Model ≠ Policy

This distinction is the second most-violated rule in real systems (after skipping the Constraint checkpoint). Mixing these three causes: agents that "reason" using stale beliefs as if they were fact (Model/State conflation), or systems whose "rules" quietly encode assumptions about how the world behaves (Policy/Model conflation).

| Domain | State (what's true now) | Model (believed dynamics) | Policy (what to do) |
|---|---|---|---|
| OS | Open file descriptors, process table, memory map | Scheduler's estimate of process burst time, page-fault predictor | CFS/round-robin scheduling algorithm |
| AgentOS | Conversation state, open tasks, tool results so far | LLM's world/task model, cost/latency predictor for tools | Which tool to call next, ReAct/planner logic |
| Quant | `BTC=105000, position=0.3, cash=10000` | Volatility model, liquidity model, risk model | "Reduce position by 10%" |
| Simulation | Positions/velocities of all bodies at tick t | Physics model (F=ma, collision model) | Controller / AI behavior tree |
| Game engine | Player HP, inventory, world flags | NPC's belief about player location (fog of war) | NPC behavior tree / player input mapping |
| Software factory | Repo HEAD, failing tests, open PRs | Estimate of "which files likely need changes" | Edit-then-test-then-fix loop strategy |

Formally: `State` is a value; `Model` is a function (with parameters) that predicts how values change; `Policy` is a function (with parameters) that chooses actions. A system can swap Models or Policies without touching State, and vice versa — that separability is the litmus test for whether the boundary is drawn correctly.

---

## 6. Universal World Model

```
World
 ├── Entities        (typed, versioned, addressable)
 ├── Relationships    (typed edges: contains, owns, adjacent-to, depends-on)
 ├── State            (per-entity + global fields, see Section 7)
 ├── Events           (append-only causal log, see Section 8)
 ├── Rules            (invariants + transition constraints)
 ├── Constraints       (hard/soft, see Section 15)
 ├── Resources        (see Section 14)
 ├── Time             (pluggable Clock, see Section 20)
 └── Environment      (exogenous, partially/fully unobservable inputs)
```

**How different system classes map onto one World:**

| System class | How it fits | Key mechanism |
|---|---|---|
| Discrete | Each Event = one State transition | StateReducer applies Events one at a time |
| Continuous | State fields are interpolated between Events using a Model | `predict()` supplies intermediate values; Events mark discontinuities |
| Event-driven | Native fit — World *is* an event-driven store | Direct |
| Real-time | Clock = WallClock; Scheduler enforces deadlines | Section 20 |
| Async | Executors run independently; World serializes commits via transactions | Section 21 |
| Deterministic | `F` and Capabilities declared `deterministic: true` | Enables exact replay |
| Stochastic | Capability declares `seed_required: true`; seed is captured in the Event | Reproducible despite randomness |
| Partially observable | `Observation = Obs(State)` is a strict projection; Policy only ever sees `Ŝ_t` | Section 2 |
| Distributed | World is sharded by Entity ID; StateReconciler merges cross-shard effects | Section 21/29 |

---

## 7. Universal State Architecture

```
Event ──▶ StateReducer(state, event) ──▶ proposed_state
                                              │
                                              ▼
                                     StateValidator (invariants)
                                              │  pass
                                              ▼
                              StateStore.commit(tx) ──▶ new canonical State
                                              │
                              ┌───────────────┼────────────────┐
                              ▼               ▼                ▼
                      EventLog.append   SnapshotStore      StateReconciler
                      (durability,      (periodic, for      (only in multi-writer
                       replay)           fast recovery)      / distributed mode)
```

| Component | Responsibility | Exists because |
|---|---|---|
| `StateStore` | Holds current canonical state; exposes transactions | Single source of truth |
| `SnapshotStore` | Immutable point-in-time copies | Fast recovery without full replay |
| `EventLog` | Append-only, ordered-per-entity record of all Events | Enables event sourcing, audit, replay, determinism |
| `StateReducer` | Pure function `(state, event) → state` | Deterministic reconstruction from log |
| `StateValidator` | Checks invariants before commit | Prevents corrupt state from ever becoming visible |
| `StateVersion` | Schema version + logical clock | Safe migrations, conflict detection |
| `StateReconciler` | Resolves concurrent conflicting writes (CRDT / LWW / custom merge) | Only needed once you have >1 writer; absent in single-writer systems |

Consistency posture: **strong consistency inside one StateStore transaction; eventual consistency only across StateStore boundaries** (see Section 21).

---

## 8. Universal Event Architecture

**Canonical event envelope:**

```json
{
  "id": "evt_9c1a...",
  "schema_version": "1.0",
  "type": "capability.executed | input.received | timer.fired | ...",
  "source": "capability:order.submit",
  "entity_id": "portfolio:acct_42",
  "timestamp": {"wall": "2026-09-08T10:00:00Z", "logical": 18422},
  "causation_id": "evt_9b02...",
  "correlation_id": "trace_77f1...",
  "idempotency_key": "order-submit-8891",
  "priority": "normal",
  "payload": { "...": "..." }
}
```

| Concern | Mechanism |
|---|---|
| Identity | UUID `id`, globally unique |
| Causality | `causation_id` (direct parent) + `correlation_id` (whole causal chain / trace) |
| Ordering | Total order **per `entity_id` partition only** — no global total order requirement (matches CAP-style tradeoffs; distributed systems can't afford global ordering) |
| Priority | `priority` field consumed by Scheduler, not by the Bus itself |
| Idempotency | `idempotency_key`; Executor deduplicates on retry |
| Replay | `EventLog.replay(from_offset)` feeds `StateReducer` |
| Persistence | Every event is appended to `EventLog` before being considered delivered |
| Routing/Filtering | Topic = `type` + `entity_id` prefix; subscribers filter by pattern |
| Correlation | `correlation_id` ties Observation → Decision → Action → Result → Evaluation into one causal trace (feeds Section 18) |

**Event categories** (all share the envelope above, differing only in `type` namespace): Input, System, Domain, Agent, Tool, Error, Timer, Resource, Security, Evaluation, Recovery.

**Event Bus / Loop:** single-writer-per-partition pub/sub; in low-resource mode this is an in-process ring buffer, in distributed mode a partitioned log (Kafka/NATS-JetStream-shaped). The **interface never changes** between these two deployments — only the backing implementation does (Section 28/29).

---

## 9. Universal Capability Architecture

```
Capability = (Input, Preconditions, Action, Postconditions, Permissions, Cost)
```

```json
{
  "id": "cap:order.submit",
  "version": "3.1",
  "input_schema": {"symbol": "string", "qty": "number", "side": "enum(buy,sell)"},
  "preconditions": ["market.is_open", "cash_available(qty*price)"],
  "postconditions": ["position.updated", "order.acknowledged"],
  "permissions_required": ["trading:submit_order"],
  "cost_model": {"type": "latency+fees", "estimate_fn": "estimate_cost"},
  "idempotent": false,
  "reversible": true,
  "rollback_ref": "cap:order.cancel"
}
```

Pipeline: **Registry → Discovery → Validation → Authorization → Execution → Monitoring → Result → (Rollback)**.

| Concept | As a Capability instance |
|---|---|
| Linux syscall | `Input`=registers, `Precond`=valid fd/permissions, `Post`=kernel state changed, `Permission`=uid/capabilities bitmask, `Cost`=cycles |
| Agent tool call | `Input`=JSON args, `Precond`=schema valid, `Post`=tool contract, `Permission`=scope grant, `Cost`=latency+$ |
| Python function | `Input`=args, `Precond`=type checks, `Post`=return contract, `Permission`=none/process-level, `Cost`=CPU time |
| REST API | `Input`=request body, `Precond`=auth token valid, `Post`=response schema, `Permission`=OAuth scope, `Cost`=latency+rate-limit budget |
| DB query | `Input`=query params, `Precond`=connection+ACL, `Post`=rows/commit, `Permission`=table grants, `Cost`=I/O+lock time |
| Trading order | `Input`=order ticket, `Precond`=risk limits, `Post`=fill/ack, `Permission`=trading mandate, `Cost`=fees+slippage+capital-at-risk |
| Robot actuator | `Input`=motor command, `Precond`=joint limits/safety zone clear, `Post`=new pose, `Permission`=safety-interlock token, `Cost`=energy+wear |
| Simulation action | `Input`=action vector, `Precond`=physically valid, `Post`=new sim state, `Permission`=n/a or multiplayer turn-token, `Cost`=compute budget |

**What's universal is the contract, not the substrate.** This directly answers Critical Question #7/#8 (Section 31): yes, a syscall and an LLM tool call share one abstraction, because both are fully described by (Input, Pre, Effect, Post, Permission, Cost) — the *executor* underneath differs (kernel mode vs. sandboxed process vs. network call), but that's a Runtime/Executor concern, not a Capability-contract concern.

---

## 10. Universal Runtime Architecture

```
Created → Queued → Scheduled → Running → Waiting → Suspended
   → Completed
   → Failed → Recovering → (Queued | Cancelled)
   → Cancelled
```

| Component | Responsibility |
|---|---|
| Scheduler | Orders queued Actions by priority/deadline/resource fit — never decides *if* allowed |
| Executor | Runs the Capability in an isolated context (process/container/sandbox/thread) |
| Worker pool | Bounded concurrency for CPU/GPU-bound Capabilities |
| Task queue | Durable, priority-aware, supports delay/deadline |
| Event loop | Cooperative concurrency for I/O-bound Capabilities |
| Concurrency model | Async event loop for I/O + worker pool for CPU-bound; isolation boundary set by Capability's declared trust level |
| Cancellation/timeout | Every `Execute` call carries a deadline; Executor enforces preemption |
| Retry | Only for `idempotent: true` Capabilities, with exponential backoff and a retry budget |
| Checkpoint | Runtime position + in-flight Action list persisted alongside State snapshots |
| Backpressure | Queue depth thresholds throttle admission, not silently drop |

---

## 11. Universal Policy Engine

```
Reactive:      π: Observation × Memory × Goal            → Action
Deliberative:  π: State × Goal × Constraints × Model      → Plan (sequence of Actions)
```

Plans are **advisory, not committed**: the Runtime re-observes and re-checks Constraints between each step of a Plan (replanning loop), so a Plan is never blindly executed end-to-end — this is what lets the same Runtime safely host both a PID controller and an LLM agent.

| Concept | Definition | Relationship to Policy interface |
|---|---|---|
| Rule | Static deterministic `Observation → Action` lookup | Simplest possible Policy |
| Policy | General decision function, may be learned or hand-written | The interface itself |
| Planner | Uses a Model + search to produce a multi-step Plan | A Policy whose output type is `Plan` |
| Optimizer | Solves `argmax Objective` over a parameter/action space | A Policy specialized for continuous/combinatorial domains |
| Controller | Closed-loop, continuous-feedback policy (e.g. PID) | A Policy with very high decision frequency and a simple Model |
| Agent | `{Policy, Memory, Goal, Capability-scope, Identity}` bound together | **Not a new primitive** — a named configuration of existing ones (answers Q6) |

All of the above implement one interface: `decide(observation, context) → Action | Plan`, which is why they can share one Runtime.

---

## 12. Goal / Objective System

```
Objective(state) = Utility(state) − Cost(state) − Risk(state) − ConstraintViolation(state)
```

- **Hierarchical goals**: a goal tree; a parent goal's `isSatisfied` may be a boolean AND/OR/weighted combination of children.
- **Multi-objective**: either weighted scalarization (fast, but requires weight tuning) or Pareto-frontier tracking (slower, preserves trade-off information) — both are pluggable strategies behind one `combine(objectives) → scalar_or_frontier` interface.
- **Temporal goals/deadlines**: `deadline` field + a decay function applied to `Utility` as deadline approaches.
- Domain-specific utility/cost/risk functions are registered per Domain Adapter (Section 23) as pure functions `(state, trajectory) → number` — the core Goal engine never hardcodes what "good" means.

---

## 13. Evaluation and Feedback Architecture

```
Observation → Metric → Evaluator → Score → Diagnosis → Feedback → Policy/Model Update
```

Evaluation is implemented as a **read-only Capability** (no side effects, no rollback needed) — this is deliberate: it lets Evaluation reuse the exact same Registry/Discovery/Authorization/Monitoring machinery as every other Capability instead of being a bespoke subsystem.

| Use case | What gets evaluated | Feedback destination |
|---|---|---|
| Coding-agent test/repair loop | Test pass/fail, diff quality | Policy (choose next edit) |
| Quant risk control | VaR, drawdown, exposure | Constraint engine (may hard-block new orders) + Policy |
| Simulation calibration | Divergence between sim and real-world trace | Model parameters `Θ^M` |
| OS monitoring | Latency/utilization SLOs | Scheduler priorities |
| Autonomous agents | Task completion, safety violations | Policy + Memory (episodic write) |
| Software-factory acceptance | CI pass rate, coverage delta | Deployment gate (hard Constraint) |

---

## 14. Memory Architecture

**State vs Memory vs Knowledge vs History vs Artifact — these are not synonyms:**

| Concept | Definition | Mutable? | Lossy? | Lifetime |
|---|---|---|---|---|
| State | Ground truth right now | Yes (via transactions) | No | Current |
| Memory | System's retained record used to decide | Yes (consolidated/decayed) | Yes (can summarize) | Task→cross-task |
| Knowledge | Validated, generalized, reusable facts/procedures | Rarely (curated) | No (validated) | Long-term |
| History | Raw immutable event record | No, append-only | No | Forever (subject to retention policy) |
| Artifact | A produced deliverable tied to a task (code, report, trade blotter) | Versioned, not overwritten | No | Long-term, explicitly retained |

**Memory subtypes:** Working Memory (task-scoped, cleared at task end) · Short-Term State (recent trajectory window feeding Policy) · Long-Term Memory, split into **Semantic** (facts), **Procedural** (how-to), **Episodic** (what-happened-when) · plus **Artifact Memory** (pointers to produced deliverables).

**Interfaces:** `MemoryRead`, `MemoryWrite`, `MemorySearch` (semantic/keyword/hybrid), `MemoryUpdate`, `MemoryConsolidation` (merge+compress old entries into higher-level summaries), `MemoryExpiration` (TTL/decay policy per subtype), `MemoryVersioning`.

---

## 15. Resource Management

```
Resource = (Capacity, Availability, Cost, Constraint)
```

CPU, RAM, GPU, Disk, Network, LLM tokens/API calls, wall-clock time, capital, energy, tool/agent seats, and software licenses are all modeled identically as `Resource` instances — the only thing that varies is the unit and the cost function.

| Operation | Responsibility |
|---|---|
| Discovery | Enumerate available resources and current headroom |
| Allocation | Bind a resource unit to a running Execution |
| Reservation | Pre-commit capacity before execution starts (prevents oversubscription) |
| Accounting | Track actual consumption vs. reserved/estimated |
| Quota | Per-actor/per-domain caps, enforced at Authorization time |
| Scheduling | Resource-aware placement (feeds Scheduler in Section 10) |
| Reclamation | Return unused/expired reservations to the pool |

---

## 16. Constraint and Governance System

| Type | Behavior on violation | Example |
|---|---|---|
| Hard Constraint | **Block** the Action before execution | Risk limit breach, missing permission |
| Soft Constraint | Allow, but penalize `Objective` | Style preference, non-critical SLA |
| Policy Constraint | Org-defined rule, usually hard | "No trades after 4pm" |
| Resource Constraint | Block if quota exceeded | Token budget exhausted |
| Safety Constraint | Block, highest precedence, cannot be overridden by Policy | Actuator torque limit, self-harm content filter |
| Domain Constraint | Business rule specific to one Domain Adapter | "Orders must be round lots" |

**Interaction with planners/executors:** the `ConstraintEngine.check(action, state)` call is a **mandatory synchronous checkpoint** sitting between L7 (Policy output) and L5 (Runtime execution) — this is the concrete implementation of the "governance spine" from Section 4. A Planner may *propose* a Plan that would violate a constraint; the checkpoint catches it at each step, forcing a replan rather than trusting the Policy to have self-checked.

---

## 17. Fault Tolerance and Recovery

```
Failure → Detection → Diagnosis → Recovery → Verification
```

| Component | Role |
|---|---|
| Health Monitor | Heartbeats / liveness probes |
| Failure Detector | Timeout + anomaly detection over Telemetry |
| Checkpoint | Periodic durable snapshot of State + Runtime position |
| Snapshot | On-demand immutable State copy |
| Retry | Bounded, backoff, only for idempotent Capabilities |
| Rollback | Restore last valid checkpoint, or invoke `rollback_ref` compensating Capability |
| Replay | Reconstruct state from EventLog since last checkpoint |
| Recovery Planner | Chooses strategy per failure class (retry vs rollback vs failover vs degrade) |
| Failover | Switch to a redundant Executor/replica |
| Degraded Mode | Reduced Capability set + conservative fallback Policy |
| Circuit Breaker | Stop invoking a Capability after repeated failures, until cooldown |

Recovery is itself run through the same Evaluator used elsewhere: **Verification = re-running Evaluation against the post-recovery State to confirm invariants hold** — recovery is not "done" until Evaluation says so.

---

## 18. Security Architecture

Security is **capability-based, not purely identity-based**: possessing a capability token is both necessary and sufficient to invoke that Capability — there is no ambient authority. This matters specifically for LLM-driven policies, which must never be trusted to self-limit; the checkpoint lives in the Runtime/Authorization layer, not in the prompt.

```
Identity → Authentication → Authorization (issues scoped Capability tokens)
                                   │
                                   ▼
                    Capability Security (token checked at every invocation)
                                   │
                    Sandbox / Isolation (per trust level)
                                   │
              Trust Boundaries: Network | Filesystem | Resource
                                   │
                          Secrets (never in State/Memory in plaintext)
                                   │
                          Audit (every check + decision logged to Telemetry)
```

---

## 19. Observability — the Causal Trace Model

```json
{
  "trace_id": "trace_77f1",
  "span_id": "span_0004",
  "parent_span_id": "span_0003",
  "actor": "policy:llm_agent_v2",
  "timestamp": "2026-09-08T10:00:00.412Z",
  "state_before_ref": "snap_88a1#v204",
  "action": {"capability_id": "cap:order.submit", "params": {"...":"..."}},
  "state_after_ref": "snap_88a1#v205",
  "result": {"success": true, "cost_actual": {"fees": 1.2}},
  "caused_event_ids": ["evt_9c1a"]
}
```

This single schema answers all eight required questions (what/why/who/before-state/action/change/result/what-it-caused-next) by construction — every Action, Event, Evaluation, and Recovery step emits one of these spans, and spans chain via `parent_span_id`/`caused_event_ids` into a full causal DAG per `trace_id`.

---

## 20. Determinism and Reproducibility

| Mechanism | How |
|---|---|
| Seed control | Stochastic Capabilities declare `seed_required: true`; the sampled seed is written into the Event, not just used in-memory |
| Event replay | `EventLog.replay()` + `StateReducer` reconstructs any past state exactly |
| State snapshots | Anchor points to avoid full replay from genesis |
| Time virtualization | `VirtualClock` decouples logical progress from wall-clock (Section 21) |
| Dependency/model/policy versioning | `Θ^M`, `Θ^π`, and library versions are all recorded in the Trace, not assumed |
| Environment capture | Container/image digest recorded per Execution |

**Handling true nondeterminism** (real markets, real sensors, other humans): UCSA does not attempt to *re-derive* the external world. Instead, every external response is captured as an **Input Event** and logged. Replay reproduces the system's **decisions** given the recorded inputs — it does not, and cannot, reproduce the physical world itself. This is the correct and honest answer to Critical Question #11.

---

## 21. Time Architecture

```
Clock interface: now() | schedule(delay, cb) | advance(Δ)  [Virtual only]
```

| Clock type | Used by | Behavior |
|---|---|---|
| WallClock | Real-time AgentOS, production trading | `now()` = OS time; deadlines are real |
| VirtualClock | Simulation, backtesting | `now()` advances on event processing, can run faster/slower than real time, fully deterministic |
| LogicalClock | Distributed event processing | Lamport/vector clocks; establishes causal order independent of clock skew |
| Fixed-timestep clock | Game loop | VirtualClock synced to a render tick, decoupled from simulation tick rate |

Because every component (World, Scheduler, Timers) is written against the `Clock` interface and never calls `Date.now()`/`time.time()` directly, **one Runtime binary can serve real-time AgentOS, backtesting, and a game loop simply by swapping the injected Clock implementation** — no core code changes.

---

## 22. Transaction and Consistency Model

| Mechanism | Lives in | Notes |
|---|---|---|
| Atomicity, Isolation, Consistency, Durability | **Core** (`StateStore` transaction boundary) | Guaranteed within one StateStore only |
| Idempotency | **Core** (Capability contract + idempotency key) | Required for safe retries |
| Sagas / Compensation | **Domain Adapter** | Needed only when an operation spans multiple independently-owned StateStores |
| Eventual consistency / StateReconciler | **Core primitive, Domain-configured policy** | Core provides the merge hook; domain decides the merge strategy (CRDT, LWW, custom) |
| Optimistic concurrency | **Core** default | Version-checked commits; cheap, works for low-contention entities |
| Pessimistic concurrency | **Domain opt-in** | For high-contention entities (e.g. a single trading account under heavy concurrent load) |

Rule of thumb: **the core runtime guarantees correctness within a boundary; only the domain knows how to reconcile across boundaries.**

---

## 23. Plugin / Extension Architecture

```
Core Runtime  (never imports domain code)
     ↓  implements
Domain Adapter   { registerEntities(), registerCapabilities(),
                    registerObjective(), registerPolicies(), bootstrapWorld() }
     ↓
Domain Model      (World schema specific to this domain)
     ↓
Domain Capabilities
     ↓
Domain Policies
```

Dependency inversion is strict: **Domain Adapters depend on Core's published interfaces; Core never depends on any Domain Adapter.** A new adapter (OS/AgentOS/Quant/Sim/Game/Robot/Software-Factory) is added by implementing the `DomainAdapter` interface — zero diffs to `/core`.

---

## 24. Domain Mappings

| Universal | OS | AgentOS | Quant | Simulation | Game Engine | Software Factory |
|---|---|---|---|---|---|---|
| Entity | Process, File | Agent, Task | Asset, Position | Physical body | Player, NPC | Repo, PR, file |
| State | Memory map, fd table | Conversation/task state | Portfolio, cash, price | Physics state | HP, inventory, world flags | Repo HEAD, test results |
| Event | Interrupt, syscall return | Tool result, message | Fill, price tick | Collision, tick | Input event, damage event | Commit, CI result |
| Capability | Syscall | Tool / Skill | Order, hedge | Physics action | Move, attack | Edit, run test, deploy |
| Policy | Scheduler algorithm | Planner / LLM agent loop | Strategy | Controller / AI behavior | Behavior tree / input map | Fix-then-test loop |
| Goal | Fairness/throughput SLO | Task completion | Sharpe/PnL target | Scenario objective | Win condition | All tests green |
| Runtime | Kernel | Agent runtime | Execution engine (OMS) | Physics/tick engine | Game loop | CI/CD pipeline |
| Constraint | Permission bits, quotas | Tool scope, budget | Risk limits | Physical laws | Game rules | Branch protection, review gate |
| Memory | Page cache | Conversation memory | Trade history/model state | Sim replay buffer | Save state | Codebase knowledge, past PRs |
| Evaluation | Perf counters | Task success eval | PnL/risk metrics | Sim-vs-real divergence | Score/objective check | Test/coverage results |

---

## 25. Implementation Architecture

```
/apps            entry points per deployment target (cli, server, sim-runner)
/core            the 6 kernel primitives ONLY — State, Event, Capability,
                 Runtime, Constraint, Clock. No domain code, ever.
/state           StateStore, SnapshotStore, EventLog, Reducer, Validator, Reconciler
/events          Event bus, schemas, routing
/capabilities    Capability registry, discovery, validation, execution wrapper
/runtime         Scheduler, Executor, worker pool, task queue
/policy          Policy interface + reference implementations (rule/planner/RL/LLM)
/goals           Goal tree, objective composition
/memory          Working/episodic/semantic/procedural stores
/evaluation      Metrics, evaluators, diagnosis
/resources       ResourceManager, quotas, accounting
/security        Identity, auth, capability tokens, sandboxing
/recovery        Health monitor, failure detector, recovery planner, circuit breaker
/observability   Trace model, logs, metrics exporters
/plugins         DomainAdapter interface + adapter loader
/domains         os/, agentos/, quant/, simulation/, game/, robotics/, software-factory/
/storage         Pluggable backends: sqlite, postgres, kafka, s3, in-memory
/network         Transport adapters (HTTP, gRPC, message bus)
/api             Public API surface (REST/gRPC/SDK)
/cli             Operator tooling
```

| Module | Responsibility | Depends on | Key data structures | Concurrency | Failure modes | Test strategy |
|---|---|---|---|---|---|---|
| `/state` | Canonical truth + durability | `/storage` | State, Snapshot, LogEntry | Transactional, single-writer per entity | Corrupt write, version conflict | Property-based invariant tests, replay-equivalence tests |
| `/events` | Causal, ordered delivery | `/state` (append), `/network` | Event envelope | Async pub/sub, per-partition order | Duplicate delivery, out-of-order across entities | Fuzz ordering, idempotency tests |
| `/capabilities` | Universal effect contract | `/state`, `/security`, `/resources` | Capability spec, Result envelope | Sync per-call | Precondition false positive, silent side effect | Contract tests per Capability (pre/post assertions) |
| `/runtime` | Turns Actions into effects, under bounds | `/capabilities`, `/resources`, `/security` | Task, Execution, Queue | Event loop + worker pool | Deadlock, starvation, resource leak | Chaos tests (kill workers mid-execution) |
| `/policy` | Decision-making | `/state` (read), `/goals`, `/memory` | Observation, Action/Plan | Stateless per-call (state passed in) | Infinite planning loop, hallucinated Action | Simulated-environment regression tests |
| `/goals` | Objective definition | none (pure data+fns) | Goal tree, Objective fn | N/A (pure functions) | Ill-defined utility causing reward hacking | Adversarial objective tests |
| `/memory` | Retained decision context | `/state`, `/events` | Memory records per subtype | Async write, sync read | Unbounded growth, stale recall | TTL/consolidation correctness tests |
| `/evaluation` | Scoring & diagnosis | `/state`, `/goals` | Score, Diagnosis | Read-only Capability | False-positive pass | Golden-trace regression suite |
| `/resources` | Capacity accounting | `/runtime` | Resource ledger | Locked accounting ops | Oversubscription | Load tests at capacity boundary |
| `/security` | Access control | `/state` (identity) | Token, Grant | Sync, on critical path | Privilege escalation | Adversarial authz fuzzing |
| `/recovery` | Failure handling | `/state`, `/observability` | Checkpoint, RecoveryPlan | Async monitor + sync recovery ops | Recovery loop (repeated failure) | Injected-fault test matrix |
| `/observability` | Explainability | all modules (read-only hooks) | Trace span | Async emit | Trace gaps under load | Trace-completeness assertions |
| `/plugins` | Domain isolation | `/core` interfaces only | DomainAdapter | Load-time | Adapter violates core invariant | Adapter conformance test suite |

---

## 26. Interface Definitions (language-neutral, then TypeScript)

**Language-neutral:**
```
World        { getEntity(id), applyEffect(capability, params), snapshot() }
StateStore   { get(key), commit(tx), validate(state) }
EventBus     { emit(event), subscribe(pattern, handler), replay(from) }
Capability   { validate(input), execute(input, ctx), rollback(ctx) }
Executor     { run(action, budget, deadline) -> Result }
Scheduler    { enqueue(action), pickNext() }
Policy       { decide(observation, goal, model, memory) -> Action | Plan }
Goal         { isSatisfied(state) -> bool, utility(state) -> number }
Evaluator    { evaluate(trajectory, goal) -> Score, Diagnosis }
Memory       { read(query), write(record), search(query), consolidate() }
ResourceManager { reserve(spec), release(handle), account(usage) }
ConstraintEngine { check(action, state) -> Allow | Deny | Penalty }
RecoveryManager  { detect(), diagnose(failure), recover(plan), verify() }
Telemetry    { emitSpan(span), query(traceId) }
```

**TypeScript reference (interfaces only, no giant implementation):**

```ts
interface StateStore<S> {
  get(key: string): Promise<S | undefined>;
  commit(tx: (draft: S) => S): Promise<{ version: number; state: S }>;
  validate(state: S): { valid: boolean; violations: string[] };
}

interface Capability<I, O> {
  id: string;
  version: string;
  validate(input: I): { valid: boolean; errors?: string[] };
  execute(input: I, ctx: ExecutionContext): Promise<CapabilityResult<O>>;
  rollback?(ctx: ExecutionContext): Promise<void>;
}

interface CapabilityResult<O> {
  success: boolean;
  output?: O;
  costActual: Record<string, number>;
  traceId: string;
}

interface Policy<Obs, Goal, Mdl, Mem, Act> {
  decide(observation: Obs, goal: Goal, model: Mdl, memory: Mem): Promise<Act | Act[]>;
}

interface ConstraintEngine {
  check(action: ActionIntent, state: unknown): "allow" | "deny" | { penalty: number };
}

interface EventBus {
  emit(event: UCSAEvent): Promise<void>;
  subscribe(pattern: string, handler: (e: UCSAEvent) => void): Subscription;
  replay(fromOffset: string, entityId?: string): AsyncIterable<UCSAEvent>;
}

interface RecoveryManager {
  detect(): Promise<FailureSignal[]>;
  diagnose(signal: FailureSignal): Promise<Diagnosis>;
  recover(diagnosis: Diagnosis): Promise<RecoveryPlan>;
  verify(plan: RecoveryPlan): Promise<{ recovered: boolean }>;
}
```

---

## 27. Data Schemas (JSON, versioned & replayable)

<details><summary>Expand for all 16 canonical schemas</summary>

```json
// SystemState
{ "version": "1.0", "entity_states": {"portfolio:acct_42": {"cash": 10000, "position": 0.3}},
  "state_version": 205, "logical_time": 18422 }

// Entity
{ "id": "portfolio:acct_42", "type": "Portfolio", "attrs": {"cash": 10000}, "version": 12 }

// Event  -- see Section 8 for full example

// Action
{ "id": "act_001", "capability_id": "cap:order.submit", "params": {"symbol":"BTC","qty":0.03},
  "issued_by": "policy:llm_agent_v2", "status": "proposed" }

// Capability -- see Section 9 for full example

// Task
{ "id": "task_7", "goal_id": "goal_close_ticket_42", "status": "running",
  "created_at": "...", "assigned_policy": "policy:coding_agent" }

// Goal
{ "id": "goal_close_ticket_42", "target": "all_tests_pass AND pr_merged",
  "deadline": "2026-09-09T00:00:00Z", "priority": 1, "utility_fn": "software.completion_utility" }

// Policy
{ "id": "policy:llm_agent_v2", "type": "llm_react", "params_version": "v2.3",
  "capability_scope": ["cap:order.submit","cap:order.cancel"] }

// Execution
{ "id": "exec_331", "action_id": "act_001", "state": "Running", "started_at": "...",
  "deadline": "...", "resource_grant": {"cpu_ms": 500} }

// Resource
{ "id": "res:llm_tokens", "capacity": 1000000, "available": 812300, "cost_per_unit": 0.00001 }

// Constraint
{ "id": "cst:risk_limit", "type": "hard", "scope": "trading", "predicate": "exposure < max_exposure" }

// Evaluation
{ "id": "eval_88", "trace_id": "trace_77f1", "score": 0.92, "diagnosis": "goal_partially_met",
  "metric": "task_completion" }

// Failure
{ "id": "fail_14", "detected_at": "...", "class": "capability_timeout",
  "capability_id": "cap:order.submit", "trace_id": "trace_77f1" }

// Recovery
{ "id": "rec_9", "failure_id": "fail_14", "strategy": "retry_with_backoff",
  "outcome": "recovered", "verified_at": "..." }

// Trace -- see Section 19 for full example

// Artifact
{ "id": "art_55", "task_id": "task_7", "type": "code_diff", "uri": "s3://.../diff_55.patch",
  "version": 1, "produced_by": "policy:coding_agent" }
```
</details>

---

## 28. Lifecycle Diagrams

**System boot:**
```
Boot → LoadConfig → InitResources → LoadWorld → RestoreState (from Snapshot+EventLog)
     → RegisterCapabilities → StartEventLoop → [Observe→Believe→Decide→Authorize→Execute
       →Log→Evaluate→Update]* → Persist(periodic checkpoint) → Recover(if needed) → Shutdown
```

**Task lifecycle:** `Created → Assigned(Policy) → Running → {Blocked ↔ Running} → Completed | Failed | Abandoned`

**Agent lifecycle:** `Instantiated(Policy+Memory+Goal+Scope) → Active → Suspended ↔ Active → Retired`

**Capability lifecycle:** `Registered → Discoverable → Validated → Authorized → Executing → Completed | RolledBack`

**State lifecycle:** `Initialized → Mutating(tx) → Committed → Snapshotted → (Replayed on recovery)`

**Event lifecycle:** `Emitted → Persisted(EventLog) → Routed → Delivered → (Replayed)`

**Failure lifecycle:** `Occurred → Detected → Diagnosed → RecoveryPlanChosen → Executed → Verified → Closed`

---

## 29. Low-Resource Deployment Architecture

- Single process; embedded `StateStore` (SQLite/RocksDB) instead of a distributed DB.
- In-process ring-buffer `EventBus` instead of a message broker.
- `SnapshotStore` interval widened; incremental (diff-based) checkpoints instead of full snapshots.
- Bounded worker pool sized to available cores; CPU-only inference fallback Model registered per Capability (`degraded_model_ref`).
- LLM/API-bound Capabilities: response caching + smaller local-model fallback behind the same Capability interface (Policy code doesn't change).
- Lazy-load Domain Adapters and Memory indexes; batch Evaluation runs instead of per-step.
- Backpressure applied aggressively — admission control over the Task queue rather than unbounded buffering.

---

## 30. Distributed Deployment / Scaling Architecture

```
Single Process → Multi Process (shared StateStore, e.g. Postgres/Redis)
              → Multi Machine (EventBus becomes Kafka/NATS; Scheduler becomes cluster-aware)
              → Distributed Cluster (StateStore sharded by entity_id; StateReconciler active)
              → Cloud (multi-region; Domain Adapters can run on independent clusters)
```

| Component | Stateless (scales horizontally) | Stateful (needs partitioning/replication) |
|---|---|---|
| Executor / worker pool | ✅ | |
| Policy evaluation | ✅ | |
| Evaluator (pure fn) | ✅ | |
| StateStore | | ✅ (shard by entity_id) |
| EventLog | | ✅ (partition by entity_id) |
| SnapshotStore | | ✅ (replicated) |
| Memory store | | ✅ (replicated / vector-index sharded) |
| Resource ledger | | ✅ (needs coordinated accounting) |

The **interface never changes** across this scaling path — only backing implementations swap, per Sections 8 and 29. This is the practical payoff of the layering discipline in Section 4.

---

## 31. Testing and Acceptance Architecture

| Category | Measurable metric(s) |
|---|---|
| Correctness | Invariant-violation rate = 0 across property-based test suite; contract-test pass rate per Capability |
| Reliability | Uptime %, MTBF |
| Fault recovery | Recovery time (P50/P95), failure-recovery success rate (%), verified-recovery rate (%) |
| Performance | P50/P95/P99 latency per Capability class; throughput (actions/sec) |
| Resource efficiency | Memory footprint (MB) per active Task; CPU utilization (%); resource cost per completed Task |
| Security | # of unauthorized-capability-invocation attempts blocked / total attempted (should be 100%) |
| Determinism | Replay-hash match rate across N replays of the same EventLog (target: 100% for deterministic Capabilities) |
| Reproducibility | Identical `Trace` DAG shape given identical Event input (target: 100%) |
| Extensibility | # of core-module diffs required to add a new Domain Adapter (target: 0) |
| Observability | Trace-completeness rate: % of Actions with a fully linked causal span (target: 100%) |
| Maintainability | Cyclomatic complexity per module; dependency-direction violations (target: 0, enforced by lint rule from Section 4's table) |
| Scalability | Throughput vs. node-count curve; checkpoint interval vs. recovery-time tradeoff curve |

---

## 32. Critical Architectural Questions — Answered

1. **Is "State Machine" sufficient to describe all systems?** No — it describes *State*, but conflates Model and Policy into `F`/`π` without separating belief-state from ground truth. UCSA's Section 2 model fixes this.
2. **Is "World Model" necessary?** Yes, as a *container/schema convention* over Entities+State+Rules — not as a new mechanism. It's the "shape" State takes on, not a 7th primitive.
3. **Should Memory be part of State?** No. State is ground truth; Memory is a specialized, lossy, decision-oriented derivative of State+Events. Merging them causes stale beliefs to be treated as fact.
4. **Should Event be part of State?** No. Event is the *cause*; State is the *effect*. They must stay separate for event sourcing and replay to work.
5. **Should Policy be separated from Runtime?** Yes, strictly — Runtime executes; Policy decides. Conflating them is what makes systems unauditable and unsafe (no checkpoint between decision and effect).
6. **Is Agent a Policy, Actor, Process, or composite?** Composite: `{Policy, Memory, Goal, Capability-scope, Identity}`. Treating Agent as a primitive causes God-object anti-patterns (Section 33).
7. **Is Capability the correct abstraction for syscall/tool/API/action?** Yes — all reduce to (Input, Pre, Effect, Post, Permission, Cost); see Section 9.
8. **Can OS syscall and LLM tool share one abstraction?** Yes, at the *contract* level; they differ only in Executor/trust-boundary implementation, which is exactly where the abstraction is supposed to allow variation.
9. **How do continuous-time systems map to discrete events?** Via a Model (`predict()`) that interpolates between discrete Events; the World stores discrete anchor points, not continuous streams.
10. **How do distributed systems map to the model?** Shard World by entity_id; use StateReconciler for cross-shard conflicts; use LogicalClock for causal ordering instead of assuming global order.
11. **How should nondeterminism be represented?** As logged Input Events (captured, not re-derived); replay reproduces decisions, not physical reality (Section 20).
12. **Where should domain-specific logic live?** Entirely inside Domain Adapters (Section 23) — never in `/core`.
13. **What belongs in the kernel/core?** The six primitives from Section 34 only.
14. **What belongs in plugins?** World schemas, Capabilities, Policies, Objective functions — everything domain-flavored.
15. **What must never cross architectural boundaries?** (a) Policy calling Capability directly, bypassing the Constraint checkpoint; (b) Domain code inside `/core`; (c) ground-truth State mutation from anywhere except a Capability execution; (d) unauthenticated/unauthorized Capability invocation.

---

## 33. Architectural Anti-Patterns

1. **God-Agent object** — folding Policy+Memory+Goal+Identity+Execution into one undifferentiated class; breaks testability and security auditing.
2. **"Everything is RAG"** — treating Memory, Knowledge, History, and State as one undifferentiated vector store; loses the ability to reason about what's *currently true* vs. *once observed*.
3. **Trusting the Policy to self-limit** — putting safety instructions in a prompt/rule instead of enforcing them at the Constraint checkpoint before execution.
4. **Policy calling Capability directly** — skips the mandatory authorization/constraint checkpoint; the single most dangerous layering violation for agentic systems.
5. **Mutating State outside a transaction** — breaks invariant checking, snapshotting, and replay simultaneously.
6. **No idempotency keys** — retries under failure silently duplicate side effects (double-submitted orders, duplicate actuator moves).
7. **Ambient wall-clock calls scattered through code** — makes simulation/backtesting/replay impossible without a full rewrite.
8. **Single global StateStore lock "for simplicity"** — works until scale, then requires a rewrite instead of a config change; violates the sharding assumption baked into Section 30.
9. **Conflating Event with State** — makes event sourcing and audit trails structurally impossible to retrofit later.
10. **Evaluation with side effects** — an Evaluator that also "fixes" what it finds hides failures from the Recovery/Observability pipeline.

---

## 34. The Kernel — Minimum Computational Substrate

> *What is the minimum substrate required to construct an OS, AgentOS, simulator, quant system, game engine, and software factory?*

**Six mechanisms, and nothing else:**

1. **State** — a transactional, versioned, invariant-checked store of what's currently true.
2. **Event** — an immutable, causally-ordered record of what happened, sufficient to reconstruct State.
3. **Capability** — the single universal contract (Input/Pre/Effect/Post/Permission/Cost) through which State can ever change.
4. **Scheduler/Executor** — turns queued intents into bounded, isolated, resource-governed executions of Capabilities, with a well-defined lifecycle.
5. **Constraint Checkpoint** — a mandatory, synchronous gate between "something wants to happen" and "it is allowed to happen."
6. **Clock** — a pluggable abstraction for time, so the same mechanisms serve real-time, virtual, and logical-time systems without modification.

Everything the prompt asks about — **World** (a schema convention over State+Entities), **Goal** (pure data + a utility function, no mechanism of its own), **Policy** (a pluggable decision *function* invoked at a well-defined hook point — the kernel guarantees the hook exists and is observable, but implements no intelligence itself), **Memory** (a specialized, lossy view derived from State+Event), **Evaluation** (a read-only Capability), and **Agent** (a named bundle of Policy+Memory+Goal+Identity) — is a **disciplined composition of these six mechanisms**, not an additional mechanism.

This is why one Runtime, unmodified at the core, can host a Linux-like scheduler, an LLM ReAct agent, a backtesting engine, a physics simulation, and a CI/CD software factory: each is simply a different **Domain Adapter** registering different Entities, Capabilities, Policies, and Objective functions against the same six primitives.

---

## Final Architecture Diagram

```
                ┌─────────────────────────────────────────────┐
                │     GOVERNANCE / SECURITY / RECOVERY /       │
                │     OBSERVABILITY  — cross-cutting spine     │
                │  (hooks at every arrow below, not a layer)   │
                └───────────────────────────────────────────────┘
                               ▲                    │ veto/allow
                               │                    ▼
   ┌───────────┐        ┌────────────┐       ┌──────────────┐       ┌───────────────┐
   │   GOAL    │───────▶│   POLICY   │──────▶│  CONSTRAINT   │──────▶│ CAPABILITY /   │
   │ (data+fn) │        │ (planner)  │       │  CHECKPOINT   │       │    ACTION      │
   └───────────┘        └────────────┘       └──────────────┘       └───────┬───────┘
        ▲                                                                    │
        │                                                                    ▼
   ┌───────────┐                                                    ┌───────────────┐
   │ EVALUATION │◀───────────────────────────────────────────────── │   RUNTIME /    │
   │ /FEEDBACK  │           trajectory + trace                      │   EXECUTOR     │
   └─────┬─────┘                                                    └───────┬───────┘
         │  updates Θ^M, Θ^π only                                          │ effect
         ▼                                                                  ▼
   ┌───────────┐          reads (belief)          ┌──────────────┐ ┌───────────────┐
   │  MEMORY    │◀──────────────────────────────── │ OBSERVATION  │◀│ WORLD / STATE  │
   │(derived)   │                                   │  (Ŝ_t proj.) │ │ (ground truth) │
   └───────────┘                                   └──────────────┘ └───────────────┘
                                    ▲                                        │
                                    └────────────── EVENT LOG ◀──────────────┘
                                              (append-only, causal, replayable)
                                                          │
                                                     CLOSED LOOP
```

---

## 35. Evolution Roadmap

| Phase | Scope |
|---|---|
| v0.1 | Single-process reference implementation of the 6 kernel primitives + one Domain Adapter (AgentOS), in-memory StateStore |
| v0.2 | Add Quant and Simulation adapters to validate generality claims against Section 24; add SnapshotStore + basic Recovery |
| v0.3 | Event sourcing hardened (full EventLog + Reducer + replay); Determinism test suite (Section 31) passing |
| v0.4 | Distributed scaling: sharded StateStore, StateReconciler, Kafka-shaped EventBus |
| v0.5 | Security hardening: capability-token model, sandboxed Executors, audit trail completeness |
| v1.0 | Multi-domain production release with OS, AgentOS, Quant, Simulation, Game, and Software-Factory adapters; plugin ecosystem + conformance test suite for third-party Domain Adapters |

---

*This document intentionally trades exhaustive prose for structural precision: every table row, schema, and interface is meant to be directly implementable rather than descriptive.*
