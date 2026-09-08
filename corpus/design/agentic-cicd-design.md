# Autonomous Agent-Native CI/CD Pipeline — Engineering Design Document

**Status:** Draft for engineering review · **Scope:** Full system architecture, NFRs, schemas, roadmap
**Audience:** Senior engineering team building v1 → production

---

## 0. Executive Summary

This document specifies an autonomous CI/CD platform in which an AI coding agent acts as the
software engineer, and deterministic infrastructure acts as the compiler, test runner, sandbox,
policy enforcer, and safety net. The central architectural principle:

> **The LLM provides intelligence. Deterministic infrastructure provides execution, isolation,
> policy enforcement, verification, and safety.** The LLM is never in the trust boundary for
> anything privileged, irreversible, or safety-critical.

The system is built around five pillars:

1. A **state-machine + DAG pipeline orchestrator** (Temporal) that is durable, resumable, and
   idempotent — never a linear script.
2. An **Agent Tool Gateway** that mediates every action an agent takes, enforcing policy,
   permissions, and resource limits before anything reaches real infrastructure.
3. A **Failure Intelligence pipeline** that turns raw logs into structured, fingerprinted,
   evidence-backed failure objects — never raw log dumps into an LLM context window.
4. A **bounded, budgeted repair loop** with oscillation detection, regression gates, and
   mandatory human escalation paths — autonomy with hard ceilings.
5. A **Policy Engine** that owns every irreversible decision (merge, deploy, promote, rollback).
   Agents recommend; policy decides.

Everything below is designed to be buildable by a team starting immediately: concrete schemas,
interfaces, state machines, technology choices with trade-offs, and measurable acceptance
criteria — not a conceptual essay.

---

## 1. Design Principles

| # | Principle | Consequence |
|---|---|---|
| 1 | Agent is the software engineer, not a chatbot bolted onto CI | Agent has a full tool suite: read, write, run, test, debug, commit, PR, deploy-recommend |
| 2 | Reasoning and execution are strictly separated | Agent Brain never calls infra directly — only through the Tool Gateway |
| 3 | Pipelines are state machines + DAGs, never linear scripts | Enables parallelism, conditional branches, resumability |
| 4 | Context is engineered, not dumped | Retrieve → rank → compress → summarize → inject, with a token budget |
| 5 | Failures are structured before they are reasoned about | Log Parser → Classifier → Fingerprint → Root Cause, never raw stdout to the LLM |
| 6 | Repair is bounded | Max iterations, token/time/execution budgets, oscillation detection, mandatory escalation |
| 7 | Production safety is a deterministic policy decision | LLM recommends rollback/promote; policy gates decide |
| 8 | Every privileged action is credentialed just-in-time | No agent ever holds a long-lived secret |
| 9 | Every operation is idempotent | Duplicate events, retries, and replays must never double-execute |
| 10 | Multi-agent systems have explicit, minimal roles | 8 named agents with strict I/O contracts, not an open-ended swarm |

**The ten mistakes this design explicitly avoids** (see prompt §42): LLM-as-CI-engine, full-repo
context dumping, raw-log-to-LLM, LLM access to production credentials, unbounded repair loops,
"everything is a code bug" classification, LLM-only rollback authority, unscoped multi-agent
sprawl, RAG-only debugging, and purely linear pipelines. Each is addressed by a specific
component below (Tool Gateway, Context Engine, Failure Intelligence, Credential Broker, Repair
Loop budgets, Failure Classifier, Policy Engine, Agent Contracts, Hybrid Failure KB, and the
Pipeline State Machine, respectively).

---

## 2. Reference Architecture

```text
Developer ──push/PR──▶ Git Provider ──webhook──▶ Event Gateway ──▶ Event Bus (NATS)
                                                                        │
                                                                        ▼
                                                          Pipeline Orchestrator (Temporal)
                                                           │                        │
                                     ┌─────────────────────┤                        ├───────────────────┐
                                     ▼                                              ▼                    ▼
                          Agent Runtime (Planner/Coder/                   CI Task Scheduler      Policy Engine (OPA)
                          Tester/Debugger/Security/                              │
                          Reviewer/Release/Incident)                             ▼
                                     │                                    CI Workers (pool)
                                     ▼
                            Agent Tool Gateway
                        (policy check · perm check ·
                         resource limits · validation)
                                     │
                                     ▼
                            Execution Fabric
                    (gVisor container / Firecracker microVM)
                                     │
              ┌──────────────┬───────┴────────┬──────────────┐
              ▼              ▼                ▼               ▼
           Build          Test            Static/Sec       Git Ops
              │              │                │               │
              └──────────────┴───────┬────────┴───────────────┘
                                      ▼
                            Failure Intelligence Engine
                        (parse → classify → fingerprint → RCA)
                                      │
                          ┌───────────┴────────────┐
                          ▼                         ▼
                  Debugger Agent            Failure Knowledge Base
                  (evidence-driven)          (SQL + vector + graph)
                          │
                          ▼
                    Repair Loop (bounded)
                          │
                        validation
                          │
                          ▼
                  Artifact Registry (OCI + SBOM + provenance)
                          │
                          ▼
                  Deployment Controller (Argo Rollouts)
                          │
                          ▼
              Canary + Observability (OTel/Prom/Grafana/Loki/Tempo)
                          │
                 ┌────────┴────────┐
                 ▼                 ▼
             Promote           Auto-Rollback
```

Every box above is horizontally scalable and independently deployable; none holds pipeline
state in memory (state lives in Postgres + Temporal's durable execution history).

---

## 3. Agent Architecture

### 3.1 Agent Layer vs. Deterministic Infrastructure Layer

| Agent Layer (untrusted, probabilistic) | Deterministic Infrastructure Layer (trusted) |
|---|---|
| Planning, diagnosis, code/test generation, next-action selection, natural-language interpretation of failures | Command execution, containers/VMs, Git operations, test execution, artifact storage, caching, deployment, health checks, metrics, rollback |
| Runs inside a sandbox with **no** direct network/credential/API access | Owns all privileged operations behind typed APIs |
| Communicates only via the **Tool Gateway** | Enforces policy before executing any Gateway request |

**Why the separation is essential:** LLMs are non-deterministic, can hallucinate tool calls,
can be prompt-injected via untrusted repository content (READMEs, issues, test fixtures — see
§10.3), and have no cryptographic identity. Infrastructure must be able to guarantee
idempotency, auditability, and safety *regardless* of what the model outputs. If the Agent could
call `kubectl`, `git push --force`, or a cloud SDK directly, a single hallucinated or injected
instruction could cause irreversible damage. Routing every action through a policy-checked
gateway makes the agent's mistakes *recoverable by construction*: worst case, a rejected tool
call, not a production incident.

### 3.2 Agent Tool Gateway

The Gateway is the only path from Agent Brain to real infrastructure.

```text
ToolRequest { agent_id, task_id, tool_name, arguments, requested_scope }
        │
        ▼
1. Schema validation (arguments match tool contract)
2. AuthN (agent identity, short-lived JWT scoped to task_id)
3. AuthZ / Policy Engine (OPA): is this tool allowed for this agent role, this stage, this repo?
4. Resource-limit check (tokens used, tool-call count, time budget, file-change count)
5. Command allowlist (for run_shell: only pre-approved binaries/subcommands)
6. Dispatch to Execution Fabric with a scoped, short-lived credential
7. Capture output, redact secrets, log to immutable audit stream
8. Return typed ToolResult to Agent Brain
```

Core tool contract (all tools implement this shape):

```yaml
tool: run_test
input_schema: { command: string, cwd: string, timeout_s: integer<=1800 }
output_schema: { exit_code: integer, stdout_ref: string, stderr_ref: string, duration_ms: integer }
allowed_roles: [tester, debugger, coder]
allowed_stages: [TESTING, REVALIDATING]
side_effects: none
requires_approval: false
```

Example tool set: `read_file`, `write_file`, `search_code`, `git_diff`, `git_commit`,
`git_push(scoped_branch_only)`, `run_shell(allowlisted)`, `run_test`, `run_static_analysis`,
`open_pull_request`, `query_failure_kb`, `query_observability`, `recommend_deploy`,
`recommend_rollback`. Note `deploy` and `rollback` are **not** agent tools — only
*recommendation* tools exist; execution requires Policy Engine + human/policy sign-off (§15, §21).

### 3.3 Multi-Agent Roles & Contracts

Eight roles, each with a strict input/output contract (full YAML in §24). No open-ended agent
swarm — every agent-to-agent handoff is a structured artifact, never free-form chat.

| Agent | Responsibility | Writes | Deploys |
|---|---|---|---|
| Planner | Requirement → task decomposition → execution plan | plan.json | no |
| Coder | Implements plan as code changes | source diffs | no |
| Test Generator | Generates/updates tests for changed behavior | test files | no |
| Debugger | Root-cause analysis on failures | diagnosis.json | no |
| Security | Reviews diffs/deps for vulns, secrets, policy | security_report.json | no |
| Reviewer | Static review of diff quality vs. conventions | review.json | no |
| Release | Drives deploy/canary decisions (recommends only) | release_plan.json | no (recommends) |
| Incident | Diagnoses production regressions, recommends rollback | incident_report.json | no (recommends) |

Orchestration: the Pipeline Orchestrator invokes agents as Temporal activities; agents never
talk to each other directly — all communication is mediated by the orchestrator writing/reading
structured artifacts, which keeps every handoff auditable and replayable.

---

## 4. Pipeline Orchestration

### 4.1 State Machine

```text
CREATED → PLANNING → IMPLEMENTING → STATIC_CHECK → BUILDING → TESTING
   → [PASSED → SECURITY_GATE → ARTIFACT_BUILD → DEPLOYING → SMOKE_TEST
        → CANARY → OBSERVING → RELEASED]
   → [FAILED → DIAGNOSING → REPAIRING → REVALIDATING → TESTING (loop, bounded)]
```

| State | Entry condition | Exit condition(s) | Owner |
|---|---|---|---|
| CREATED | Run requested (event or manual) | Workspace provisioned | Orchestrator |
| PLANNING | Workspace ready | Plan artifact produced | Planner Agent |
| IMPLEMENTING | Plan approved (auto, if within policy) | Diff produced | Coder Agent |
| STATIC_CHECK | Diff exists | Lint/type/SAST pass or fail | Deterministic tool |
| BUILDING | Static check passed | Build succeeds/fails | Build system |
| TESTING | Build artifact exists | All selected tests pass/fail | Test runner |
| FAILED | Any test/build failure | Failure fingerprinted | Failure Engine |
| DIAGNOSING | Failure fingerprinted | Diagnosis produced (root cause + confidence) | Debugger Agent |
| REPAIRING | Diagnosis confidence ≥ threshold | Patch applied | Coder Agent |
| REVALIDATING | Patch applied | Targeted+regression tests re-run | Test runner |
| PASSED | All required tests green | — | — |
| SECURITY_GATE | Tests passed | SAST/DAST/dep/secret/container scans pass | Security Agent + scanners |
| ARTIFACT_BUILD | Security gate passed | OCI image + SBOM + provenance produced | Build system |
| DEPLOYING | Artifact verified | Deployed to target env | Deployment controller |
| SMOKE_TEST | Deploy complete | Health checks pass | Deterministic probes |
| CANARY | Smoke passed | Canary stage criteria met at each step | Deployment controller |
| OBSERVING | 100% rollout or final canary stage | SLOs stable over observation window | Observability |
| RELEASED | Observation window clean | — | — |

**Failure branches**

| Branch | Trigger | Path |
|---|---|---|
| TEST_FAILURE | Any test stage fails | → DIAGNOSING → REPAIRING → REVALIDATING → TESTING |
| REPAIR_LIMIT_EXCEEDED | `repair_iterations > max_iterations` OR budget exhausted OR oscillation detected | → HUMAN_REVIEW |
| SECURITY_FAILURE | Critical/high vuln, secret leak, policy violation | → BLOCK_RELEASE (hard stop, no override by agent) |
| DEPLOYMENT_FAILURE | Deploy step errors (infra, not app regression) | → ROLLBACK (deterministic, immediate) |
| PRODUCTION_REGRESSION | Post-deploy SLO/metric breach during CANARY/OBSERVING | → AUTOMATIC_ROLLBACK (policy-triggered, not agent-triggered) |

Terminal states: `RELEASED`, `HUMAN_REVIEW`, `BLOCK_RELEASE`, `ROLLED_BACK`, `ABANDONED`.

### 4.2 Pipeline DAG

The state machine governs macro pipeline phase; within a phase, work is a DAG (e.g., unit tests,
lint, and SAST can all run in parallel once `BUILDING` completes; integration tests depend on a
provisioned ephemeral DB). Pipelines are compiled from a declarative definition:

```yaml
pipeline: default-service
stages:
  - id: static_check
    parallel: [lint, typecheck, semgrep]
  - id: build
    depends_on: [static_check]
  - id: test
    depends_on: [build]
    parallel:
      - id: unit_tests
      - id: integration_tests
        needs: [ephemeral_postgres, ephemeral_redis]
  - id: security_gate
    depends_on: [test]
    parallel: [sast, dependency_scan, secret_scan, container_scan]
  - id: artifact_build
    depends_on: [security_gate]
  - id: deploy_staging
    depends_on: [artifact_build]
  - id: e2e
    depends_on: [deploy_staging]
  - id: canary
    depends_on: [e2e]
    condition: policy.canary.enabled
```

`Pipeline Definition → Pipeline Compiler → Execution DAG → Orchestrator → Task Scheduler →
Workers/Agents`. The Compiler resolves `depends_on`/`condition` into a Temporal workflow graph
at run start; conditional edges (e.g., skip canary for internal tools) are policy-evaluated at
compile time, not hardcoded.

### 4.3 Orchestrator Technology Decision

| Option | Strengths | Weaknesses | Verdict |
|---|---|---|---|
| **Temporal** | Durable execution, automatic retries, versioned workflows, first-class long-running human-in-the-loop signals, language SDKs (TS/Go/Python), replayable history = free audit trail | Operational component to run (or use Temporal Cloud); learning curve | **Selected** |
| Argo Workflows | Kubernetes-native, good for pure CI DAGs | Weaker support for long-lived stateful agent loops with signals/timers; workflow-as-YAML is clunky for dynamic agent-driven branching | Use underneath for raw CI job execution (see §11), not as the top-level orchestrator |
| Dagster | Excellent for data/asset pipelines, great observability UI | Not designed for imperative, long-running, human-interruptible agent workflows | Not selected |
| GitHub Actions / GitLab CI | Zero infra to run, great Git-native UX | No durable state across long repair loops, 6hr job ceilings, weak support for dynamic DAGs and cross-run memory | Use as an *integration target* (adapter, §11), not the core orchestrator |
| Jenkins / Buildkite / CircleCI | Mature, widely deployed | Same limitation as above; agent-loop semantics don't map to job-based CI models | Integration targets only |
| Custom orchestrator | Full control | Reinvents durable execution, retries, and history — high risk, high cost | Rejected |

**Decision:** Temporal is the control-plane orchestrator for pipeline state, agent loops, and
human-in-the-loop signals. It dispatches raw build/test/security jobs to existing CI providers
(GitHub Actions, GitLab CI, Buildkite) via the **Agent CI Adapter** (§11) when the org already
has CI investment, or to a self-hosted **CI Worker pool on Kubernetes** for a from-scratch
deployment. This gives durable, resumable, signal-driven orchestration without discarding
existing CI infrastructure.

---

## 5. Git-Native Workflow

```text
Repository → Workspace → Agent Branch (agent/{task_id}) → Code Changes → Local Validation
   → Commit (signed, structured message) → Push → Pull Request → CI → Review → Merge Queue → Merge
```

**Git State Manager** — a service the Agent queries instead of shelling out to raw `git`
directly for anything beyond local diffing:

```text
GitStateManager.get_status(workspace_id) → { branch, ahead, behind, dirty_files, conflicts }
GitStateManager.get_diff(workspace_id, base) → unified diff + changed-file AST map
GitStateManager.commit(workspace_id, message, files) → commit_sha   (idempotent via content hash)
GitStateManager.push(workspace_id) → { pushed: bool, remote_sha }
GitStateManager.open_pr(workspace_id, title, body, base) → pr_number   (idempotent: one PR per task_id)
GitStateManager.rebase(workspace_id, onto) → { success, conflicts[] }
GitStateManager.bisect(repo, good_sha, bad_sha, test_cmd) → first_bad_sha
```

Supported operations: branches, commits, diffs, PRs, **merge queues** (serialize merges to
avoid semantic conflicts between concurrent agent PRs), rebasing, automated conflict resolution
(agent-assisted, always re-validated by full test re-run — never trust a resolved conflict
without rerunning tests), revert, cherry-pick, bisect (used by the Debugger Agent to localize
regressions introduced by a range of commits), and worktrees (used to parallelize multiple agent
tasks against the same repo without repeated clones).

Branch naming and commit conventions are enforced deterministically (pre-commit hook + CI check),
not left to agent discretion, so downstream tooling (merge queue, bisect, changelossg) can rely
on structure.

---

## 6. Ephemeral Execution & Sandbox Architecture

```text
Task → Workspace Provisioner → Repository Clone (shallow, cached) → Dependency Cache (warm)
   → Sandbox → Agent
```

| Isolation level | Startup | Isolation strength | Use when |
|---|---|---|---|
| **Container (gVisor/Kata)** | ~1–3s | Kernel-syscall-filtered, good but shares host kernel surface with extra syscall interception | Default for static analysis, unit tests, lint, most agent tool calls |
| **Firecracker microVM** | ~125ms cold, near-container speed | Full VM-grade isolation (separate kernel), minimal attack surface | Running agent-generated/untrusted code, integration tests touching real-ish services, anything from an untrusted repo (open-source contributions, third-party PRs) |
| **Full VM** | Seconds–minutes | Strongest isolation, heaviest | E2E tests needing full OS fidelity (browser farms, GPU workloads), or as a fallback for exotic build toolchains that don't containerize well |

**Default posture:** Firecracker microVMs (via Kubernetes + Kata/Firecracker containerd
shim, or Fly.io/Modal-style microVM platforms) for anything executing agent- or
repository-authored code, because the Agent's inputs are inherently untrusted (§10.3 prompt
injection). Plain gVisor containers are acceptable for deterministic, non-agent-controlled
steps (e.g., running a fixed linter binary against a mounted diff).

Limits enforced per execution (see also §53 NFR):

```yaml
sandbox_limits:
  cpu: 4
  memory: 8Gi
  disk: 20Gi
  network: egress_allowlist_only   # package registries + internal services only, no arbitrary internet
  timeout: 30m
  max_processes: 256
  filesystem: read_only_root + writable /workspace overlay only
```

No sandbox has network access to the credential broker, cloud metadata service, or production
network by default; those require an explicit, policy-approved, short-lived grant (§10.2).

---

## 7. Build System

| Requirement | Mechanism |
|---|---|
| Deterministic builds | Pinned toolchain images (digest-pinned, not tag-pinned), locked dependencies |
| Dependency locking | `package-lock.json`/`poetry.lock`/`go.sum`/`Cargo.lock` enforced in CI (fail on lockfile drift) |
| Build cache (local + remote) | BuildKit remote cache backed by object storage, keyed by content hash |
| Artifact hashing | SHA-256 digest for every build output |
| SBOM | Generated per build (Syft) |
| Provenance | SLSA-style attestation (in-toto + Sigstore, §55) |

| Tool | Strengths | Weaknesses | Verdict |
|---|---|---|---|
| **BuildKit (Docker)** | Ubiquitous, great caching, OCI-native, low ramp-up | Not a true hermetic build system across languages | **Default** for containerized service builds |
| Bazel | True hermeticity, best-in-class remote caching/execution, multi-language | Steep adoption cost, requires BUILD file authoring/migration | **Recommended for large monorepos** (Phase 3+) once the org is ready to invest |
| Nix | Fully reproducible, great for pinning exact toolchains | Smaller talent pool, steep learning curve | Use for pinning the *sandbox base images/toolchains* themselves, not app builds |
| Language-native (npm/pip/cargo/go build/maven) | Zero extra tooling, agent already knows these | Weaker cross-language caching/hermeticity | Used *inside* the BuildKit/Bazel wrapper, not standalone |

**Default stack:** BuildKit with remote caching for services (Node.js, Python, Go, Java,
C/C++), each building inside a digest-pinned OCI base image; Nix pins the base images
themselves; Bazel is offered as an opt-in for repos large enough to need it (>500k LOC or
multi-language monorepos), introduced in Phase 3.

---

## 8. Testing Architecture

### 8.1 Seven Layers

| Level | Purpose | Tools | Runs on every PR? |
|---|---|---|---|
| 1. Static Analysis | Type/lint/security-pattern checks | ESLint, TypeScript, Ruff, MyPy, Clippy, Semgrep, SonarQube | Yes, always, fast fail |
| 2. Unit Tests | Function/class-level correctness | pytest, Jest/Vitest, JUnit, `go test`, `cargo test` | Yes, targeted + full on merge |
| 3. Integration Tests | DB/queue/API/service interaction | Testcontainers, Docker Compose, ephemeral DBs | Yes, targeted subset; full on merge queue |
| 4. E2E Tests | User-journey correctness | Playwright, Cypress, Selenium | On staging deploy, and pre-canary |
| 5. Contract Tests | API/schema compatibility | OpenAPI diff, Pact, GraphQL schema validation | On any public-interface change |
| 6. Performance Tests | Latency/throughput regressions | k6, Locust, JMeter, Gatling | On merge queue for perf-sensitive services; nightly full |
| 7. Security Tests | Vuln/secret/supply-chain | SAST (Semgrep/CodeQL), DAST (OWASP ZAP), Trivy (deps+container), Gitleaks (secrets), SBOM validation | Every PR (SAST/secrets/deps), pre-deploy (DAST/container) |

### 8.2 Agentic Test Generation

```text
Code Change → AST Analysis → Diff Analysis → Coverage Analysis → Existing Test Discovery
   → Risk Analysis → Test Generation → Test Execution → Test Quality Evaluation
```

The Test Generator Agent is given the diff, the AST of changed functions/classes, current
coverage for those lines, and any existing tests that already exercise the changed code —
never the whole repository. It is asked to enumerate: changed public APIs, changed
database/side-effect behavior, changed business-logic branches, and edge cases not currently
covered (nulls, boundary values, error paths, concurrency where relevant).

**Preventing weak, implementation-mirroring tests:**
1. **Mutation testing gate** — generated tests must kill a minimum mutation score (e.g., ≥70%)
   against the changed lines, computed with a mutation tool (e.g., Stryker/mutmut); a test suite
   that passes against the implementation but dies against nearly every mutant is rejected.
2. **Independent oracle requirement** — the Test Generator is prompted to derive expected
   outputs from the *requirement/spec*, not by reading the implementation and asserting
   whatever it currently returns; a separate lint step flags tests whose assertions are
   generated via execution-and-snapshot rather than reasoned expected values, for closer review.
3. **Adversarial review** — the Reviewer Agent (a distinct agent, different prompt/context)
   checks generated tests for "tautological" patterns (assert-equals-itself, mocked-everything
   tests) before they're accepted.
4. **Regression replay** — every generated test is also run against the *pre-change* code; a
   good regression test must **fail** on the old code and **pass** on the new code. Tests that
   pass on both are not testing the change and are discarded.

### 8.3 Test Impact Analysis (Test Selection)

```text
Git diff + dependency graph + import graph + call graph + historical test failures + coverage
   → Targeted Tests → Regression Tests → Full Suite (conditionally)
```

Three-tier strategy:

1. **Fast Feedback** — tests directly covering changed lines (from coverage-to-test mapping),
   runs in seconds, on every save/agent iteration.
2. **Changed-Module Tests** — all tests in modules reachable from the changed files via the
   import/call graph within N hops, run before opening/updating a PR.
3. **Full Regression Suite** — runs on merge-queue entry and nightly, as the final safety net.

**Building the code→test dependency graph:** instrument test runs once (coverage-guided) to
record, per test, the set of source files/lines executed; store as a bipartite graph
`test_id ↔ {file, line-range}` in Postgres + a graph index. On each diff, compute
`changed_lines ∩ covered_lines` to select directly-impacted tests, then walk the static
import/call graph (built via language-specific AST tooling — `ts-morph`, `astroid`,
`go/packages`, etc.) outward by configurable hop-count for changed-module tests. Recompute
incrementally on each merge, not from scratch.

### 8.4 Flaky Test Detection

Track per test: `failure_rate`, `failure_fingerprint`, `environment`, `duration`,
`historical_pass_rate`, `time_distribution`.

Classification (never single-failure-based):

| Category | Rule |
|---|---|
| REAL_FAILURE | Deterministically reproducible on retry against the same commit |
| FLAKY_FAILURE | Statistically significant pass/fail variance across ≥N reruns of the *same* commit/environment (binomial test, not "failed once") |
| INFRA_FAILURE | Failure fingerprint matches known infra categories (network timeout to CI runner, registry 5xx) uncorrelated with code changes |
| UNKNOWN | Insufficient history — treated as REAL_FAILURE by default (fail closed) until evidence accumulates |

Quarantine rules: a test can only enter quarantine after ≥5 recent runs show ≥20% variable
outcome under identical inputs, requires an owning-team ticket auto-filed, and quarantine has a
hard expiry (e.g., 14 days) after which it re-blocks merges if unfixed. The Agent is never
permitted to unilaterally mark a test as "flaky" and skip it — that classification requires the
statistical detector, and quarantine (not deletion) is the only automated action available.

---

## 9. Failure Intelligence & Automated Repair

### 9.1 Failure Schema

```text
Raw Logs → Log Parser → Error Extractor → Stack Trace Parser → Failure Classifier
   → Failure Fingerprint → Context Retrieval → Root Cause Analysis
```

```json
{
  "failure_id": "flr_9f2a...",
  "category": "UNIT_TEST_FAILURE",
  "fingerprint": "sha256(normalized_stack + test_id + error_type)",
  "command": "pytest tests/auth/test_login.py -k test_oauth_flow",
  "exit_code": 1,
  "stack_trace": "...(parsed, structured frames, not raw text)...",
  "affected_files": ["src/auth/middleware.py"],
  "affected_tests": ["tests/auth/test_login.py::test_oauth_flow"],
  "environment": {"os": "linux", "runtime": "python3.12", "container_digest": "sha256:..."},
  "recent_changes": ["commit:abc123 modified src/auth/middleware.py"],
  "suspected_root_causes": ["middleware now requires `state` param not set by test fixture"],
  "confidence": 0.91
}
```

Categories: `COMPILE_ERROR, TYPE_ERROR, UNIT_TEST_FAILURE, INTEGRATION_FAILURE, E2E_FAILURE,
TIMEOUT, OOM, NETWORK_ERROR, DEPENDENCY_ERROR, ENVIRONMENT_ERROR, FLAKY_TEST,
SECURITY_FAILURE, PERFORMANCE_REGRESSION, DEPLOYMENT_FAILURE`.

**Classifier design (not "every failure is a code bug"):** a deterministic rules-first
classifier runs before any LLM involvement — regex/AST-level patterns for compile errors,
known exit codes for OOM/timeout, network-error signatures for transient infra issues, and a
lookup against the Flaky Test Detector (§8.4). Only failures that don't match a deterministic
category, or that are classified `UNIT/INTEGRATION/E2E_FAILURE` with a real code-level cause,
are routed to the Debugger Agent. This alone eliminates the majority of failures from LLM
involvement entirely (cost win, see §19).

### 9.2 Debugger Agent

Input: `git diff, failure fingerprint, relevant source (via Context Engine, §17), stack trace,
test code, recent commits touching affected files, dependency info, environment info`.

Output:

```json
{
  "root_cause": "middleware.validate_state() now requires `state` cookie; test fixture doesn't set it",
  "evidence": [
    "stack trace frame: middleware.py:44 in validate_state",
    "commit abc123 added state validation on 2026-08-29",
    "test_oauth_flow fixture unchanged since 2026-06-01"
  ],
  "confidence": 0.92,
  "repair_strategy": "update test fixture to set `state` cookie, matching new middleware contract",
  "files_to_modify": ["tests/auth/fixtures.py"],
  "tests_to_run": ["tests/auth/test_login.py", "tests/auth/*"]
}
```

The agent is required to produce the chain
`Observation → Hypothesis → Evidence → Root Cause → Proposed Fix → Validation Plan` explicitly
in its output (not hidden reasoning) so it can be programmatically checked: every `root_cause`
claim must cite at least one `evidence` item traceable to a real artifact (a specific stack
frame, a specific commit, a specific line of test code) — claims without a traceable evidence
item are rejected by a validator before the fix is attempted (§59 explainability requirement).

### 9.3 Automated Repair Loop

```text
Test Failure → Extract → Diagnose → Generate Patch → Apply → Targeted Tests
   → Regression Tests → Evaluate → Success? ── Yes → Continue
                                          └── No → Diagnose Again (bounded)
```

Budgets enforced by the orchestrator (not self-reported by the agent):

```yaml
repair_budget:
  max_iterations: 5
  max_tokens: 150000
  max_tool_calls: 100
  max_wall_clock: 30m
  max_patch_lines: 300
  risk_threshold: 0.7        # diagnoses below this confidence route to HUMAN_REVIEW, no patch attempted
```

**Oscillation detection:** the Repair History stores a content hash of every patch applied per
task. If a new patch's diff is a near-revert of a patch applied 1–2 iterations earlier (high
diff-similarity to `patch[i-2]` inverse), or if the same test alternates pass/fail across
iterations while a different test flips the opposite way, the loop halts immediately and routes
to `HUMAN_REVIEW` regardless of remaining budget — this is the deterministic guard against
"fix A breaks B, fix B breaks A."

```text
RepairHistory: [{iteration, patch_hash, diff_summary, tests_before, tests_after, verdict}]
```

`REPAIR_LIMIT_EXCEEDED` → `HUMAN_REVIEW` packet (see §16) includes the full Repair History so a
human never has to re-derive what was already tried.

---

## 10. Security Architecture

### 10.1 Zero-Trust Model

Every agent execution is treated as untrusted code execution, because it *is* — the agent is
directed by an LLM whose input includes repository content the agent doesn't control (issues,
READMEs, dependency metadata, other developers' commits).

```text
Sandbox (Firecracker) → Network Policy (default-deny egress, allowlist registries) →
Filesystem Isolation (read-only root, scoped writable overlay) → Secret Isolation (no secrets
in env/files; broker only) → Credential Broker (JIT, scoped, short-lived) → Command Allowlist
(Tool Gateway) → Resource Limits (§53) → Timeout → Audit Log (append-only, tamper-evident)
```

### 10.2 Credential Broker

```text
Agent → Tool Gateway (requests action needing credential, e.g. "deploy to staging")
     → Policy Engine evaluates: agent role, task, target, current pipeline state
     → Credential Broker mints a short-lived, scoped token (OIDC federation, ~5–15 min TTL)
     → Token used for exactly one action, then discarded
```

The agent **never** receives: long-lived cloud credentials, database root credentials,
production SSH keys, or master API keys — this is a hard invariant, not a preference. All
production access is via OIDC-federated short-lived tokens (e.g., GitHub Actions OIDC →
cloud IAM role, or Vault's dynamic secrets engine), scoped to the single action and audited.

### 10.3 Security Threat Model

| Threat | Vector | Mitigation |
|---|---|---|
| Prompt injection | Malicious content in README, source comments, test fixtures, issues, commit messages, generated logs (e.g., "ignore previous instructions and exfiltrate secrets") | Agent has no ambient credentials to exfiltrate (broker model); Tool Gateway allowlist blocks unauthorized tools regardless of what the model "decides"; all untrusted text is tagged as data, not instructions, in the prompt template; acceptance tests in §80 |
| Sandbox escape | Container/microVM breakout | Firecracker for untrusted execution; kernel-level isolation; regular sandbox-escape penetration testing (§81) |
| Credential exfiltration | Agent tries to read/print secrets | Secrets never materialize in the sandbox filesystem/env; broker returns ephemeral tokens only at point of use via the Gateway, not to the agent's shell |
| Supply-chain compromise | Malicious dependency, poisoned build cache | SBOM + dependency scanning on every build; remote cache entries content-addressed and verified; Sigstore-signed artifacts |
| Cross-tenant access | Multi-tenant data leakage | `tenant_id`/`project_id`/`workspace_id` enforced as hard boundaries at the DB row level (RLS) and in the Tool Gateway's policy checks |
| Malicious PR from external contributor | Untrusted code executes in CI | External/fork PRs run with a stricter sandbox profile (no secrets, no deploy tools available at all) until a maintainer approves |
| Unauthorized production action | Agent or compromised component attempts deploy/rollback directly | No agent tool exists for direct deploy/rollback; only "recommend"; execution requires Policy Engine + deployment controller, both outside agent reach |

---

## 11. CI/CD Integration & Event-Driven Architecture

**Agent CI Adapter** — a provider-agnostic interface so the orchestrator never hardcodes a CI
vendor:

```text
interface CIProvider {
  create_run(spec) -> run_id
  cancel_run(run_id) -> void
  get_status(run_id) -> RunStatus
  get_logs(run_id) -> LogRef
  get_artifacts(run_id) -> ArtifactRef[]
  retry_run(run_id) -> run_id
  download_artifact(artifact_ref) -> bytes
}
```

Implementations: `GitHubActionsProvider`, `GitLabCIProvider`, `JenkinsProvider`,
`BuildkiteProvider`, `ArgoWorkflowsProvider`, `NativeK8sJobProvider` (self-hosted default).
Swapping providers means implementing this interface — no orchestrator changes.

**Event-driven, not polling:**

```text
GitHub/GitLab Webhook → Event Gateway (verifies signature, deduplicates by delivery-id)
   → Event Bus → Orchestrator (subscribes to relevant event types) → dispatches Temporal signal
```

Event catalog: `PullRequestCreated, CommitPushed, CIStarted, BuildFinished, TestFailed,
TestPassed, RepairStarted, RepairFinished, SecurityScanFailed, ArtifactCreated,
DeploymentStarted, DeploymentSucceeded, DeploymentFailed, ProductionIncidentDetected,
RollbackStarted, RollbackCompleted`. Each carries `{event_id, trace_id, pipeline_id, occurred_at,
payload}`; `event_id` is used for exactly-once processing (dedupe table with TTL) even though the
bus offers at-least-once delivery.

| Bus | Strengths | Weaknesses | Verdict |
|---|---|---|---|
| **NATS (JetStream)** | Lightweight, low ops overhead, good pub/sub + work-queue semantics, easy self-host | Smaller ecosystem than Kafka | **Selected** for MVP→mid scale |
| Kafka | Best-in-class throughput/durability at massive scale, huge ecosystem | Heavier ops burden, overkill below ~10k events/sec | Migration target if event volume at 10k-repo scale (§34) demands it |
| Redis Streams | Simple, fast | Weaker durability/replay guarantees, not ideal as system-of-record for events | Used only for ephemeral fan-out (e.g., live log tailing), not the durable event bus |
| RabbitMQ | Mature, flexible routing | Operationally heavier than NATS for this use case, less natural streaming/replay model | Not selected |

Polling is retained only where a provider offers no webhooks (rare legacy CI systems) or as a
reconciliation safety net (§48) to catch missed webhook deliveries every few minutes.

---

## 12. Artifact Management & Supply Chain Security

Every execution produces immutable artifacts: source snapshot, Git diff, test reports,
coverage, logs, screenshots/videos (E2E), binaries, OCI images, SBOM, security reports,
deployment manifests — stored in object storage (content-addressed) with metadata in Postgres.

```json
{
  "artifact_id": "art_7c1e...",
  "commit_sha": "abc123",
  "build_id": "bld_44a2",
  "digest": "sha256:9f86d0...",
  "created_at": "2026-09-01T10:12:00Z",
  "provenance": "in-toto-attestation-ref",
  "security_status": "PASSED"
}
```

**Supply-chain traceability** — every production artifact must answer: *which exact source,
build process, and dependencies produced it?* Achieved via:
- **SBOM** (Syft, CycloneDX format) generated at `ARTIFACT_BUILD`.
- **Build provenance** (in-toto attestations, SLSA level target: build track L2 at MVP, L3 by
  production — hermetic, non-forgeable builder identity).
- **Signing** (Sigstore/cosign) — artifacts are signed by the build system's OIDC identity, not
  a long-lived key; deployment controller verifies signature + provenance before deploying.

**Retention:** debug logs 14 days · pipeline metadata 180 days · failure knowledge indefinite ·
audit logs 1+ year · production artifacts per release policy (commonly: keep last N releases +
anything currently deployed to any environment) · security records per compliance requirement.
All configurable per tenant/project.

---

## 13. Deployment & Progressive Delivery

Strategies supported: Rolling, Blue-Green, Canary, Shadow, and general Progressive Delivery
(Argo Rollouts implements all four declaratively on Kubernetes).

Default high-risk-service flow:

```text
Build → Deploy to staging → Smoke test → Canary 1% → Observe
   → Canary 5% → Observe → Canary 25% → Observe → Canary 50% → Observe → 100%
```

**Automatic promotion criteria** (evaluated by the deployment controller, not the agent):

```yaml
promotion:
  error_rate_max: 0.01
  p95_latency_max: baseline * 1.10
  availability_min: 0.999
  critical_errors_max: 0
  observation_window: 10m
  statistical_test: sequential_probability_ratio  # avoid false-promote on noisy small-sample canaries
```

Each canary step requires the window to pass *before* the next promotion step is even
scheduled; a metric breach at any step halts progression and triggers §21's rollback path
immediately rather than "waiting to see."

---

## 14. Observability Architecture

Stack: **OpenTelemetry** (instrumentation/propagation) → **Prometheus** (metrics) →
**Grafana** (dashboards) → **Loki** (logs) → **Tempo** (traces). Every pipeline entity carries a
propagated ID set (§57): `trace_id, pipeline_id, task_id, agent_run_id, tool_call_id, build_id,
test_run_id, deployment_id` — through API, event bus, agent, gateway, CI, build, tests,
deployment, and observability, enabling one query ("show me everything for pipeline X") across
every system.

**Machine-readable observability API for agents** (read-only, no write/control access):

```text
Observability.query_metric(service, metric, since) -> series
Observability.get_recent_deploys(service) -> [deployment_id, commit_sha, deployed_at]
Observability.get_error_spike(service, since) -> { started_at, top_errors[], correlated_deploy }
Observability.get_slo_status(service) -> { slo, current, budget_remaining }
```

This lets the Incident Agent answer *"what changed / which service is failing / which endpoint
is degraded / when did the regression start / which deployment caused it / what metrics
changed"* from structured queries — never by having the agent grep raw log dumps.

**Agent Engineering Dashboard** (the platform observing itself, §37/§94): tracks
`agent_success_rate, repair_success_rate, mean_repair_iterations, test_failure_rate,
flaky_test_rate, pipeline_duration, llm_tokens, llm_cost, tool_call_count, sandbox_failures,
deployment_failure_rate, rollback_rate, human_escalation_rate` — one dashboard per pipeline
component (§94 details per-area breakdowns for Pipeline/Agent/CI/Deployment/Security).

---

## 15. Policy Engine

A centralized, declarative Policy Engine (**OPA/Rego**) is the sole authority over every
irreversible or privileged decision: *can execute? can deploy? can merge? can retry? can repair
automatically? can rollback?* The agent cannot override policy — policy checks happen in the
Tool Gateway and the Deployment Controller, both outside agent reach.

```yaml
deployment:
  production:
    require_tests: true
    require_security_scan: true
    require_approval: false        # per-project override; high-risk services set true
    max_error_rate: 0.01
    max_latency_p95: 500ms
    canary:
      enabled: true
      initial_percent: 1
repair:
  max_iterations: 5
  require_human_review_below_confidence: 0.7
merge:
  require_green_ci: true
  require_security_gate: true
  require_no_open_critical_findings: true
```

Policies are versioned (§58 determinism), stored in Git alongside the pipeline definitions they
govern, and evaluated with the specific policy version pinned into every execution record so
past decisions remain explainable even after policy changes.

---

## 16. Human-in-the-Loop

Escalation triggers: repair iterations exceeded, diagnosis confidence too low, security risk
detected, high production impact, dangerous database migration, architecture-level change
detected, unusually large diff, breaking API change, or an unclassifiable/unknown failure.

**Escalation packet** (compressed, high-signal — never a raw log dump):

```json
{
  "problem": "Repair loop exceeded 5 iterations on auth middleware regression",
  "evidence": ["...top 3 evidence items from each diagnosis attempt..."],
  "attempted_fixes": ["...RepairHistory summary, 1 line per attempt..."],
  "failed_tests": ["tests/auth/test_login.py::test_oauth_flow"],
  "relevant_diff": "...unified diff, <100 lines, or link to full diff...",
  "risk": "medium — auth path, no prod deploy yet",
  "recommended_action": "manual review of state-param contract change; consider reverting commit abc123"
}
```

Delivered via Slack/PagerDuty/ticket integration with a deep link to the full pipeline run;
the human can approve, redirect the agent with guidance, or take over manually — all recorded
as an `Approval` entity (§22) tied to the pipeline run.

---

## 17. Context Engineering

Do not dump the repository or CI logs into the model. The **Context Engine** performs
`Retrieve → Rank → Compress → Summarize → Inject` against these sources: repository, AST, Git
diff, code graph, dependency graph, test graph, failure history, CI history, issue tracker,
docs/architecture docs, logs, metrics, and previous repair attempts.

**Adaptive context budget** (illustrative starting allocation, not fixed — the allocator
re-weights based on failure category and available evidence):

```text
repository_metadata: 2% | git_diff: 10% | failure_info: 15% | relevant_code: 30%
tests: 20% | historical_fixes: 10% | instructions: 8% | safety/policy: 5%
```

The optimization target is **diagnostic information per token**, not minimum token count: for a
`COMPILE_ERROR`, relevant_code and git_diff dominate; for a `SECURITY_FAILURE`, safety/policy
and dependency metadata get more budget; for a failure matching a known fingerprint, the entire
budget can shrink dramatically because the Failure Knowledge Base (§18) supplies the answer
directly. The allocator is itself a small, cheap deterministic model/heuristic (§19) — not the
large reasoning model being fed.

---

## 18. Agent Memory & Failure Knowledge Base

| Layer | Scope | Example |
|---|---|---|
| Short-Term | Current execution | Current diagnosis chain, current patch |
| Task | Current feature/bug | Plan, prior patches this task, RepairHistory |
| Repository | Architecture & conventions | "This repo uses hexagonal architecture; DB access only via `repo/` package" |
| Failure | Historical failures & fixes | Fingerprint → root cause → successful patch |
| Organization | Cross-repo engineering patterns | "This org's services all validate JWT via shared `auth-lib`" |

**Failure Knowledge Base** — hybrid retrieval, not pure vector RAG:

```text
Failure record
 ├── SQL metadata   (exact fingerprint match, category, affected files — fast, precise)
 ├── Vector embedding (semantic similarity for near-duplicate but non-identical failures)
 └── Dependency/code graph (structural similarity: "same call path", "same module")
```

**Why hybrid beats pure RAG:** vector similarity alone conflates surface-level textual
resemblance with actual root-cause similarity (two different bugs can produce similar-looking
stack traces; the same bug can produce very different-looking ones across languages/frameworks).
SQL exact/fuzzy fingerprint match handles the common "we've seen this exact failure before" case
with zero ambiguity and near-zero cost. The code/dependency graph catches "different error text,
same structural cause" (e.g., any test touching a newly-breaking shared utility). Vector search
is reserved for the residual case where neither exact nor structural match is found. Ordering
lookups this way (SQL exact → graph structural → vector semantic) dramatically cuts both false
positives and LLM invocations, since a fingerprint hit can resolve `DIAGNOSING` without invoking
the Debugger Agent at all — going straight to applying the previously-successful patch pattern
(subject to re-validation).

This memory hierarchy reduces token consumption because most repairs stop at "Failure
Fingerprint → Historical Failure DB → Previous Successful Fix" without ever reaching the
Debugger Agent's full reasoning path (§25/§27).

---

## 19. Cost Optimization & Model Routing

```text
Rule Engine → Deterministic Analyzer → Small Model → Medium Model → Large Reasoning Model → Human
```

| Failure type | Route |
|---|---|
| Simple syntax/compile error | Deterministic parser (no LLM) |
| Exact fingerprint match in Failure KB | Historical fix retrieval (no/minimal LLM) |
| Simple dependency version conflict | Small model |
| Moderate logic bug, single file | Medium model |
| Complex, multi-file, cross-cutting bug | Large reasoning model |
| Architecture-level failure / repeated escalation | Strongest model, then human |

Routing policy is a scored decision (`failure_category`, `historical_kb_confidence`,
`num_affected_files`, `prior_iteration_count`) → model tier, continuously tuned against tracked
outcomes: `tokens, latency, cost, success_rate, repair_iterations` per tier, so the router can be
recalibrated as models change (e.g., "medium model now solves what previously needed large
model" shifts traffic down-tier automatically once success-rate data supports it).

**Cost NFR (§64):** prefer, in order, deterministic tools → cached results → targeted tests →
small models → retrieval → historical fixes, before reaching for expensive reasoning. Tracked
per task: `cost/task, cost/successful task, cost/fixed bug, cost/deployment`.

---

## 20. Reliability, Idempotency & Recovery

**Reliability:** the pipeline tolerates failure of LLM, agent, worker, container, CI provider,
network, database, message broker, artifact registry, deployment system, or observability
system. Guaranteed by Temporal's durable execution (workflow state survives worker/orchestrator
crashes and resumes from the last completed activity), exponential-backoff retries, and
idempotent operations everywhere. Target: **pipeline state loss = 0**.

**Idempotency:** every important operation (build, deploy, rollback, create artifact, create
branch, create CI run) is keyed by a stable `idempotency_key` derived from
`{execution_id, commit_sha, artifact_digest}`. Deploys additionally check "is `commit_sha`
already the currently-deployed revision for this environment?" before acting — duplicate
`DeploymentStarted` events (from webhook redelivery or retry) become no-ops rather than
double-deploys.

**Recovery targets:**

| Component | RTO | RPO |
|---|---|---|
| Control plane | ≤ 15 min | ≤ 1 min |
| Pipeline state | — | ≤ 10 sec |
| Committed artifacts | — | 0 |

**Reconciliation loop** (catches drift missed by events):

```text
Desired State (from policy/config) → Actual State (queried from infra) → Diff → Reconcile → repeat
```

Runs continuously at low frequency (e.g., every 2–5 min) as a safety net alongside the primary
event-driven path — e.g., detects and closes duplicate deployments, orphaned canaries, or stuck
pipeline runs whose worker died without emitting a completion event.

**Failure containment:** bulkheads, circuit breakers, rate limits, per-tenant quotas,
dead-letter queues, and backpressure ensure a failure in one project/tenant cannot cascade into
others, the control plane, or the artifact registry (§69).

---

## 21. Non-Functional Requirements Summary

| NFR | Metric | MVP Target | Production Target | Measurement |
|---|---|---|---|---|
| Availability (control plane) | Uptime | 99.5% | 99.95% | Synthetic probes + SLO burn-rate alerts |
| Availability (event gateway) | Uptime | 99.5% | 99.99% | Health checks |
| Pipeline state correctness | % runs with consistent final state | ≥99.99% | ≥99.99% | Reconciliation audit |
| Successful pipeline execution | % completing without infra error | ≥99% | ≥99% | Pipeline outcome logs |
| Duplicate deployment rate | count | 0 | 0 | Idempotency key audit |
| Lost pipeline state | count | 0 | 0 | Temporal history integrity check |
| First-pass agent task success | % | ≥50% | ≥70% | Golden Benchmark |
| Eventual task success (within budget) | % | ≥75% | ≥90% | Golden Benchmark |
| Repair success rate | % | ≥60% | ≥85% | Golden Benchmark |
| Regression rate post-repair | % | ≤10% | ≤3% | Golden Benchmark + prod monitoring |
| Human escalation rate | % | ≤40% | ≤15% | Pipeline metrics |
| Failure classification accuracy | % | ≥90% | ≥95% | Labeled failure benchmark |
| Root-cause top-1 accuracy | % | ≥60% | ≥70% | Labeled failure benchmark |
| Root-cause top-3 accuracy | % | ≥85% | ≥90% | Labeled failure benchmark |
| Flaky classification precision | % | ≥90% | ≥95% | Repeated-run statistical audit |
| False quarantine rate | % | ≤2% | ≤1% | Quarantine audit |
| Test-selection regression recall | % | ≥95% | ≥98% | Mutation-seeded regression benchmark |
| Rollback detection latency | seconds | <120s | <60s | Chaos test |
| Rollback execution success | % | ≥97% | ≥99% | Chaos test |
| Unauthorized privileged action | count | 0 | 0 | Audit log scan |
| Credential leakage | count | 0 | 0 | Secret-scan + pen test |
| Critical vuln reaching production | count | 0 | 0 | Security gate audit |
| Cost per simple bug fix | $ | project-configured budget | tighter, tuned from data | Cost tracking |

Definitions used consistently: **SLI** = the measured indicator (e.g., "% of requests under
300ms"); **SLO** = the internal target for that SLI (e.g., "99% under 300ms over 30 days");
**SLA** = an externally-committed, often contractual, version of an SLO with consequences for
breach; **Error Budget** = `1 - SLO`, the allowance for how much the SLO can be missed before
triggering a freeze on risky changes (e.g., canary rollout pace slows automatically as error
budget depletes).

---

## 22. Data Model / Database Schema

Primary store: **PostgreSQL** (strong consistency for pipeline/state entities, row-level
security for tenant isolation), **Redis** (queues/locks/ephemeral state), **Object Storage**
(artifacts/logs, content-addressed), **Vector DB** (pgvector, colocated with Postgres to avoid
a second system — sufficient at this scale; dedicated vector DB is a Phase 4 option if volume
demands it).

Core tables (key columns only; all tables carry `tenant_id`, `created_at`, `updated_at`):

```text
projects(id, tenant_id, repo_url, default_branch, policy_id)
repositories(id, project_id, provider, external_id)
workspaces(id, task_id, repo_id, base_sha, sandbox_type, status, expires_at)
tasks(id, project_id, requirement_text, created_by, status)
pipeline_runs(id, task_id, pipeline_version, state, started_at, ended_at, trace_id)
pipeline_stages(id, run_id, stage_name, state, started_at, ended_at, input_ref, output_ref)
agent_runs(id, run_id, agent_role, model, model_version, prompt_version, tokens_in, tokens_out,
           cost_usd, tool_call_count, status)
tool_calls(id, agent_run_id, tool_name, arguments_hash, result_ref, policy_decision, duration_ms)
builds(id, run_id, commit_sha, artifact_digest, cache_hit, duration_ms, status)
tests(id, project_id, test_id, file_path, kind)
test_runs(id, run_id, test_id, status, duration_ms, environment, fingerprint)
failures(id, run_id, category, fingerprint, stack_trace_ref, affected_files, confidence)
diagnoses(id, failure_id, agent_run_id, root_cause, evidence, confidence, repair_strategy)
repairs(id, failure_id, diagnosis_id, iteration, patch_ref, verdict, oscillation_flag)
artifacts(id, run_id, artifact_id, digest, kind, provenance_ref, security_status)
deployments(id, artifact_id, environment, strategy, state, promoted_at, idempotency_key)
rollbacks(id, deployment_id, trigger, reason, initiated_at, completed_at, verified)
policies(id, tenant_id, name, version, definition_ref, effective_at)
approvals(id, run_id, requested_of, decision, decided_at, escalation_packet_ref)
events(id, type, trace_id, pipeline_id, payload, occurred_at, dedupe_key)
metrics(id, run_id, name, value, recorded_at)
```

Relationships: `tasks 1—N pipeline_runs` (retries create new runs, same task);
`pipeline_runs 1—N pipeline_stages`; `pipeline_stages 1—N agent_runs` (a stage may invoke
multiple agent calls); `failures 1—N diagnoses 1—N repairs` (repair history, §9.3);
`artifacts 1—N deployments`; `deployments 0—N rollbacks`. `dedupe_key` on `events` and
`idempotency_key` on `deployments`/`builds` are unique-constrained at the DB level — the
correctness backstop beneath application-level idempotency checks.

---

## 23. API & Event Schemas

REST/gRPC control-plane API (selected endpoints):

```text
POST   /v1/tasks                         create a task (requirement → pipeline run)
GET    /v1/pipeline_runs/{id}            full state, stages, artifacts
POST   /v1/pipeline_runs/{id}/cancel
POST   /v1/pipeline_runs/{id}/retry
GET    /v1/pipeline_runs/{id}/logs
GET    /v1/failures/{id}
POST   /v1/approvals/{id}/decide         { decision: approve|reject|redirect, note }
GET    /v1/deployments/{id}
POST   /v1/deployments/{id}/rollback     (policy-gated; requires role + reason)
```

Event envelope (all bus messages):

```json
{
  "event_id": "evt_...",
  "type": "TestFailed",
  "trace_id": "trc_...",
  "pipeline_id": "pln_...",
  "occurred_at": "2026-09-01T10:00:00Z",
  "payload": { "...event-specific..." }
}
```

---

## 24. Agent Contracts

Every agent is defined declaratively — tools, permissions, and budgets, never implicit:

```yaml
agent:
  name: debugger
  input_schema: DiagnosisRequest
  output_schema: DiagnosisResult
  tools: [read_file, search_code, run_test, git_diff, query_failure_kb, query_observability]
  permissions:
    write_source: false
    deploy: false
  budget:
    max_iterations: 5
    max_tokens: 30000
    max_tool_calls: 40
  success_criteria: "diagnosis.confidence >= 0.7 AND evidence traceable to real artifacts"
  failure_criteria: "budget exhausted OR confidence < 0.4"
  escalation_criteria: "confidence < 0.7 after max_iterations"

agent:
  name: coder
  tools: [read_file, write_file, search_code, git_diff, git_commit, run_shell_allowlisted]
  permissions: { write_source: true, deploy: false }
  budget: { max_iterations: 8, max_tokens: 80000, max_tool_calls: 100, max_changed_files: 100 }

agent:
  name: release
  tools: [query_observability, query_failure_kb, recommend_deploy, recommend_rollback]
  permissions: { write_source: false, deploy: false }   # recommend-only, policy engine executes
```

Inter-agent communication is always a structured artifact matching a schema, never free-form
text between agents:

```json
{
  "task_id": "tsk_...",
  "agent": "debugger",
  "input_artifacts": ["failure:flr_9f2a", "diff:abc123"],
  "diagnosis": { "root_cause": "...", "confidence": 0.92 },
  "recommended_actions": ["apply_patch:tests/auth/fixtures.py"]
}
```

---

## 25. Technology Stack

| Layer | Options evaluated | Selected | Why |
|---|---|---|---|
| Backend language | TypeScript/Node, Python, Go | **TypeScript (control plane/orchestrator glue) + Go (execution fabric/workers)** | TS gives fast iteration + great Temporal SDK + shared types with dashboard; Go gives efficient, low-overhead workers/sandboddling code where performance and small binaries matter. Python is used *inside* agent-tool implementations where ML/data tooling helps, not as the core service language. |
| Orchestration | Temporal, Argo, Dagster, GitHub Actions | **Temporal** (control plane) + Argo Workflows/native K8s jobs (raw CI execution) | §4.3 |
| Execution | Docker, Kubernetes, Firecracker | **Kubernetes + Firecracker (Kata shim) for untrusted/agent code, gVisor containers for deterministic steps** | §6 |
| Messaging | NATS, Kafka, Redis Streams | **NATS JetStream** (MVP→mid scale), Kafka migration path at extreme scale | §11 |
| Database | PostgreSQL, Redis, Object Storage, Vector DB | **PostgreSQL + pgvector, Redis, S3-compatible object storage** | Consolidates system-of-record + vector search; adds dedicated vector DB only if scale demands (§34) |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Tempo | **All five, standard OTel-native stack** | §14 |
| Security | Vault, OIDC, K8s RBAC, OPA, Kyverno | **OPA (policy engine), Vault (secrets/dynamic creds), OIDC (federation), K8s RBAC + Kyverno (cluster admission policy)** | §10, §15 |
| Build | BuildKit, Bazel, Nix | **BuildKit (default) + Nix (base image pinning) + Bazel (opt-in, large monorepos)** | §7 |
| Testing | Playwright, pytest, Vitest, Testcontainers, k6, Semgrep, Trivy | **All, per layer** (§8.1) | Best-in-class per test layer |

**Selection priorities honored:** low operational complexity (NATS over Kafka at MVP, Postgres
over a fragmented polyglot-persistence stack), high automation (Temporal's durable execution
removes huge classes of manual recovery work), high reliability (idempotency + reconciliation
everywhere), low cost (model routing + hybrid KB before large-model calls), easy local dev
(Docker Compose profile mirrors prod topology for local iteration), easy cloud deployment
(everything ships as Helm charts on any Kubernetes).

---

## 26. Production Deployment Topology

```text
Region A (primary)                         Region B (standby / DR)
┌─────────────────────────────┐            ┌─────────────────────────────┐
│ K8s cluster                  │            │ K8s cluster (warm standby)  │
│  - API / Webhook GW (HPA)    │            │  - replicated via async     │
│  - Temporal cluster (HA, 3+  │◀──streaming replication──▶│  Postgres  │
│    nodes, multi-AZ)          │            │  - artifact storage         │
│  - NATS JetStream (clustered)│            │    cross-region replicated  │
│  - Orchestrator workers (HPA)│            └─────────────────────────────┘
│  - Agent runtime pool (HPA,  │
│    node pool w/ Firecracker) │
│  - CI worker pool (HPA)      │
│  - Postgres (primary, HA via │
│    Patroni, multi-AZ)        │
│  - OTel/Prom/Grafana/Loki/   │
│    Tempo                      │
└─────────────────────────────┘
```

Every stateless component (API, gateway, orchestrator workers, agent runtime, CI workers,
failure engine, context retrieval, event consumers — §52) runs behind an HPA on Kubernetes.
Postgres is the only component requiring careful HA design (Patroni/streaming replication +
automated failover); Temporal itself is deployed HA per its standard multi-node topology.
Cross-region DR targets the RTO/RPO in §20; artifact storage and Postgres backups replicate
cross-region continuously.

---

## 27. End-to-End Execution Example

**Developer:** *"Add OAuth login."*

| # | Step | Artifact produced |
|---|---|---|
| 1 | Requirement parsing | `task.requirement_text`, structured intent |
| 2 | Repository analysis | Architecture summary (cached, incrementally updated) |
| 3 | Architecture discovery | Relevant modules: `src/auth/`, `src/api/routes/` |
| 4 | Task decomposition | `plan.json`: add OAuth provider config, middleware, callback route, session handling |
| 5 | Agent implementation | Diff on `agent/tsk_1234` branch |
| 6 | Test generation | `tests/auth/test_oauth_login.py` (regression-verified per §8.2) |
| 7 | Static analysis | Lint/type/Semgrep pass |
| 8 | Build | `build.artifact_digest = sha256:...` |
| 9 | Unit tests | 42/42 pass |
| 10 | Integration tests | 1 failure: `test_oauth_callback_sets_session` |
| 11 | **Failure** | `failures` row created |
| 12 | Failure fingerprinting | `fingerprint = sha256(...)` |
| 13 | Historical retrieval | No exact match; structural match to a prior "session cookie SameSite" fix |
| 14 | Diagnosis | Debugger Agent: root cause = missing `SameSite=Lax` on session cookie, confidence 0.88 |
| 15 | Patch | 3-line change in `src/auth/session.py` |
| 16 | Targeted tests | Pass |
| 17 | Regression tests | Pass |
| 18 | Security scanning | SAST/dep/secret scans pass |
| 19 | Artifact creation | OCI image + SBOM + provenance |
| 20 | Staging deployment | `deployments` row, `state=deployed` |
| 21 | E2E tests | Playwright OAuth flow passes |
| 22 | Canary deployment | 1% → 5% → 25% → 50% → 100%, each window clean |
| 23 | Observability | Error rate/latency within baseline throughout |
| 24 | Promotion | `RELEASED` |
| 25 | PR merge | Merge queue serializes merge into `main`, PR closed with linked pipeline run |

---

## 28. Failure-and-Repair Example

**Successful repair:**

```text
Agent modifies authentication middleware
  → Integration test fails
  → Failure Engine extracts stack trace, classifies UNIT/INTEGRATION_FAILURE
  → Fingerprint generated
  → Historical failure DB searched (structural match found: 70% similarity)
  → Debugger Agent receives compact context (diff + stack trace + matched historical fix, not
    the whole repo)
  → Root cause identified: new middleware requires `state` param test fixture doesn't set
  → Patch generated (fixture update)
  → Targeted test passes
  → Regression suite passes
  → Security scan passes
  → Pipeline continues to SECURITY_GATE
```

**Correct escalation (agent cannot fix):**

```text
Agent attempts to fix a failing integration test tied to a database migration
  → Iteration 1: patch adjusts query, breaks a different test (foreign-key constraint)
  → Iteration 2: patch adjusts constraint, breaks original test again
  → Oscillation Detector flags: patch_hash(iter 3) ≈ inverse(patch_hash(iter 1))
  → Repair loop halts at iteration 3 (below max_iterations=5, but oscillation overrides budget)
  → Escalation packet generated: both failing tests, both attempted patches, root-cause
    hypothesis ("migration changes FK semantics in a way that conflicts with existing data
    assumptions — needs a data migration, not a code fix"), risk=high (schema change)
  → Routed to HUMAN_REVIEW; pipeline paused, not abandoned; human can resume with guidance
```

---

## 29. Evaluation Framework & Acceptance Criteria

**Acceptance test suites (§72):** Functional, Agent Evaluation, CI/CD Integration, Security,
Reliability, Performance, Scalability, Recovery, Chaos, Cost, Reproducibility, Human-in-the-loop.

**Golden Benchmark (§92):** 100 fixed scenarios — 10 each of simple/medium/complex bugs,
feature tasks, refactors, dependency upgrades, security tasks, CI failures, deployment
failures, and flaky-test cases. Every architecture/prompt/model change re-runs this benchmark;
results tracked on a **versioned leaderboard** (success rate, regression rate, tokens, cost,
latency, tool calls, human escalation per run), so regressions in agent quality are caught the
same way code regressions are.

**Release gate for the agent system itself (§93):**

```text
Agent Release Allowed IF:
  functional_tests >= 99% AND security_tests = 100% AND sandbox_escape = 0
  AND pipeline_state_loss = 0 AND regression_rate <= 3% AND repair_success >= 85%
  AND critical_benchmark_regressions = 0 AND p95_latency <= target AND cost_per_task <= budget
ELSE BLOCK RELEASE
```

Key metric definitions used throughout (§74–79, §91): eventual task success requires the fix to
both resolve the original failure *and* keep regression tests green (§75); root-cause accuracy
is measured top-1 and top-3 against a labeled benchmark; missed high-risk escalation target is
**zero** — the system should prefer "I don't know" over a confident wrong diagnosis (§76, §91).

---

## 30. Implementation Roadmap

| Phase | Adds | Key components | Primary risk | Acceptance gate |
|---|---|---|---|---|
| **1 — Foundations** | Git integration, workspace, sandbox, command execution, basic CI, test execution, agent repair loop | Git State Manager, Tool Gateway v1, Firecracker sandbox, Temporal skeleton, basic Failure schema | Sandbox isolation gaps | Repair loop hits ≥50% first-pass success on a 20-task pilot benchmark; 0 sandbox escapes in pen test |
| **2 — Intelligence** | Failure Intelligence, Test Impact Analysis, Agent Memory, Failure Knowledge Base | Classifier, fingerprinting, code→test graph, hybrid KB (SQL+vector+graph) | KB retrieval quality (false-positive fix reuse) | Root-cause top-3 accuracy ≥85%; test-selection regression recall ≥95% |
| **3 — Production Readiness** | Deployment, Observability, Canary, Rollback, Policy Engine | Argo Rollouts, OTel stack, OPA policies, Credential Broker | Rollback false negatives (missed regression) | Rollback detection <60s in chaos tests; 0 unauthorized privileged actions |
| **4 — Scale & Self-Improvement** | Multi-agent orchestration, cost-aware routing, self-improving repair, org-wide memory | Full 8-agent contract set, model router, cross-repo Organization Memory | Cost runaway from unbounded model escalation | Cost/task within configured budget across Golden Benchmark; escalation rate ≤15% |

Each phase deliverable includes, per §39: components, interfaces, DB schema deltas, APIs,
deployment architecture, risks, and acceptance criteria — captured as phase-entry ADRs (not
duplicated here) referencing the sections above.

---

## 31. Repository Structure

```text
agentic-cicd/
├── apps/
│   ├── api/                    # control-plane REST/gRPC API
│   ├── orchestrator/           # Temporal workflows + activities
│   ├── agent-runtime/          # hosts agent brains, calls Tool Gateway
│   ├── worker/                 # CI/build/test worker binary
│   ├── webhook-gateway/        # Git provider webhook ingestion + dedupe
│   └── dashboard/               # Agent Engineering Dashboard (Grafana app / custom UI)
│
├── agents/
│   ├── planner/  ├── coder/  ├── tester/  ├── debugger/
│   ├── security/ ├── reviewer/ ├── release/ └── incident/
│   └── (each: prompts/, contract.yaml, evals/)
│
├── packages/
│   ├── agent-sdk/               # typed client for agent-runtime → tool gateway
│   ├── tool-sdk/                # tool contract definitions + validators
│   ├── pipeline-engine/         # state machine + DAG compiler
│   ├── policy-engine/           # OPA bundle build + eval client
│   ├── failure-engine/          # parser, classifier, fingerprinter
│   ├── context-engine/          # retrieve/rank/compress/inject
│   ├── memory/                  # short-term/task/repo/failure/org memory clients
│   ├── git/                     # Git State Manager
│   ├── artifacts/               # artifact registry client, SBOM/provenance
│   ├── observability/           # OTel setup, ID propagation helpers
│   └── schemas/                 # shared JSON Schema / protobuf definitions
│
├── workers/
│   ├── build/  ├── test/  ├── security/  └── deploy/
│
├── infrastructure/
│   ├── docker/  ├── kubernetes/ (Helm charts)  ├── terraform/  └── helm/
│
├── policies/                    # OPA/Rego bundles, versioned
├── migrations/                  # Postgres schema migrations
├── tests/
│   ├── acceptance/               # §72 suites A–L
│   └── golden-benchmark/         # §92, 100 scenarios + harness
├── docs/
└── scripts/
```

---

## 32. Definition of Done

```text
[ ] Agent implements code, generates tests, executes tests, diagnoses failures, repairs
[ ] Repair loop bounded (iterations, tokens, time, patch size) with oscillation detection
[ ] Test impact analysis + flaky test detection operational
[ ] CI providers and Git workflow integrated via adapters
[ ] Artifacts immutable; SBOM + build provenance generated
[ ] Production credentials fully isolated behind Credential Broker
[ ] Agent execution sandboxed (Firecracker default for untrusted code)
[ ] Policy Engine blocks unsafe merge/deploy/rollback actions
[ ] Deployment progressive (canary) with deterministic rollback
[ ] Observability integrated with propagated trace/pipeline IDs
[ ] Pipeline state durable, resumable; all operations idempotent
[ ] Audit logs immutable and complete for privileged actions
[ ] Multi-agent contracts defined and enforced
[ ] Context engineered (budgeted, ranked) not dumped
[ ] Failure memory (hybrid KB) reduces repeat-diagnosis cost
[ ] Cost-aware model routing operational
[ ] Golden benchmark exists with versioned leaderboard
[ ] Chaos, security, performance, scalability targets pass
[ ] Human escalation path tested and correctly triggered
```

---

## 33. Final Architecture Evaluation

**Scorecard (0–10, current design as specified):**

| Dimension | Score | Rationale |
|---|---|---|
| Correctness | 8 | Strong completion predicate + regression gating; residual risk in diagnosis accuracy at scale |
| Reliability | 8 | Temporal durable execution + idempotency give strong guarantees |
| Security | 8 | Zero-trust, broker model, sandboxing well specified; needs continuous red-teaming to hold this score |
| Scalability | 7 | Solid to ~1,000 repos; NATS/Postgres choices need revisiting past that (§34) |
| Performance | 7 | Latency budgets defined; not yet validated against real 500k-LOC benchmark |
| Automation | 8 | Bounded autonomy with clear escalation is the right shape |
| Agent Intelligence | 7 | Hybrid KB + routing is sound; quality depends heavily on prompt/eval iteration, not architecture alone |
| Cost Efficiency | 8 | Model routing + deterministic-first design directly targets the dominant cost driver |
| Observability | 8 | Full ID propagation + dedicated agent-system dashboard |
| Maintainability | 8 | Clear layering (Agent → SDK → Gateway → Policy → Service → Infra) |
| Extensibility | 8 | Adapter interfaces for CI/Git/cloud providers |
| Developer Experience | 7 | Strong once built; onboarding curve (Temporal, OPA, Firecracker) is nontrivial |
| Operational Complexity | 6 | Many moving parts (Temporal, NATS, OPA, Vault, K8s, Firecracker) — real ops investment required |

**Top 10 architectural risks**

| Risk | Prob. | Impact | Detection | Mitigation | Residual |
|---|---|---|---|---|---|
| Debugger Agent over-confident wrong diagnosis causes bad patch to merge | Med | High | Regression-after-fix tracking, confidence calibration audits | Require regression-suite green + confidence threshold + reviewer agent | Low-Med |
| Prompt injection via repo content triggers unsafe tool call | Med | High | Injection acceptance tests (§80), anomalous tool-call pattern detection | Tool Gateway allowlist + no ambient credentials + data/instruction tagging | Low |
| Sandbox escape | Low | Critical | Continuous pen testing (§81) | Firecracker isolation, minimal syscall surface, no network to metadata service | Low |
| Postgres becomes a bottleneck at scale | Med | Med | Query latency SLOs, connection pool saturation alerts | Read replicas, partitioning by tenant, eventual move to sharded/managed scale-out (§34) | Med |
| Repair loop cost runaway (many low-value LLM calls) | Med | Med | Cost/task dashboards, budget alerts | Deterministic-first routing, hybrid KB short-circuit, hard token budgets | Low |
| Canary promotion on noisy metrics (false positive promote) | Low | High | Backtesting promotion criteria against historical incidents | Sequential statistical test, not fixed-threshold snapshot | Low |
| Temporal cluster operational failure | Low | High | Chaos tests (kill orchestrator) | Multi-node HA Temporal, durable history in Postgres, DR region | Low |
| Failure Knowledge Base poisoned by a bad "successful fix" that wasn't actually correct | Med | Med | Track regression-after-reuse rate per KB entry | Re-validate every reused fix with full regression suite before accepting; decay/demote entries with poor reuse outcomes | Low |
| Cross-tenant data leakage via shared caches/queues | Low | Critical | Tenant-isolation fuzzing, RLS audit | `tenant_id` enforced at DB row level + Gateway policy checks + per-tenant queue namespaces | Low |
| Test suite growth outpaces test-selection accuracy, slowing feedback | Med | Med | Track P95 pipeline duration trend | Continuous recomputation of code→test graph, periodic full-suite reconciliation | Med |

**Top 10 bottlenecks:** Postgres write throughput at very high pipeline-run concurrency; NATS
message volume beyond ~10k events/sec; Firecracker microVM provisioning latency under burst
load; Context Engine retrieval latency for very large monorepos; Tool Gateway policy-eval
latency if OPA bundles grow large/complex; artifact object-storage egress cost at high build
volume; Debugger Agent large-model latency for complex multi-file failures; merge-queue
serialization becoming a throughput ceiling with many concurrent agent PRs; dashboard/query
load on the metrics store at scale; single-region control plane during regional incidents.

**Top 10 failure modes:** LLM API outage/timeout mid-repair; worker OOM during a large build;
webhook delivery duplication/storm; ephemeral DB provisioning failure for integration tests;
CI provider outage; flaky-test false classification causing missed regression; canary metric
pipeline lag causing delayed rollback detection; Git provider rate-limiting agent PR creation;
credential broker outage blocking all deploys; object storage regional outage affecting
artifact retrieval.

**Top 10 security threats:** covered in full in §10.3 (prompt injection, sandbox escape,
credential exfiltration, supply-chain compromise, cross-tenant access, malicious external PRs,
unauthorized production actions), plus: insider misuse of human-approval path, dependency
confusion attacks on internal package names, and audit-log tampering (mitigated by
append-only/WORM storage for audit records).

**Top 10 cost drivers:** large-reasoning-model repair calls; full-regression-suite runs
triggered too eagerly; E2E test infrastructure (browser farms); microVM cold-start overhead at
low utilization; object storage for logs/videos/screenshots; cross-region data transfer for DR
replication; observability stack cardinality (high-cardinality labels blowing up Prometheus);
Postgres compute for high-concurrency workloads; CI worker pool over-provisioning for peak
bursts; vector search compute for Failure KB queries at high failure volume.

**Scaling to 10,000 repositories / hundreds of thousands of jobs per day:**

The components that fail first, in order: (1) **Postgres** as a single write target for
`pipeline_stages`/`tool_calls`/`events` — needs partitioning by `tenant_id`/time and eventually
a move to a horizontally-shardable store (Citus, or splitting hot tables into a
purpose-built time-series/event store) well before 10k repos; (2) **NATS JetStream** throughput
— migrate the durable event bus to **Kafka** once sustained event rates exceed the
tens-of-thousands-per-second range, keeping NATS only for low-latency ephemeral fan-out;
(3) **the merge queue** becomes a global serialization point — needs to become per-repo/per-shard
rather than global, with cross-repo dependencies handled explicitly rather than implicitly
serialized; (4) **Context Engine retrieval** against very large, numerous codebases needs a
dedicated, pre-computed, incrementally-updated code-graph index service rather than
computing dependency/call graphs on demand; (5) **single-region control plane** must become
active-active or at minimum much faster failover, since blast radius at this scale makes a
15-minute RTO too costly. Architecturally, the fix is the same principle applied recursively:
keep every component stateless and horizontally partitionable, push anything that becomes a
bottleneck behind a sharding key (`tenant_id` is the natural one throughout), and replace
single-writer stores with either partitioned/sharded variants or purpose-built systems (event
store, time-series store) before they saturate — the design in this document is intentionally
built so that migration path exists without a control-plane rewrite.

---

*End of design document.*
