# AgentOS: A Coding Agent Operating System

*A systems architecture specification for a production-grade, LLM-driven operating system for autonomous software engineering agents.*

---

## A. Executive Summary

AgentOS is not a prompt-orchestration framework. It is an operating system whose "processes" are LLM-driven agents, whose "memory hierarchy" is a managed context engine, whose "syscalls" are tools, and whose "compiler/debugger" is an independent verification engine that never trusts a model's self-report of success.

The central architectural problem AgentOS solves is this: **LLM reasoning is probabilistic, but software correctness is not.** Every subsystem in this design exists to wrap non-deterministic reasoning inside deterministic, observable, recoverable infrastructure — so that the *system* behaves reliably even when the *model* does not.

The design rests on four commitments:

1. **The kernel is small and deterministic.** It manages process lifecycle, context admission, tool mediation, permissions, scheduling, and checkpointing. It contains no product logic, no workflow logic, and — critically — no LLM calls of its own. The kernel is boring on purpose.
2. **Context is a scheduled resource, not a prompt.** Nothing is "just injected." Every token entering the model's context window is retrieved, prioritized, budgeted, and evicted by a Context Engine that behaves like a memory hierarchy (L0–L5) rather than a string template.
3. **Verification is independent of the model.** An agent claiming "done" is an *observation*, not a *fact*. Only the Verification Engine — running real compilers, type checkers, linters, and tests — can transition a task to `Verified`.
4. **Multi-agent execution is a distributed system, not a chat with personas.** Subagents are isolated processes with their own workspaces, budgets, and capability sets, coordinated through explicit IPC and supervision trees, not implicit shared context.

AgentOS is deployable as an embedded library (single developer, local sandbox), a multi-tenant server (team, remote workers), or a distributed control plane (fleet of agents across many repositories). The same kernel powers coding, debugging, testing, DevOps, and security agents without modification — because the kernel knows nothing about "coding." It only knows about processes, context, tools, and verification.

---

## B. Mental Model

### B.1 The refined analogy

The traditional OS analogy is a good *entry point* and a bad *specification*. Below is a critical pass: what holds, what's incomplete, and what breaks.

| Classical Concept | Naive AgentOS Mapping | Verdict |
|---|---|---|
| CPU | LLM inference | **Incomplete.** A CPU is deterministic and stateless between instructions. The LLM is stochastic and its "instruction fetch" (context construction) is itself a major subsystem. Better framed as a *probabilistic co-processor* invoked by the kernel, not the kernel's core loop. |
| Instruction | Tool call | **Valid**, with a caveat: a CPU instruction is a single guaranteed atomic operation. A tool call must be validated, sandboxed, and its result normalized — it is closer to a *system call* than a raw instruction. |
| RAM | Working context | **Valid but incomplete.** RAM is uniform, addressable, byte-random-access. Context is non-uniform: order matters (recency/position bias), capacity is small and expensive (tokens cost money and attention degrades near the limit), and there is no random access — only serial re-presentation. Context is closer to a *scarce, ordered cache* than RAM. |
| Disk | Repository | **Valid.** The repository (plus event log, plus long-term memory store) is genuinely the durable backing store. |
| Process | Agent | **Valid**, and this is the strongest mapping in the whole analogy. An agent process has an address space (context), a scheduler-visible state, resource limits, and a lifecycle. |
| Thread | Agent turn/task | **Incomplete.** A thread shares an address space with siblings and is preemptible mid-instruction. An agent "turn" is closer to a *transaction* — it runs an observe→act→verify cycle to completion or rollback, and is not safely preemptible mid-reasoning. |
| Kernel | Agent harness/kernel | **Valid** if — and only if — the kernel is kept free of workflow/business logic (see Section E). |
| Syscall | Tool invocation | **Valid.** This is the correct primitive-level abstraction. |
| Device driver | Tool adapter / MCP server | **Valid.** MCP servers are drivers for external "devices" (SaaS APIs, databases, browsers). |
| Filesystem | Workspace/repository | **Valid**, extended with git semantics (branching, worktrees) that classical filesystems don't natively have. |
| Interrupt | Hook/event | **Incomplete.** Classical interrupts preempt the CPU mid-instruction. Most agent "interrupts" (PreTool, PostEdit) are actually *synchronous checkpoints* the kernel inserts around tool calls, not true asynchronous preemption. True async interrupts (user cancel, budget exceeded) are rarer and need a different mechanism (see Section 14 analysis below).
| Compiler | Verification engine | **Undersells it.** A compiler is one *stage* of verification. The Verification Engine also owns tests, lint, security scanning, and behavioral checks — it is closer to a full **CI system embedded in the control loop**. |
| Distributed system | Multi-agent runtime | **Valid**, and it should be taken completely literally: multi-agent coordination should be designed with the same rigor as any distributed system (partial failure, message loss, split-brain on shared workspace state), not as "agents talking to each other."

### B.2 Where the analogy fully breaks down

- **There is no equivalent of virtual memory.** Classical VM gives every process the illusion of unlimited, uniform address space via paging. Context has no such illusion — when it's full, information is simply *gone* unless something deliberately re-retrieves it. AgentOS must invent an explicit substitute: **just-in-time re-retrieval**, where "swapped out" context is not paged back in automatically but re-derived from the repository/memory store on demand. This is a new abstraction with no classical analog: **context is lossy, and the system must be designed assuming permanent, silent loss unless retrieval is explicit.**
- **There is no equivalent of an instruction pointer.** A CPU always knows exactly what it will do next. An LLM agent's "next instruction" is inferred, not fetched — it can be wrong, hallucinated, or contradictory to prior state. This requires a new primitive: **Action Validation**, a mandatory gate between "the model proposed an action" and "the kernel will execute it," which has no equivalent in classical CPU design (a CPU never rejects its own next instruction as invalid).
- **There is no equivalent of confidence.** Classical systems don't have partial trust in their own instructions. AgentOS must carry a **confidence/uncertainty signal** through the entire pipeline — from action proposal through verification depth selection — because how much to verify, and whether to escalate to a human, is a function of estimated correctness, not just outcome.
- **There is no equivalent of "the program can rewrite its own understanding of the problem."** Classical programs don't replan. Agents can and do abandon their plan mid-task based on new observations. This requires a first-class **Plan** object that is versioned and revisable, sitting above the task graph — again, nothing in classical OS design plays this role.
- **There is no equivalent of semantic retrieval.** A classical filesystem's "search" is exact-match or index-scan. Repository memory needs meaning-based retrieval (embeddings, ASTs, symbol graphs) that has no counterpart in `read()`/`write()`/`lseek()`.

### B.3 Genuinely new abstractions required

| New Abstraction | Why it has no classical equivalent |
|---|---|
| **Context Scheduler** | Decides what enters a bounded, ordered, lossy window — unlike a memory allocator, it must reason about *relevance*, not just availability. |
| **Action Validator** | Gates a probabilistically-generated "next instruction" before execution — CPUs never validate their own fetched instruction. |
| **Verification State Machine** | Independently re-derives ground truth about task state instead of trusting the actor's self-report — no analog in trusted CPU/OS execution. |
| **Confidence/Risk Signal** | A first-class value threaded through scheduling, verification depth, and escalation decisions. |
| **Plan Object (revisable)** | A mutable, versioned hypothesis about how to solve the task, distinct from the task graph itself. |
| **Loop/Oscillation Detector** | Detects when the "processor" is repeating a failed strategy — necessary because probabilistic actors can get stuck in ways deterministic programs structurally cannot (a deterministic program either halts or loops identically; an LLM can loop *approximately*, trying slightly different failed variants forever). |
| **Context Provenance Ledger** | Tracks *why* a piece of information is in context (which retrieval, which tool result, what turn) so conflicting or stale information can be identified and evicted — classical memory has no notion of "why is this byte here." |

---

## C. Full Architecture Diagram

```
                                   ┌─────────────────────────────┐
                                   │           Clients            │
                                   │  CLI · IDE · CI Bot · API SDK │
                                   └───────────────┬──────────────┘
                                                    │ ACP / gRPC / SSE
                                   ┌───────────────▼──────────────┐
                                   │        Orchestrator           │
                                   │  Plans tasks · Workflow logic │
                                   │  Business rules · Role graphs │
                                   └───────────────┬──────────────┘
                                                    │ Kernel API (stable ABI)
┌───────────────────────────────────────────────────────────────────────────────┐
│                              AGENT KERNEL                                     │
│                                                                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                  │
│  │ Process Manager │  │ Context Manager │  │ Resource Manager│                  │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                  │
│          │                    │                    │                          │
│  ┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐                  │
│  │    Scheduler    │  │  Memory Manager │  │  Tool Manager   │                  │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                  │
│          │                    │                    │                          │
│  ┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐                  │
│  │  Policy Engine  │  │  Event Engine   │  │ Runtime Manager │                  │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                  │
│          │                    │                    │                          │
│          └────────────────────┼────────────────────┘                          │
│                     ┌─────────▼──────────┐                                    │
│                     │ Security / Isolation│                                    │
│                     └─────────┬──────────┘                                    │
└───────────────────────────────┼───────────────────────────────────────────────┘
                                 │
        ┌────────────────┬──────┴──────┬────────────────┬─────────────────┐
        ▼                ▼             ▼                ▼                 ▼
 ┌────────────┐  ┌──────────────┐ ┌──────────┐  ┌────────────────┐ ┌─────────────┐
 │  Model      │  │ Tool Runtime │ │ Sandbox  │  │ Verification    │ │ Persistence │
 │  Runtime    │  │ (native +MCP)│ │ (T0–T5)  │  │ Engine          │ │ (event log, │
 │  (routing)  │  │              │ │          │  │ (independent)   │ │  stores)    │
 └─────┬──────┘  └──────┬───────┘ └────┬─────┘  └────────┬───────┘ └──────┬──────┘
       │                │               │                 │                │
       ▼                ▼               ▼                 ▼                ▼
 Frontier/Fast/    Read/Search/Edit  Container/    Type/Lint/Test/    Postgres · Git
 Local/Embedding    Execute/Git/     microVM/       Build/Security/    · Object Store
 Models              Browser/DB      Remote          Behavioral         · Event Log

                                 External World
        GitHub/GitLab · CI/CD · Registries · K8s · Issue Trackers · Cloud APIs
```

---

## D. Layered Architecture

| Layer | Responsibility | Must NOT contain |
|---|---|---|
| **L5 — Applications** | Coding agent, debugging agent, DevOps agent, etc. Role-specific prompts, domain heuristics. | Kernel primitives, direct sandbox access |
| **L4 — Orchestrator** | Task planning, workflow DAGs, multi-agent role assignment, business policy ("PRs need 2 reviewers") | Tool execution, permission enforcement (only *requests* it) |
| **L3 — Kernel** | Process/context/resource/tool mediation, scheduling, policy enforcement, checkpointing, event dispatch | Any workflow-specific logic, any single hardcoded agent role |
| **L2 — Runtime Services** | Model runtime, tool runtime (native + MCP), sandbox execution, verification engine | Task-level knowledge — a sandbox doesn't know what task it's serving |
| **L1 — Substrate** | Repository/git, object storage, databases, event log, network | — |
| **L0 — Infrastructure** | Compute (VMs/containers), model inference providers, cloud primitives | — |

Requests flow strictly downward through this stack; results flow upward as observations. No layer is permitted to skip a layer beneath it (the Orchestrator never touches the sandbox directly — it always goes through the Kernel's Tool Manager).

---

## E. Kernel Architecture

### E.1 Kernel modules and invariants

| Module | Owns | Invariant it guarantees |
|---|---|---|
| **Process Manager** | Agent process lifecycle (spawn, suspend, resume, kill) | Every live process has exactly one authoritative state record; no process exists without a parent supervisor |
| **Context Manager** | Context window construction per turn | Context assembly is deterministic given the same inputs and retrieval index state (reproducibility) |
| **Resource Manager** | Token/time/cost budgets per process and subtree | No process can exceed its allocated budget without explicit kernel-approved escalation |
| **Scheduler** | Turn/task/tool scheduling order | Starvation-free; respects declared priorities and deadlines |
| **Memory Manager** | Read/write path to working, session, and long-term memory stores | Writes are attributed (provenance) and never silently overwrite conflicting memory |
| **Tool Manager** | Tool registration, discovery, invocation mediation, result normalization | No tool executes without a capability check having passed first |
| **Policy Engine** | Capability grants, permission checks | Deny-by-default; every allow decision is logged with the policy rule that authorized it |
| **Event Engine** | Event bus, hook dispatch (Pre/Post events) | Every state-changing action produces exactly one durable event before and after |
| **Runtime Manager** | Sandbox tier selection and lifecycle | A tool never runs outside the tier its risk classification requires |
| **Security/Isolation** | Cross-cutting enforcement of the above (secrets, network egress, filesystem boundaries) | Isolation failures fail closed, never open |

### E.2 Kernel vs. user-space boundary

**In the kernel** (small, stable, rarely changes): process lifecycle, context admission control, budget accounting, tool mediation/permission checks, event log writes, checkpointing, sandbox tier selection.

**In user-space** (the Orchestrator and above): *what* task to run next, *which* agent roles exist, *how* to decompose a feature into subtasks, retry/backoff *policy choices* (the kernel provides the mechanism, not the strategy), prompt content, verification *thresholds* per project.

This split mirrors the classical "mechanism, not policy" kernel principle. A kernel that hardcodes "coder → tester → reviewer" is not a kernel, it's a workflow engine wearing a kernel's clothing — and it will need to be rewritten for every new agent type (Section 34's "same kernel powers 8 agent types" requirement fails immediately if role logic leaks into the kernel).

---

## F. Agent Process Model

### F.1 Primitives and their relationships

```
Agent            — a bound (model, permission-set, workspace) capable of running Tasks
Agent Process     — one running instantiation of an Agent with live State + Context
Task              — a unit of work with a defined completion/verification condition
Subtask           — a Task decomposed under a parent Task, forms a DAG
Action            — a single proposed tool call or reasoning step, output of inference
Observation        — the result returned to the agent after an Action executes
Context           — the ordered, budgeted set of tokens visible to the model this turn
State             — the durable, structured record of task/process progress (not context)
Memory            — durable information that outlives a single Process (session/long-term)
Workspace         — the isolated filesystem view (worktree) a Process operates on
Tool              — a callable capability with a schema, policy, and runtime
Capability         — a specific grant (e.g., CAN_WRITE /src/**) held by a Process
Resource          — a schedulable, budgeted quantity (tokens, time, sandbox slots)
Policy            — a rule set the Policy Engine evaluates to grant/deny capabilities
Event             — an immutable fact appended to the Event Log
Runtime           — the execution substrate a tool call runs inside (sandbox tier)
Sandbox           — an isolated execution environment instance
Artifact          — a durable output (diff, file, report) referenced, not embedded, in Context
Checkpoint         — a durable snapshot of {State, Context pointer, Workspace ref} enabling resume
Verification       — an independent determination of whether a Task's completion condition holds
Failure            — a classified deviation from expected State transition
Recovery           — a kernel-mediated strategy to return a Process to a valid State
```

**Key relationship:** State is the source of truth; Context is a *view* constructed from State + Memory + Repository for one inference call. This distinction is the single most important discipline in the whole system — conflating "what's true" (State) with "what's currently visible to the model" (Context) is the root cause of most agent reliability bugs in naive implementations.

### F.2 Process states

```
        spawn
          │
          ▼
      ┌────────┐   admit ctx    ┌───────────┐   propose action  ┌────────────┐
      │ CREATED│───────────────▶│  RUNNING   │───────────────────▶│  ACTING    │
      └────────┘                └─────┬─────┘                     └─────┬──────┘
                                       │▲                                │
                         resume ┌──────┘└──────┐ suspend         result  │
                                │               │                        ▼
                          ┌─────▼─────┐   ┌─────┴─────┐          ┌────────────┐
                          │ SUSPENDED  │   │  WAITING   │◀─────────│ VERIFYING  │
                          └───────────┘   │ (approval/  │         └─────┬──────┘
                                          │  subagent)  │               │
                                          └─────────────┘        pass  │  fail
                                                                        ▼   ▼
                                                              ┌─────────┐ ┌────────┐
                                                              │VERIFIED │ │ FAILED │
                                                              │(commit) │ └───┬────┘
                                                              └─────────┘     │
                                                                     retry ◀──┘ (budget permitting)
                                                                     │
                                                                     ▼
                                                              ┌─────────────┐
                                                              │  CRASHED /   │
                                                              │  ESCALATED   │
                                                              └─────────────┘
```

Every transition writes an Event and, at `VERIFYING`, `VERIFIED`, and `SUSPENDED`, a Checkpoint. Crash recovery always resumes from the last Checkpoint, never from raw context replay (context is a view, not a log — replaying it exactly is not guaranteed to be reproducible if retrieval indices changed).

### F.3 Model comparison and hybrid choice

| Model | Strength | Weakness for this domain |
|---|---|---|
| Pure Actor Model | Great isolation, natural message-passing IPC | No native notion of "verify before commit" or budget accounting |
| Pure Process Model | Strong isolation, resource limits, familiar mental model | Heavyweight for short-lived subtasks; no native DAG dependency tracking |
| Pure Thread Model | Cheap, shared address space | Wrong isolation properties — agents must NOT share context/workspace by default |
| Task Graph / DAG | Excellent for dependency-aware scheduling and parallelism | No lifecycle semantics for a *long-running, statefully reasoning* unit |
| Event-Driven State Machine | Excellent for recoverability and observability | Insufficient alone for expressing spawn/supervise hierarchies |
| Workflow DAG | Good for orchestrator-level planning | Wrong granularity for kernel-level primitives (too coarse) |

**Chosen hybrid:** Agent Processes are **actors** (isolated state, message-passing IPC, supervised) whose internal execution is an **event-driven state machine** (Section F.2), and whose task decomposition is exposed to the Orchestrator as a **DAG** for scheduling and parallelism. This gives isolation (actor) + recoverability (state machine) + parallel dependency-aware scheduling (DAG) without forcing any one paradigm to do a job it's bad at.

---

## G. Context / Memory Architecture

### G.1 Context hierarchy

```
L0  Immediate token context     — this turn's assembled prompt (hard token budget)
L1  Active task context         — current task's plan, recent tool results, open diffs
L2  Session memory               — this conversation/session's history, summarized
L3  Repository semantic index    — AST/symbol graph, embeddings, dependency graph
L4  Project knowledge            — conventions, prior decisions, docs, past PR patterns
L5  External knowledge           — web, docs sites, issue trackers, org-wide memory
```

Analogy to cache levels is deliberate: L0 is expensive and small (like L1 cache — every token here costs latency and money), L5 is cheap and effectively unbounded but slow to retrieve and lower-precision. The **Context Scheduler** decides, per turn, what gets promoted from L1–L5 into L0, under a hard token budget, using:

- **Relevance scoring** — structural (AST proximity to files being edited) + semantic (embedding similarity to the current subtask) + recency (event log distance).
- **Provenance-aware deduplication** — don't re-include a file already summarized unless it changed.
- **Eviction policy** — least-relevant-and-oldest first, but *never* evict State (State lives outside context entirely, in the Process record — this is what makes eviction safe).
- **Just-in-time retrieval over the repository** — the default is NOT "index the whole repo into context." The default is: give the agent a **repository map** (file tree + symbol index, cheap) and a `search`/`read` tool, and let retrieval be pull-based, driven by the agent's own actions, with the scheduler only pre-fetching high-confidence candidates (e.g., the file the current diff touches).

### G.2 Memory type → storage mapping

| Memory Type | Best Storage | Why |
|---|---|---|
| Working memory (this turn) | In-process, ephemeral | Never persisted beyond the turn |
| Short-term/session memory | SQLite (local) / Postgres (server) | Structured, queryable, transactional; small enough not to need anything heavier |
| Task/process state | Postgres (or SQLite embedded) | Needs ACID transactions for state transitions and checkpoint writes |
| Long-term/episodic memory | Postgres + object storage for large artifacts | Structured facts in Postgres; large blobs (diffs, logs) referenced by pointer in object storage |
| Repository memory (code) | Git + AST index (e.g., tree-sitter) + lexical index | Git is already the correct source of truth for code; don't duplicate it into a vector DB |
| Semantic memory (concepts, decisions, conventions) | Vector DB (selectively) | This is the *one* place embeddings clearly win — fuzzy conceptual recall, not code lookup |
| Procedural memory (learned tool-use patterns, fix recipes) | Structured store (Postgres) keyed by task signature | These are discrete, reusable facts, not fuzzy text — retrieval by exact/structural match beats embeddings here too |
| Event log | Append-only log (e.g., Postgres table or dedicated log store) | Source of truth for replay/audit |

**Explicit rejection:** a vector database is *not* used for code retrieval as the primary mechanism. Code has exact structure (imports, call graphs, types) that AST-aware and lexical (ripgrep-style) retrieval satisfy with higher precision and zero embedding drift risk. Embeddings are reserved for genuinely fuzzy recall: "have we solved something like this before," "what's our convention around X," cross-repo knowledge.

---

## H. Tool Architecture

### H.1 Tool interface (schema)

```typescript
interface Tool {
  name: string;
  version: string;
  category: "READ" | "SEARCH" | "EDIT" | "EXECUTE" | "GIT" | "BROWSER"
          | "NETWORK" | "DATABASE" | "BUILD" | "TEST" | "DEPLOY" | "OBSERVE";
  schema: JSONSchema;                 // input/output contract
  riskTier: 0 | 1 | 2 | 3 | 4 | 5;      // maps to sandbox tier (Section I)
  idempotent: boolean;
  timeoutMs: number;
  costEstimate: (input: unknown) => TokenOrDollarCost;
  execute(input, ctx: ToolExecContext): Promise<ToolResult>;
}

interface ToolResult {
  ok: boolean;
  output: NormalizedOutput;   // schema-consistent regardless of underlying tool
  provenance: { tool: string; version: string; startedAt: Date; runtime: RuntimeRef };
  cost: ActualCost;
}
```

### H.2 Where MCP belongs

MCP is **not** the whole Tool Layer. It is the **device driver bus for external, third-party capability** (Section H answer to "do not assume MCP should control the whole Tool Layer"):

| Stays as native kernel syscalls | Goes through MCP / user-space adapters |
|---|---|
| File read/write within workspace | External SaaS integrations (Jira, Slack, Linear) |
| Git operations on the managed repo | Arbitrary third-party APIs |
| Shell execution inside the sandbox | Browser automation |
| Diff application, patch validation | Org-specific internal tools |
| Verification tool invocation (test/build/lint runners) | Anything requiring dynamic, runtime-negotiated capability discovery |

Rationale: native tools are on the *hot path* of every task and must have kernel-level performance, permission integration, and result-normalization guarantees. MCP tools are on the *long tail* — high value, low frequency per-tool, benefiting from MCP's dynamic discovery/versioning instead of hardcoded kernel bindings. Treating MCP as a *driver bus mounted below the Tool Manager*, not as the Tool Manager itself, keeps the kernel's core hot-path tools fast and independently versioned from the sprawling MCP ecosystem.

### H.3 Discovery, versioning, sandboxing

- **Discovery:** static native tool registry (compiled in) + dynamic MCP server registry (queried at process start, cached, revalidated on version mismatch).
- **Versioning:** every tool call's ToolResult carries the tool version in provenance — this is required for reproducibility (Section 25).
- **Sandboxing:** the `riskTier` field routes execution to the matching Runtime tier (Section I) — the Tool Manager never lets a tool choose its own isolation level.
- **Retries/idempotency:** only idempotent tools are auto-retried by the kernel; non-idempotent tools (e.g., `git push`, `deploy`) require explicit compensating-action logic from the Orchestrator on failure.

---

## I. Runtime / Sandbox Architecture

| Tier | Mechanism | Used for | Network | Filesystem |
|---|---|---|---|---|
| T0 | In-process, read-only | `read`, `search`, AST parse | None | Read-only workspace mount |
| T1 | Restricted subprocess (seccomp/rlimits) | Local lint/format, cheap scripts | None | Workspace only, no `..` escape |
| T2 | Workspace sandbox (bubblewrap/namespaces) | Test running, build | Loopback only | Workspace + scoped temp |
| T3 | Container (gVisor-hardened) | Arbitrary shell commands, package installs | Egress-filtered allowlist | Container-scoped, copy-on-write overlay |
| T4 | microVM (Firecracker-class) | Untrusted/unreviewed code execution, plugin execution | Fully isolated, explicit proxy | Ephemeral disk, snapshot-restorable |
| T5 | Remote isolated execution | Production-adjacent actions (deploy, infra changes) | Policy-gated, audited | No direct FS — mediated through deploy APIs only |

Selection is automatic from `Tool.riskTier`, never agent-chosen. Every tier enforces: CPU/memory/process-count limits, wall-clock timeout, credential injection *only* for the specific call (never ambient), and a structured audit log entry per execution regardless of outcome.

---

## J. Scheduler Architecture

```
              ┌───────────────────┐
              │   Model Scheduler  │  routes inference calls across providers/models
              └─────────┬─────────┘
                        │
              ┌─────────▼─────────┐
              │   Agent Scheduler  │  decides which Process runs next / gets a turn
              └─────────┬─────────┘
                        │
              ┌─────────▼─────────┐
              │   Task Scheduler   │  DAG-aware ordering of subtasks within a process tree
              └─────────┬─────────┘
                        │
              ┌─────────▼─────────┐
              │   Tool Scheduler   │  queues/rate-limits tool + sandbox invocations
              └─────────┬─────────┘
                        │
              ┌─────────▼─────────┐
              │  Runtime Scheduler │  assigns sandbox tier instances to queued tool calls
              └───────────────────┘
```

**Algorithm choice:** a **hybrid resource-aware, DAG-respecting priority scheduler**, not pure FIFO or pure fair-share. Concretely: tasks are nodes in a dependency DAG (blocked tasks can't be scheduled); among unblocked tasks, priority is a weighted function of `(deadline proximity, cost budget remaining, historical failure probability for this task class, workspace-lock availability)`; ties broken by fair-share across tenants/projects to prevent starvation. Work-stealing is used at the Tool Scheduler level for embarrassingly parallel verification tasks (e.g., running independent test shards). Pure FIFO is rejected (starves urgent fixes behind long-running exploratory agents); pure priority is rejected alone (starves low-priority work indefinitely without fair-share).

At fleet scale (hundreds–thousands of agents), the Agent Scheduler becomes bin-packing over sandbox capacity and model-provider rate limits — this is the actual bottleneck at scale (see Section X), not reasoning quality.

---

## K. Multi-Agent Architecture

### K.1 Model comparison

| Model | Fit |
|---|---|
| Pure hierarchical (main→subagents, fixed roles) | Simple, predictable, but brittle when the right decomposition isn't known upfront |
| Pure peer-to-peer | Flexible but hard to bound cost/scope; coordination overhead grows combinatorially |
| Blackboard | Good for exploratory/convergent problems (many agents proposing hypotheses) but weak on accountability/ownership of writes |
| Pure actor model | Good isolation, but needs an explicit supervision layer added on top |
| Task DAG only | Great for scheduling, insufficient for dynamic replanning mid-execution |
| Central scheduler | Necessary at the kernel level regardless of the above |
| Market-based | Interesting for cost-optimal routing at huge scale, unnecessary complexity below ~1000 agents |

**Chosen hybrid:** **Hierarchical supervision** for accountability and budget containment (every subagent has exactly one supervisor responsible for its budget and result), **DAG-based scheduling** for dependency-aware parallelism, and a **narrow blackboard** (a shared, append-only findings store, not a shared mutable workspace) for exploratory fan-out tasks (e.g., three "Explorer" agents investigating a bug independently, writing findings, not files). Direct filesystem sharing between concurrent agents is avoided by default — isolation via git worktrees is the norm; blackboard is for *information*, not *code state*.

### K.2 Coordination primitives

- **Agent discovery:** Orchestrator queries the kernel's Process Manager for capability-matching idle/spawnable agent types.
- **Spawning:** parent process requests a child via the kernel, which allocates a scoped workspace (worktree), a context budget, and a capability subset that is a **strict subset** of the parent's (no privilege escalation through spawning).
- **Messaging:** typed `AgentMessage` over the Event Bus, not raw context concatenation.
- **Shared state:** only through the Persistence layer (Section M) — never through directly shared in-memory context.
- **Conflict resolution:** workspace-level (git merge/rebase mediated by kernel), never "last agent to finish wins" silently — conflicts surface as a `MergeConflict` event requiring resolution (auto-resolvable class, or escalate).
- **Supervision:** every subagent failure propagates to its parent as a `FailureReport`; parent decides retry/reassign/escalate — classic Erlang-style "let it crash, supervisor decides" philosophy, deliberately reused here because it's the right pattern for unreliable workers.

---

## L. IPC / Agent Communication

```
AgentMessage {
  from: AgentId; to: AgentId | "broadcast";
  type: "TaskRequest" | "TaskResult" | "Observation" | "ArtifactReference" | "FailureReport" | "VerificationReport";
  payload: Reference | InlineSmall;   // large payloads are ALWAYS ArtifactReference, never inlined
  correlationId: TaskId;
}
```

**Rule:** payloads above a small inline threshold (e.g., a few KB) are always passed **by reference** (an `ArtifactReference` pointing into object storage or the git object store), never copied into another agent's context. This is the direct fix for the most common naive-multi-agent failure mode: context bloat from re-transmitting large diffs/logs between agents. The receiving agent pulls only the slice of the artifact it actually needs, on demand, through the Context Scheduler.

---

## M. Persistence Architecture

| Data | Store | Event-sourced? |
|---|---|---|
| Process/task state | Postgres (transactional tables) | State is a **projection** of the event log, not the log itself |
| Event log | Append-only log table / dedicated log store | Yes — this *is* the log |
| Checkpoints | Postgres + object storage pointer to workspace snapshot | Snapshot referenced, not re-derived from full replay (replay is for debugging, not the recovery hot path) |
| Context | Not persisted as-is; reconstructed from State + Memory each turn | No — context is a view, persisting it is redundant and encourages the State/Context conflation this design explicitly avoids |
| Artifacts (diffs, logs, reports) | Object storage, content-addressed | No |
| Repository | Git | N/A — git is its own append-mostly log |
| Policies | Postgres, versioned | Yes, for audit — policy changes are themselves events |

**Where event sourcing earns its cost:** task/process lifecycle (needed for replay, audit, time-travel debugging of *why* an agent did something). **Where it's rejected:** context reconstruction (too expensive to replay per-turn; a snapshot-based checkpoint plus fresh retrieval is cheaper and just as correct) and raw file content (git already does this better than a bespoke event log would). This directly follows Section 22's instruction to use event sourcing "where it provides real value," not everywhere.

Recovery paths: **crash recovery** restores the last Checkpoint and resumes the state machine; **task resume** reconstructs Context fresh from current State + Memory (not from the pre-crash context — the world may have changed); **replay** (for debugging only) walks the Event Log to reconstruct a full causal trace, never used on the recovery hot path.

---

## N. Security Model

### N.1 Capability-based, not role-based

Capabilities are chosen over RBAC as the primary model because agent permissions are **per-process and dynamically scoped**, not per-user-role. A single "Coder" role in RBAC terms would need dozens of ambient permissions; a capability model instead grants an agent process *exactly* the resource handles it needs for its current task, and those handles do not persist beyond the process (unlike a role, which is a standing grant). RBAC is layered on top only at the Orchestrator level, for coarse human-facing concerns ("which humans can approve deploys").

### N.2 Example policy

```
Agent: coder-subprocess-4471
  CAN_READ:    /repo/**
  CAN_WRITE:   /repo/src/**, /repo/tests/**
  CAN_EXECUTE: npm test, npm run lint, tsc --noEmit
  CANNOT_ACCESS: ~/.ssh, ~/.aws, production credentials, arbitrary outbound network
  BUDGET:      120,000 tokens, $4.00, 15 minutes wall-clock
  SANDBOX_TIER: T3 (container)
```

Every capability grant is evaluated at call time by the Policy Engine (deny-by-default), and every allow/deny decision is written to the audit log with the specific rule that fired. Spawned children receive a subset — never a superset — of the parent's capability set (Section K.2), which structurally prevents privilege escalation through agent hierarchies.

---

## O. Observability

```
User Request → Task → Agent Process → Context Assembly → Model Call
   → Tool Call → Runtime/Sandbox → Verification → Final Artifact
```

Every arrow above is a traced span with a shared `correlationId`. Agent-specific telemetry beyond classical metrics/logs/traces/profiles:

- **Token usage** and **context size** per turn (cost + relevance-vs-window-size ratio)
- **Tool latency and failure rate**, broken out per tool and per sandbox tier
- **Model latency/cost** per provider, feeding the Model Scheduler's routing decisions
- **Reasoning step count** and **retry rate** — leading indicators of an agent struggling before it outright fails
- **Loop/oscillation detection hits** — the anti-loop mechanism (Section 17/P) should itself be observable, not just a silent internal guard
- **Verification pass rate by risk tier** — are lightweight-verified changes actually safe in practice, informing whether verification tiers need recalibration

This telemetry is what lets the Scheduler and Verification Engine *adapt* over time (e.g., escalate verification depth for a task class with a rising post-merge defect rate) — observability isn't just for human dashboards, it's a feedback input to the control loop itself.

---

## P. Failure and Recovery Model

| Failure Class | Typical Cause | Recovery Strategy |
|---|---|---|
| Model failure | Provider outage, malformed output, refusal | Model switch (Model Scheduler fallback), retry with backoff |
| Tool failure | Transient error, bad input | Retry if idempotent; else surface to agent as Observation for replanning |
| Runtime failure | Sandbox crash, OOM | Runtime restart, resource limit re-evaluation, checkpoint restore |
| Network failure | External API unreachable | Backoff + circuit breaker; degrade to cached/offline context sources |
| Context failure | Retrieval returned irrelevant/stale info | Context refresh — re-run retrieval, invalidate provenance-tagged stale entries |
| State corruption | Concurrent write race, bad projection | Rebuild projection from Event Log (this is the payoff of event sourcing at the state layer) |
| Permission failure | Policy denied a needed capability | Escalate to human approval, or replan within granted capabilities |
| Dependency failure | Missing package, version conflict | Sandbox environment rebuild from lockfile, or escalate |
| Build/test failure | Genuine code defect | Normal control-loop retry: back to Infer Action with new Observation |
| Agent deadlock | Circular subagent wait | Supervisor-detected timeout → forced termination of the cycle, escalate |
| Agent loop | Repeating near-identical failed action | Loop Detector trips → forced strategy change or human escalation (never silent infinite retry) |
| Resource exhaustion | Budget/token/time limit hit | Checkpoint, suspend, escalate for budget increase or termination |

General principle: **recovery strategy escalates in a fixed ladder** — retry → backoff → refresh (context/model/tool) → checkpoint restore → replanning → human escalation — and the kernel enforces that a process cannot skip straight to "just keep trying the same thing," which is the anti-loop invariant from Section 17.

---

## Q. Technology Stack

| Subsystem | Language/Framework | Store | Rationale |
|---|---|---|---|
| Kernel core (process mgr, scheduler, policy engine, resource mgr) | **Rust** | — | Correctness-critical, concurrency-heavy, must be memory-safe and fast; this is infrastructure code, not experimentation code |
| Sandbox/runtime orchestration | **Rust** | — | Direct control over namespaces/cgroups/microVM lifecycles; Rust's ecosystem here (Firecracker itself is Rust) is mature |
| Tool runtime (native tools) | **Rust**, with a stable FFI/RPC boundary | — | Hot path performance and safety |
| MCP adapter layer / SDK / CLI | **TypeScript** | — | This is where ecosystem breadth matters most — most MCP servers, IDE integrations, and developer tooling are TS-first |
| Context Engine (retrieval, scheduling, compression) | **Rust** core with **Python** for embedding-model inference paths only | Vector DB (selective) + Postgres | Retrieval logic needs to be fast and called extremely often; only the embedding model call itself benefits from Python's ML ecosystem, and that's isolated behind an RPC boundary |
| Verification Engine | **Rust** orchestrator invoking language-native toolchains (tsc, pytest, cargo test, etc.) | — | The engine itself is a thin, fast dispatcher; the actual compilers/test runners are whatever the target project already uses — AgentOS should never reimplement a type checker |
| Model Runtime (routing, budget) | **Rust** | Postgres (usage ledger) | Needs to be fast, on the hot path of every inference call |
| Event log / state store | Postgres | Postgres | Boring, correct, transactional — exactly what state transitions need |
| Repository memory | Git + tree-sitter (AST) + ripgrep-class lexical index | Git objects + local index files | No reason to duplicate what git already does well |
| Semantic memory | Vector DB (e.g., a managed pgvector instance) | Postgres extension, not a separate service, below fleet scale | Avoids operating a whole separate database class for a narrow use case |
| Object storage (artifacts, checkpoints) | — | S3-compatible object store | Standard, cheap, content-addressable |
| API/ABI layer | gRPC (agent↔kernel), SSE (streaming to clients), REST (simple CRUD, e.g., policy management), MCP (external tool bus), ACP (cross-agent-vendor interop where applicable) | — | See Section 26 rationale below |
| Orchestrator / workflow logic | **TypeScript** or **Python**, pluggable | — | This layer changes often and benefits from rapid iteration; deliberately kept out of the Rust kernel |
| Observability | OpenTelemetry (traces/metrics), structured logs to a log store, agent-specific telemetry as OTel span attributes | — | Standard, avoids inventing a bespoke tracing format |

**Why not a single language everywhere:** the kernel/runtime/sandbox tier is correctness- and performance-critical infrastructure — Rust. The orchestration/workflow/tool-ecosystem tier changes constantly and benefits from TypeScript's ecosystem (this is also where most MCP servers and IDE integrations already live). Python is deliberately confined to the narrow slice where its ML ecosystem is genuinely load-bearing (embedding inference), isolated behind an RPC boundary so a slow, GIL-bound process is never on the kernel's hot path.

### Q.1 API/ABI protocol placement

| Boundary | Protocol | Why |
|---|---|---|
| Client ↔ AgentOS | SSE (streaming) + REST (control) | Clients need incremental token/event streaming and simple request/response for control actions |
| Orchestrator ↔ Kernel | gRPC | High call volume, needs low latency and strong typing; this is the busiest internal boundary |
| Kernel ↔ Tool Runtime (native) | In-process/RPC (same trust boundary) | No need for a heavyweight protocol within the same security domain |
| Kernel ↔ MCP servers | MCP (JSON-RPC based) | This is literally what MCP is for — external, dynamically discovered tool capability |
| Agent ↔ Agent (cross-vendor) | ACP where interoperating with non-AgentOS agents | Only needed at the boundary with foreign agent systems |
| Kernel ↔ Persistence | Native DB drivers (Postgres wire protocol) | No reason to add an RPC hop for the state store |

---

## R. Repository Structure

```
agent-os/
├── kernel/                 # Rust: process mgr, scheduler, policy, resource mgr, event engine
│   ├── process/
│   ├── scheduler/
│   ├── policy/
│   ├── resources/
│   └── events/
├── context/                 # Rust: context scheduler, hierarchy (L0-L5), retrieval interfaces
│   ├── retrieval/            # AST, lexical, semantic adapters
│   └── provenance/
├── memory/                  # store adapters: postgres, object-store, vector, git-index
├── tools/
│   ├── native/                # Rust native tool implementations (read/edit/exec/git)
│   └── mcp-bridge/            # kernel-side MCP client integration
├── runtime/                  # sandbox tier implementations (T0-T5)
│   ├── process-sandbox/
│   ├── container/
│   └── microvm/
├── verification/              # verification state machine + toolchain adapters
├── models/                    # model runtime, routing, provider adapters
├── security/                  # capability system, secret manager, audit log
├── persistence/                # event log, checkpoint store, projections
├── agents/                     # actor runtime, supervision trees
├── orchestration/               # workflow DAGs, role graphs, business policy (user-space, TS/Py)
├── protocols/                   # gRPC/REST/SSE/MCP/ACP schema definitions (shared)
├── sdk/                          # client SDKs (TS, Python)
├── cli/
├── web/                           # dashboard / observability UI
├── workers/                        # deployable worker processes for server/cloud mode
├── observability/                    # OTel exporters, agent-specific telemetry pipeline
├── tests/
│   ├── kernel/
│   ├── integration/
│   └── chaos/                          # failure-injection tests for the recovery model
└── docs/
```

Change from the example in the prompt: `mcp/` is collapsed into `tools/mcp-bridge/` (it's not a peer of the kernel, it's a bridge the Tool Manager owns — giving it a top-level directory implies it's a co-equal subsystem, which Section H explicitly rejects). `observability/` and `security/` are promoted to top-level, cross-cutting directories rather than being buried, since both are cross-cutting invariants touched by nearly every module. A `tests/chaos/` directory is added explicitly, since a system whose core design principle is "recover from probabilistic failure" needs failure-injection testing as a first-class citizen, not an afterthought.

---

## S. Core Data Structures

```typescript
interface AgentProcess {
  id: AgentId;
  parent: AgentId | null;
  model: ModelProfile;
  state: ProcessState;              // CREATED | RUNNING | ACTING | VERIFYING | ...
  workspace: WorkspaceRef;          // git worktree reference
  capabilities: Capability[];       // strict subset of parent's
  budget: { tokens: number; costUsd: number; wallClockMs: number };
  eventStream: EventStreamRef;
  checkpoints: CheckpointRef[];
  createdAt: Date;
}

interface Task {
  id: TaskId;
  parentTask: TaskId | null;
  description: string;
  completionCondition: VerificationSpec;
  dependsOn: TaskId[];               // DAG edges
  state: "pending" | "blocked" | "in_progress" | "verifying" | "verified" | "failed";
  ownerAgent: AgentId;
}

interface Action {
  id: ActionId;
  taskId: TaskId;
  proposedBy: AgentId;
  kind: "tool_call" | "reasoning_step" | "plan_revision";
  toolCall?: { tool: string; input: unknown };
  confidence: number;                 // 0-1, threaded through to verification depth selection
}

interface ToolCallEvent {
  actionId: ActionId;
  tool: string; version: string;
  riskTier: 0|1|2|3|4|5;
  input: unknown; result: ToolResult;
  policyDecision: { allowed: boolean; ruleId: string };
}

interface Checkpoint {
  id: CheckpointId;
  processId: AgentId;
  taskState: Task;
  workspaceSnapshot: WorkspaceSnapshotRef;
  eventLogOffset: number;
  createdAt: Date;
}

interface VerificationReport {
  taskId: TaskId;
  stages: { name: string; passed: boolean; detail: string }[];
  overallPassed: boolean;
  requiredHumanReview: boolean;
}

interface Policy {
  agentPattern: string;
  canRead: string[]; canWrite: string[]; canExecute: string[];
  cannotAccess: string[];
  budget: Budget;
  sandboxTier: 0|1|2|3|4|5;
}
```

---

## T. Execution Sequence

```
User Request
   → Orchestrator creates Task (with completion condition)
   → Kernel spawns/reuses Agent Process, allocates Workspace + Capability set
   → Context Manager assembles L0 context (repo map + task + relevant L1-L5 pulls)
   → Model Runtime routes inference call → LLM proposes Action
   → Action Validator checks: schema valid? capability held? budget remaining?
        ├─ invalid → reject, re-prompt with reason (no execution)
        └─ valid → proceed
   → Tool Manager checks Policy Engine → Runtime Manager selects sandbox tier
   → Tool executes in Sandbox → Result normalized → Observation returned
   → State updated, Event written, (periodically) Checkpoint written
   → Loop until agent proposes "task complete"
   → Verification Engine independently checks completion condition
        ├─ fails → Observation fed back, retry (bounded) or replan
        └─ passes → Task → VERIFIED, Checkpoint committed
   → Final Artifact (diff/PR/report) produced, referenced not embedded
```

---

## U. Security Sequence

```
Agent proposes Action (tool_call: "execute", input: "rm -rf /tmp/x")
   → Tool Manager: is this tool registered? version pinned?
   → Policy Engine: does Agent's capability set include CAN_EXECUTE for this pattern?
        ├─ deny → Event{PolicyDenied, ruleId} logged, Observation="denied: <rule>" returned to agent
        └─ allow → continue, decision logged with ruleId
   → Runtime Manager: map tool riskTier → Sandbox Tier (e.g., T2)
   → Secret Manager: inject only the specific credentials this call is scoped to (if any), scoped to call lifetime
   → Sandbox executes with filesystem/network restrictions for that tier
   → Result captured → Audit Log entry written (agent, tool, input hash, decision, result, timestamp)
   → Observation returned to Agent Process
```

---

## V. Multi-Agent Sequence

```
Parent Agent (Task: "fix flaky test suite")
   → decomposes into subtasks: {investigate, fix, verify}
   → Kernel: Spawn Subagent("Explorer") with capability subset {CAN_READ /repo/**}
   → Kernel: Allocate isolated Workspace (git worktree, branch from parent's HEAD)
   → Kernel: Allocate Context budget (child gets its own L0 budget, separate from parent's)
   → Explorer executes (Section T loop) → produces Findings (ArtifactReference, not inlined)
   → Explorer reports TaskResult to Parent via typed AgentMessage
   → Parent spawns "Coder" subagent, passing Findings by reference
   → Coder executes → produces diff in its own worktree
   → Verification Engine checks Coder's diff independently
   → On VERIFIED: Kernel mediates merge of Coder's worktree back into Parent's workspace
        ├─ clean merge → Parent's workspace updated, Event{Merged} logged
        └─ conflict → Event{MergeConflict}, escalate to Parent (or human) for resolution
   → Parent aggregates results, marks its own Task VERIFIED once its own completion condition holds
   → Subagents terminated, their Checkpoints retained for audit, Workspaces garbage-collected
```

---

## W. Performance Model

- **Latency:** dominated by (a) model inference time — mitigated by routing cheap/fast models to low-complexity actions (Model Scheduler), and (b) tool/sandbox cold-start — mitigated by sandbox pooling/warm pools for common tiers (T2/T3).
- **Token usage:** the single largest controllable cost lever. The Context Scheduler's admission control (Section G) is the primary defense against unbounded growth; a hard per-turn budget plus aggressive eviction keeps cost roughly constant per turn regardless of task length, rather than growing linearly with conversation length as naive "append everything" designs do.
- **Memory usage:** State records and Event Log entries are small and structured (cheap); the risk is context reconstruction cost at scale, mitigated by caching recently-assembled context views keyed by (task state hash, retrieval index version).
- **Concurrency:** bounded primarily by sandbox capacity and model-provider rate limits, not by kernel logic itself (the kernel's own operations are sub-millisecond; the expensive parts are I/O to models and sandboxes).
- **I/O:** repository reads should be memory-mapped/cached at the Runtime Manager level per workspace; avoid re-cloning/re-checking-out on every subagent spawn — use lightweight worktrees off a shared object store.
- **Tool overhead:** normalize once, cache idempotent read-tool results within a task's lifetime (e.g., don't re-read an unchanged file twice in one task).
- **Scheduling overhead:** negligible until fleet scale (hundreds+ concurrent processes), at which point the Agent Scheduler's bin-packing computation itself needs to be incremental, not recomputed from scratch per tick.

---

## X. Scalability Model

| Scale | Bottleneck | Mitigation |
|---|---|---|
| **1 agent** | None — single-process concerns only | N/A |
| **10 agents** | Shared workspace contention if not properly isolated | Enforce worktree-per-agent as default (Section K), not optional |
| **100 agents** | Model-provider rate limits; sandbox pool exhaustion | Model Scheduler multi-provider routing + request queuing; sandbox pool autoscaling |
| **1,000+ agents** | Scheduler bin-packing overhead; Postgres write contention on Event Log/State; object storage egress cost | Shard the Event Log/state store by tenant/project; move Agent Scheduler to incremental/streaming bin-packing; introduce a Control Plane (Section 27) separating Scheduler/Policy/Storage as independently scalable services rather than one monolith |

The transition point that forces genuine distributed-systems architecture (control plane + independently scalable workers, per Section 27's "Distributed Cloud" deployment mode) is roughly the 100→1,000 agent boundary — below that, a single well-engineered server process with a Postgres backend is sufficient and simpler.

---

## Y. Design Trade-offs

| Decision | Trade-off accepted |
|---|---|
| Kernel in Rust, orchestrator in TS/Python | Two-language system increases build/tooling complexity, in exchange for correctness where it matters most and velocity where it matters most |
| Pull-based (JIT) retrieval instead of full-repo context injection | More tool-call round trips per task, in exchange for dramatically lower cost and better precision at any repo size |
| Independent Verification Engine (never trusting model self-report) | More engineering investment in toolchain integration, in exchange for actually reliable completion signals |
| Event sourcing for process/task state only, not for context or files | Loses "replay literally everything" purity, in exchange for avoiding an expensive and largely pointless context-replay mechanism |
| Capability-based security over RBAC | More fine-grained policy authoring burden, in exchange for structurally preventing privilege escalation through spawning |
| Strict artifact-by-reference (never inline large payloads between agents) | Extra indirection/lookup on every cross-agent handoff, in exchange for bounded context growth in multi-agent trees |
| Hard budget ceilings with kernel-enforced escalation ladder | Some legitimately-long tasks will hit friction requiring human approval, in exchange for bounding worst-case runaway cost/loops |
| Sandbox tier chosen by tool risk classification, not agent self-selection | Less flexibility for agents to "ask" for looser sandboxing, in exchange for closing the most common security bypass vector (an agent talking itself into a less restrictive tier) |

---

## Z. Final Architecture

```
                         ┌───────────────────────────┐
                         │        Orchestrator         │   (workflow/policy — user space)
                         └──────────────┬────────────┘
                                        │  gRPC
        ┌───────────────────────────────▼───────────────────────────────┐
        │                          AGENT KERNEL                          │
        │   Process · Context · Resource · Scheduler · Policy · Events    │
        │              (deterministic, small, model-agnostic)             │
        └──┬──────────┬───────────┬───────────┬───────────┬─────────────┘
           │          │           │           │           │
      ┌────▼───┐ ┌────▼────┐ ┌────▼────┐ ┌────▼─────┐ ┌───▼─────────┐
      │ Model   │ │ Tool    │ │ Sandbox │ │Verification│ │ Persistence │
      │ Runtime │ │ Runtime │ │ (T0-T5) │ │  Engine    │ │ (event log, │
      │(routing)│ │(native+ │ │         │ │(independent│ │  Postgres,  │
      │         │ │  MCP)   │ │         │ │ of model)  │ │  git, obj)  │
      └─────────┘ └─────────┘ └─────────┘ └────────────┘ └─────────────┘

   Probabilistic reasoning (LLM) is a compute resource the kernel calls out to —
   never the thing the kernel's correctness depends on.
   Determinism lives in the kernel, the verification engine, and the persistence layer.
   Non-determinism is confined to Action proposal, and is always gated by
   validation → policy → sandbox → independent verification before it can
   change anything durable.
```

**The one-sentence architecture:** *AgentOS is deterministic infrastructure that safely schedules, bounds, and independently verifies probabilistic reasoning — and the same kernel does this identically whether the reasoning is writing code, debugging a test, or planning a deployment.*

---

## Appendix: Minimal Viable AgentOS & Roadmap

**MVP scope (V0):** Agent Loop (observe→act→verify) · State (Postgres) · Context Engine (L0/L1 only, JIT retrieval, no L3-L5) · Tool Registry (native tools only: read/edit/exec/git) · Filesystem/worktree isolation · Shell sandbox (T1/T2 only) · Verification (build/test/lint, single tier, not adaptive) · Persistence (event log + checkpoints) · Single-agent only, no multi-agent.

**Explicitly deferred, not V0:** multi-agent orchestration, MCP bridge, vector/semantic memory, adaptive verification tiers, distributed scheduler, model routing across providers (single model is fine), T4/T5 sandbox tiers, ACP interop.

```
V0: Single-agent loop, local, one sandbox tier, basic verification
 ↓
V1: Adaptive verification, JIT context L0-L3, capability-based policy engine
 ↓
V2: Multi-agent (hierarchical + DAG), MCP bridge, checkpoint/resume, server deployment
 ↓
Distributed AgentOS: Control plane split, fleet scheduling, T4/T5 sandboxes, model routing
 ↓
Software Factory: Cross-repo memory, self-improving tool system, continuous autonomous operation with escalation-based human oversight
```

Rule of thumb for what NOT to build first: nothing on the "Advanced AgentOS" list (Section 30) — speculative execution, dynamic context compilation, self-healing workflows — is worth building before the Verification Engine and Policy Engine are rock-solid, since every advanced capability multiplies the cost of a verification or security gap rather than compensating for it.
