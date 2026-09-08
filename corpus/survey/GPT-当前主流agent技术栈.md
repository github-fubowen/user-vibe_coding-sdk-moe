我调查了截至 2026 年 8 月仍在快速演进的主流 Coding Agent。一个非常明显的结论是：



> 现在真正拉开 Coding Agent 差距的，已经不只是 LLM，而是围绕 LLM 构建的 “Harness”——即 Agent Loop + Context Engineering + Tool Runtime + Sandbox + State + Verification + Orchestration 的完整执行系统。



OpenHands 在 2026 年甚至直接把软件 Agent 基础设施拆成三层：Harness、Orchestrator、Control Plane。(\[OpenHands]\[1])



\---



\# 1. 先定义：Coding Agent Harness 到底是什么



可以把它理解成：



```text

&#x20;                   Coding Agent

&#x20;                        │

&#x20;             ┌──────────▼──────────┐

&#x20;             │     Agent Harness   │

&#x20;             │                      │

&#x20;             │ 1. Agent Loop        │

&#x20;             │ 2. Context Engine    │

&#x20;             │ 3. Tool System       │

&#x20;             │ 4. Memory / State    │

&#x20;             │ 5. Policy / Approval │

&#x20;             │ 6. Sandbox / Runtime │

&#x20;             │ 7. Verification      │

&#x20;             │ 8. Git / Workspace   │

&#x20;             │ 9. Subagents        │

&#x20;             │ 10. Observability    │

&#x20;             └──────────┬──────────┘

&#x20;                        │

&#x20;         ┌──────────────┼──────────────┐

&#x20;         ▼              ▼              ▼

&#x20;       LLM            Tools         Runtime

&#x20;    Claude/GPT       Shell/MCP      Docker/VM

&#x20;    Gemini/...       Browser/Git     Worktree

```



所以：



```text

LLM

≠

Coding Agent



LLM + Harness

=

Coding Agent

```



更进一步：



```text

Coding Agent

\+

Orchestrator

\+

Control Plane

=

Agentic Software Factory

```



OpenHands 当前对这一层次划分就是类似这个思路。(\[OpenHands]\[1])



\---



\# 2. 当前主流 Coding Agent Harness 第一梯队



我会把目前主流体系大致分成：



| 项目          | 类型       | Harness 特点   | Runtime              | Context               | Tool                   | Multi-Agent |

| ----------- | -------- | ------------ | -------------------- | --------------------- | ---------------------- | ----------- |

| Claude Code | 商业闭源/可扩展 | 非常强          | 本机/远程                | CLAUDE.md、Skills      | Tool + MCP             | 强           |

| Codex       | OpenAI   | 非常强          | Sandbox/VM           | Thread/Skills         | Shell/File/MCP         | 强           |

| Cursor      | 商业闭源     | 极强           | 本地 + Cloud VM        | Codebase Context      | IDE/Agent tools        | 强           |

| Gemini CLI  | 开源       | 很强           | Docker/bwrap/gVisor  | GEMINI.md/JIT Context | Tool/MCP               | 强           |

| OpenHands   | 开源       | 很强           | Docker / 可插拔 Runtime | Context/Memory        | Tools                  | 很强          |

| Cline       | 开源       | 很强           | 本地/容器/工作树            | Context               | File/Shell/Browser/MCP | 强           |

| Roo Code    | 开源       | 很强           | 本地                   | Rules/Modes           | Tool Groups/MCP        | 很强          |

| Goose       | 开源       | 很强           | 本地/Server            | Recipes/Session       | MCP Extensions         | 很强          |

| Aider       | 开源       | 成熟轻量         | 本地                   | Repo Map              | Git/Edit/Shell         | 弱           |

| SWE-agent   | 开源/研究    | ACI 很强       | Sandbox              | Issue Context         | ACI Tools              | 中           |

| Agentless   | 开源/研究    | 非 Agent Loop | 外部执行                 | Localization          | Repair/Validation      | 弱           |



其中：



\* Codex、Claude Code、Cursor 更接近“生产级商业 Harness”

\* OpenHands、Goose、Cline、Roo Code 更接近“开放 Harness”

\* SWE-agent 更偏“Agent Computer Interface / Research Harness”

\* Aider 更偏“高效代码编辑 Harness”

\* Agentless 则代表另一条路线：尽量减少开放式 Agent Loop。(\[GitHub]\[2])



\---



\# 3. Codex：目前非常值得研究的 Harness



我认为如果你想自己实现一个 Coding Agent，Codex 是最值得拆解的架构之一。



OpenAI 在 2026 年专门公开写了一篇：



> Unlocking the Codex harness: how we built the App Server



核心思想是：



```text

&#x20;                      Client

&#x20;       ┌──────────────┼──────────────┐

&#x20;       │              │              │

&#x20;      TUI             IDE           Web

&#x20;       │              │              │

&#x20;       └──────────────▼──────────────┘

&#x20;                   App Server

&#x20;                 JSON-RPC / JSONL

&#x20;                        │

&#x20;                  Thread Manager

&#x20;                        │

&#x20;                   Codex Core

&#x20;                        │

&#x20;             ┌──────────┼──────────┐

&#x20;             ▼          ▼          ▼

&#x20;           Tools      Context    Policies

&#x20;             │

&#x20;      ┌──────┼────────────┐

&#x20;      ▼      ▼            ▼

&#x20;    Shell   Files        MCP

&#x20;      │

&#x20;      ▼

&#x20;   Sandbox

```



Codex Core 同时承担 Agent loop、工具执行以及一个 thread 的运行时与持久化；App Server 则把这个核心 Harness 暴露给 TUI、IDE、Web 等不同客户端。(\[OpenAI]\[3])



这里有个非常重要的设计：



```text

UI ≠ Agent

Agent ≠ Runtime

Agent ≠ Protocol

```



而是：



```text

Client

&#x20;  ↓

App Server

&#x20;  ↓

Codex Core

&#x20;  ↓

Sandbox / Tools

```



这是非常适合大型 Coding Agent 的架构。



而且 Codex 当前默认 CLI 已经是 Rust 实现，以 standalone executable 为目标。(\[GitHub]\[4])



\### Codex 的关键组件



OpenAI 明确列出的核心 Harness 能力包括：



```text

Agent Loop

Thread Lifecycle

Persistence

Config

Auth

Shell/File tools

MCP

Skills

Sandbox

Event Stream

JSON-RPC

```



其中 Thread 不是简单的 chat history，而是完整的可恢复 Agent execution state。(\[OpenAI]\[3])



这意味着：



```text

session

&#x20;  ↓

thread

&#x20;  ↓

events

&#x20;  ↓

tool calls

&#x20;  ↓

state

```



都变成一等公民。



这个思想非常重要。



\---



\# 4. Claude Code：非常强的“工具 + Hooks + Skills + Subagents”体系



Claude Code 的核心特点不是花哨 UI，而是把 Harness 能力大量暴露出来。



尤其是：



```text

Claude Code

├── Tools

├── Skills

├── Agents

├── Hooks

├── MCP

├── Plugins

└── Permissions

```



Anthropic 的插件体系当前已经明确支持：



```text

commands/

agents/

skills/

hooks/

.mcp.json

```



同时 Hooks 可以监听：



```text

PreToolUse

PostToolUse

Stop

SubagentStop

SessionStart

SessionEnd

UserPromptSubmit

PreCompact

Notification

```



并且可以针对工具调用实施自动化控制。(\[GitHub]\[5])



这其实非常接近：



```text

Agent Event Bus

```



例如：



```text

Agent

&#x20; │

&#x20; ├── PreToolUse

&#x20; │       ↓

&#x20; │   Security Policy

&#x20; │

&#x20; ├── Tool

&#x20; │

&#x20; ├── PostToolUse

&#x20; │       ↓

&#x20; │   Formatter / Linter

&#x20; │

&#x20; ├── SubagentStop

&#x20; │       ↓

&#x20; │   Reviewer

&#x20; │

&#x20; └── Stop

&#x20;         ↓

&#x20;     Verification

```



这比单纯：



```text

LLM → Tool → LLM

```



强很多。



实际上已经开始接近：



```text

LLM

\+

Event-driven Workflow Engine

```



不过 Claude Code 当前的公开 issue 也显示出一个值得注意的问题：Subagent 与父 Agent 的 hooks、权限、上下文继承仍然是复杂区域。(\[GitHub]\[6])



这恰恰证明：



> Subagent orchestration 正在从“提示词技巧”变成 Harness 基础设施问题。



\---



\# 5. Gemini CLI：非常典型的现代开源 Harness



Gemini CLI 的架构很值得借鉴。



它目前是：



```text

Node.js

TypeScript

React/Ink

npm monorepo

```



核心代码划分：



```text

packages/

├── cli/

├── core/

├── sdk/

├── a2a-server/

└── ...

```



其中 `core` 负责：



```text

Gemini API

Prompt Construction

Tool Execution

Agent Loop

Context

Policy

Compression

```



(\[GitHub]\[7])



尤其值得注意的是它已经非常明确地发展出了：



```text

Agent

├── Tool Registry

├── Prompt Registry

├── Resource Registry

├── Context

├── Compression Service

└── Agent Executor

```



源码中的 `LocalAgentExecutor` 就是一个明确的 Agent loop executor，会不断执行 Agent → Tool，直到 `complete\_task`。(\[GitHub]\[8])



\---



\# 6. Gemini CLI 的 Context Engineering 很值得研究



Gemini CLI 已经加入了：



> JIT Context Discovery



也就是：



```text

不是：

启动 Agent

↓

把整个 repo 塞给模型



而是：

Agent

↓

需要什么

↓

动态发现

↓

读取

↓

继续推理

```



Gemini CLI 的更新记录明确把 JIT Context Discovery 作为 Agent Architecture Enhancements。(\[GitHub]\[9])



这其实是下一代 Coding Agent 非常核心的方向。



\---



\# 7. Gemini CLI 的 Sandbox 也很典型



目前它已经支持：



```text

Docker

Podman

LXC

gVisor

bubblewrap

seccomp

Windows native

```



并且可以配置：



```text

sandboxAllowedPaths

sandboxNetworkAccess

```



(\[GitHub]\[10])



这说明现代 Coding Agent 的 Runtime 正在从：



```text

subprocess()

```



升级成：



```text

Policy-controlled execution environment

```



\---



\# 8. OpenHands：最值得研究的开源 Agent Harness 之一



OpenHands 非常重要，因为它已经明确把：



```text

Harness

Orchestrator

Control Plane

```



拆开。



它现在的 Agent Core 是：



```text

Agent

&#x20; ↓

Reasoning / Action Loop

&#x20; ↓

Tool Orchestration

&#x20; ↓

Context Management

```



并且采用 event-driven architecture。(\[GitHub]\[11])



\---



\## OpenHands Runtime



传统 OpenHands V0：



```text

Agent

&#x20; ↓

Runtime Server

&#x20; ↓

Docker

&#x20; ├── Bash

&#x20; ├── Browser

&#x20; ├── Plugins

&#x20; └── Jupyter

```



可以实现：



```text

Code execution

Browser

Shell

Package installation

Testing

Isolation

```



(\[GitHub]\[12])



但非常有意思的是 OpenHands V1 正在改变：



```text

以前：

Agent

&#x20; ↓

Docker Runtime



现在：

Agent + Tools

&#x20; ↓

同进程运行

&#x20; ↓

需要隔离时再 containerize

```



也就是说：



> Sandbox 从“强制基础设施”逐渐变成“可插拔 Runtime”。



(\[GitHub]\[13])



这是一个非常重要的趋势。



\---



\# 9. Cline：非常典型的 IDE Agent Harness



Cline 的工具体系相当直接：



```text

File

Shell

Browser

MCP

Interaction

Task delegation

```



它已经抽象成 SDK，可以被：



```text

VSCode

JetBrains

CLI

Kanban

Custom Application

```



共用。(\[Cline]\[14])



因此其方向也是：



```text

Agent Core

&#x20;      ↓

&#x20;     SDK

&#x20;      ↓

┌──────┼────────┬────────┐

IDE    CLI     Kanban   API

```



这其实与 Codex App Server 的思路高度一致。



\---



\# 10. Roo Code：特别值得研究它的 Mode / Tool Permission



Roo Code 有个非常重要的设计：



```text

Mode

```



例如：



```text

Code

Ask

Architect

Debug

Orchestrator

```



不同 Mode 拥有不同 Tool 权限。



例如：



```text

Architect

&#x20;   ↓

read + mcp

&#x20;   +

limited edit



Code

&#x20;   ↓

read + edit + command + mcp



Orchestrator

&#x20;   ↓

new\_task

```



(\[GitHub]\[15])



这个设计特别适合你之前一直研究的：



> “上层 Agent → 中间路由层 → 专业 Agent”



可以直接抽象成：



```text

Agent Role

&#x20;   +

Tool Capability

&#x20;   +

Permission

&#x20;   +

Prompt

&#x20;   +

Context

```



而不是：



```text

所有 Agent

↓

所有 Tools

```



\---



\# 11. Goose：目前非常典型的“通用 Agent Runtime”



Goose 当前已经发展到：



```text

Desktop

CLI

API

MCP

ACP

Recipes

Subagents

Scheduler

```



并且本身用 Rust 实现。(\[Block]\[16])



其内部逻辑可以理解成：



```text

Profile

&#x20;  ↓

Extensions

&#x20;  ↓

Exchange

&#x20;  ↓

LLM

&#x20;  ↓

Tool Calls

```



(\[GitHub]\[17])



这里的 Extension 基本就是：



```text

Tool + State + Prompt

```



这是非常漂亮的抽象。



\---



\# 12. Goose 的 Recipe 很值得借鉴



Recipe 相当于：



```text

可执行 Agent Workflow

```



比如：



```yaml

task:

&#x20; ...

extensions:

&#x20; - developer

&#x20; - browser

sub\_recipes:

&#x20; - ...

```



所以 Goose 已经逐渐形成：



```text

Agent

&#x20;  ↓

Recipe

&#x20;  ↓

Sub Recipe

&#x20;  ↓

Sub Agent

```



同时还开始将：



```text

Chat

Scheduler

Dynamic Task

Recipe

Subagent

```



统一到一个 Execution Pipeline。(\[GitHub]\[18])



这其实就是：



> Agent Execution Engine



\---



\# 13. Aider：虽然老一些，但很多底层设计非常优秀



Aider 最大的特点不是 Multi-Agent，而是：



> Context Engineering + Edit Efficiency



它维护：



```text

Repo Map

```



把整个代码库压缩成：



```text

file

class

function

signature

critical code

```



然后持续提供给模型。(\[GitHub]\[19])



这是 Coding Agent 中非常重要的：



```text

Repository Representation

```



\---



\## Aider 的 Edit Harness



它支持：



```text

whole

diff

diff-fenced

udiff

editor-diff

editor-whole

```



而且不同模型使用不同编辑格式。(\[GitHub]\[20])



这说明：



> “怎样让模型修改代码”本身就是 Harness 的核心算法。



而不是简单调用：



```text

write\_file()

```



\---



\# 14. SWE-agent：从“Agent Computer Interface”角度非常重要



SWE-agent 有一个很经典的思想：



> Agent Computer Interface（ACI）



即：



```text

LLM

&#x20;↓

不是直接操作 Linux

&#x20;↓

而是操作经过设计的 Computer Interface

```



例如 SWE-agent：



```text

specialized viewer

special edit command

syntax checking

tool constraints

```



甚至编辑时就运行 linter，如果语法不合法则不允许提交修改。(\[swe-agent.com]\[21])



这实际上说明一个很重要的事实：



> Tool Design 本身就是 Agent Intelligence 的一部分。



同一个模型：



```text

LLM + 普通 shell

```



可能远远弱于：



```text

LLM + 精心设计的 ACI

```



\---



\# 15. Cursor：目前商业 Coding Harness 的另一种路线



Cursor 的 Cloud Agents 已经采用：



```text

Task

&#x20;↓

Dedicated VM

&#x20;↓

Repo

&#x20;↓

Dependencies

&#x20;↓

Secrets

&#x20;↓

Network

&#x20;↓

Agent

&#x20;↓

Code

&#x20;↓

Tests

&#x20;↓

Artifacts

&#x20;↓

PR

```



每个 Agent 都有自己的 VM，同时存在：



```text

Secret redaction

Network policy

Credential management

Sandbox isolation

```



并且最终可以产出：



```text

Screenshot

Video

Log

Pull Request

```



(\[Cursor]\[22])



所以 Cursor 更像：



```text

Coding Agent

\+

Cloud Dev Environment

\+

Remote Worker

```



而不仅仅是 IDE Copilot。



\---



\# 16. 一个非常重要的技术趋势：MCP 正在变成“Tool Bus”



现在主流产品基本都在走：



```text

Agent

&#x20;↓

Tool Registry

&#x20;↓

MCP

&#x20;↓

External capability

```



例如：



```text

GitHub

Database

Browser

Search

Filesystem

Cloud

Linear

Jira

Slack

Kubernetes

```



因此推荐的设计已经越来越接近：



```text

&#x20;                   Agent

&#x20;                     │

&#x20;               Tool Registry

&#x20;                     │

&#x20;         ┌───────────┼───────────┐

&#x20;         ▼           ▼           ▼

&#x20;      Built-in      MCP        Native API

&#x20;         │           │           │

&#x20;       shell       GitHub       Cloud

```



Gemini CLI、Claude Code、Goose、Cline、OpenHands 都在向这个方向发展。(\[GitHub]\[5])



\---



\# 17. MCP 还不是完整的 Agent Protocol



这里必须注意一个容易混淆的问题：



```text

MCP

```



解决的是：



> Agent ↔ Tools/Data



而：



```text

ACP / App Server

```



解决的是：



> Client ↔ Agent



这两个完全不是一回事。



例如 Codex 当前明确把：



```text

MCP

```



作为 Tool integration，而：



```text

Codex App Server

```



用于：



```text

TUI

IDE

Web

Desktop

```



的 Agent integration。(\[OpenAI]\[3])



Goose 则已经同时使用 MCP 和 ACP：



```text

MCP

↓

Extensions / Tools



ACP

↓

Agent ↔ Client

```



(\[GitHub]\[23])



所以未来可能会形成：



```text

&#x20;                 Client

&#x20;                   │

&#x20;                ACP/API

&#x20;                   │

&#x20;             Agent Runtime

&#x20;                   │

&#x20;           Agent Execution

&#x20;                   │

&#x20;            Tool Registry

&#x20;              │        │

&#x20;             MCP    Native Tools

```



\---



\# 18. 当前主流 Harness 技术栈可以总结成这一张表



| 层                | 主流技术                                             |

| ---------------- | ------------------------------------------------ |

| LLM              | Claude / GPT / Gemini / Qwen / DeepSeek          |

| Model Gateway    | LiteLLM / OpenRouter / Native SDK                |

| Agent Loop       | 自研 loop / state machine / event-driven loop      |

| Context          | Repo Map / JIT Discovery / RAG / semantic search |

| Code Search      | ripgrep / tree-sitter / AST / embeddings         |

| Code Edit        | Patch / Unified Diff / Search-Replace / AST      |

| Shell            | subprocess / PTY / node-pty                      |

| Browser          | Playwright / Puppeteer / Chrome DevTools         |

| Tool Protocol    | MCP                                              |

| Agent Protocol   | ACP / JSON-RPC / SSE / WebSocket                 |

| Memory           | Session DB / SQLite / files / vector DB          |

| Session          | Thread / conversation / event log                |

| Sandbox          | Docker / Podman / LXC / gVisor / bubblewrap / VM |

| Isolation        | git worktree / container / VM                    |

| Policy           | Allow/Deny / approval / hooks                    |

| Verification     | test / lint / typecheck / build                  |

| Git              | libgit2 / simple-git / subprocess Git            |

| Multi-Agent      | subagent / task / recipe / DAG                   |

| Scheduling       | cron / queue / temporal                          |

| Observability    | OpenTelemetry / traces / events                  |

| Storage          | SQLite / Postgres / object storage               |

| API              | REST / SSE / WebSocket / JSON-RPC                |

| UI               | React / VSCode Extension / TUI                   |

| Runtime Language | Rust / TypeScript / Python                       |



\---



\# 19. 目前最重要的架构趋势，其实不是“Multi-Agent”



很多人研究 Coding Agent 时第一反应是：



```text

Planner

Coder

Reviewer

Tester

...

```



但从这些项目的演化来看，更底层的优先级其实是：



```text

Context

&#x20;  ↓

Tools

&#x20;  ↓

Runtime

&#x20;  ↓

Verification

&#x20;  ↓

State

&#x20;  ↓

Policy

&#x20;  ↓

Orchestration

```



而不是：



```text

Multi-Agent

```



原因很简单：



```text

Garbage Context

\+

Bad Tools

\+

No Sandbox

\+

No Verification

=

100 agents still garbage

```



\---



\# 20. 真正现代的 Coding Agent Harness



我认为目前最佳实践可以抽象成：



```text

&#x20;                        ┌──────────────┐

&#x20;                        │     User     │

&#x20;                        └──────┬───────┘

&#x20;                               │

&#x20;                               ▼

&#x20;                    ┌───────────────────┐

&#x20;                    │  Agent Interface  │

&#x20;                    │ ACP / JSON-RPC    │

&#x20;                    └─────────┬─────────┘

&#x20;                              │

&#x20;                              ▼

┌──────────────────────────────────────────────────────────────┐

│                      AGENT HARNESS                           │

│                                                              │

│  ┌────────────┐       ┌──────────────┐                      │

│  │ Agent Loop │──────▶│ State/Thread │                      │

│  └─────┬──────┘       └──────────────┘                      │

│        │                                                     │

│        ▼                                                     │

│  ┌──────────────┐                                            │

│  │ Context      │                                            │

│  │ Engine       │                                            │

│  ├──────────────┤                                            │

│  │ Repo Map     │                                            │

│  │ JIT Search   │                                            │

│  │ RAG          │                                            │

│  │ Memory       │                                            │

│  └──────┬───────┘                                            │

│         │                                                    │

│         ▼                                                    │

│  ┌────────────────┐                                          │

│  │ Tool Registry  │                                          │

│  ├────────────────┤                                          │

│  │ read           │                                          │

│  │ search         │                                          │

│  │ edit           │                                          │

│  │ shell          │                                          │

│  │ git            │                                          │

│  │ browser        │                                          │

│  │ MCP            │                                          │

│  └──────┬─────────┘                                          │

│         │                                                    │

│         ▼                                                    │

│  ┌──────────────────┐                                        │

│  │ Policy Engine    │                                        │

│  │ Permissions      │                                        │

│  │ Hooks            │                                        │

│  │ Approval         │                                        │

│  └────────┬─────────┘                                        │

│           │                                                  │

│           ▼                                                  │

│  ┌──────────────────┐                                        │

│  │ Runtime          │                                        │

│  │ Sandbox          │                                        │

│  │ Worktree         │                                        │

│  │ Network           │                                        │

│  └────────┬─────────┘                                        │

│           │                                                  │

│           ▼                                                  │

│  ┌──────────────────┐                                        │

│  │ Verification     │                                        │

│  │ lint              │                                        │

│  │ test              │                                        │

│  │ build             │                                        │

│  │ typecheck         │                                        │

│  │ review            │                                        │

│  └────────┬─────────┘                                        │

│           │                                                  │

│           ▼                                                  │

│      Success / Retry                                         │

│                                                              │

└──────────────────────────────────────────────────────────────┘

```



这比传统：



```text

Prompt

&#x20;↓

LLM

&#x20;↓

Function Calling

```



已经完全是不同的东西。



\---



\# 21. 如果你准备自己做 Coding Agent，我最推荐的技术组合



结合你之前一直在研究的：



```text

Agent

Middleware

Skills

MCP

RAG

Knowledge Base

GitHub Actions

CI/CD

自动化软件生产线

```



我不会建议你直接复制某一个项目，而是组合：



\### Core



```text

TypeScript

```



或者：



```text

Rust

```



\### Agent Loop



```text

Event-driven State Machine

```



核心对象：



```text

AgentSession

AgentThread

AgentTurn

ToolCall

ToolResult

Event

Task

SubTask

```



\### Context



```text

tree-sitter

ripgrep

Repo Map

JIT Context Retrieval

Embedding

SQLite

```



而不是一上来把整个 repo RAG 化。



\### Tool



```text

Built-in Tools

\+

MCP

```



工具分类：



```text

READ

SEARCH

EDIT

EXECUTE

GIT

BROWSER

NETWORK

DEPLOY

```



\### Edit



优先：



```text

Search/Replace

Unified Diff

Patch

```



不要默认：



```text

whole file rewrite

```



Aider 和 SWE-agent 的设计都说明编辑协议本身对 Agent 能力影响很大。(\[GitHub]\[20])



\### Runtime



本地：



```text

git worktree

\+

subprocess

\+

PTY

```



高风险任务：



```text

Docker

```



云端：



```text

microVM / VM

```



\### Policy



```text

Tool Permission

\+

Approval

\+

Hook

\+

Network Policy

\+

Filesystem Policy

```



\### Verification



```text

Agent 修改

&#x20;↓

format

&#x20;↓

lint

&#x20;↓

typecheck

&#x20;↓

test

&#x20;↓

build

&#x20;↓

security scan

&#x20;↓

review agent

```



\### Multi-Agent



不要一上来做：



```text

10 个 Agent

```



建议做：



```text

Main Agent

&#x20;   │

&#x20;   ├── Explore

&#x20;   ├── Implement

&#x20;   ├── Test

&#x20;   └── Review

```



其中每一个 Subagent 都：



```text

Scoped Context

\+

Scoped Tools

\+

Scoped Permissions

\+

Scoped Workspace

```



这和 Roo Code 的 Mode、Goose 的 Extension/Recipe、Codex 的 thread 模型都很契合。(\[GitHub]\[15])



\---



\# 22. 如果从“工程成熟度”评价，我会这样排



不是单纯按产品名气，而是按“值得研究 Harness 架构”的角度：



\### 第一梯队：强烈建议拆解



```text

Codex

Claude Code

Cursor

OpenHands

Gemini CLI

```



重点研究：



```text

Agent Loop

Context

Sandbox

Session

Tools

Policy

App Server

```



\### 第二梯队：非常值得研究



```text

Goose

Cline

Roo Code

```



重点研究：



```text

MCP

ACP

Extensions

Modes

Recipes

Subagents

SDK 化

```



\### 第三梯队：算法/机制研究价值很高



```text

Aider

SWE-agent

Agentless

```



重点研究：



```text

Repo Map

ACI

Edit Protocol

Localization

Patch Validation

```



Agentless 尤其值得当作“反方向基准”：它明确采用 localization → repair → patch validation 的三阶段流程，而不是无限制 Agent loop。(\[GitHub]\[2])



\---



\# 23. 最值得关注的下一阶段



我认为 2026 年以后 Coding Agent Harness 会逐渐从：



```text

LLM Agent

```



转变为：



```text

Agent Runtime

```



再进一步：



```text

Software Engineering Runtime

```



最后变成：



```text

Software Factory Control Plane

```



大概是：



```text

&#x20;               Control Plane

&#x20;                    │

&#x20;         ┌──────────┼──────────┐

&#x20;         ▼          ▼          ▼

&#x20;      Planner    Scheduler   Policy

&#x20;         │          │          │

&#x20;         └──────────┼──────────┘

&#x20;                    ▼

&#x20;                Orchestrator

&#x20;                    │

&#x20;      ┌─────────────┼─────────────┐

&#x20;      ▼             ▼             ▼

&#x20;  Agent A        Agent B        Agent C

&#x20;      │             │             │

&#x20;      ▼             ▼             ▼

&#x20;  Worktree       Worktree       Worktree

&#x20;      │             │             │

&#x20;      ▼             ▼             ▼

&#x20;   Sandbox        Sandbox        Sandbox

&#x20;      │             │             │

&#x20;      └─────────────┼─────────────┘

&#x20;                    ▼

&#x20;                CI / Test

&#x20;                    │

&#x20;                    ▼

&#x20;              Review / Merge

&#x20;                    │

&#x20;                    ▼

&#x20;                 Deploy

```



也就是说，真正有长期技术壁垒的东西，不太可能只是一个“更好的 Prompt”。



更可能是：



```text

Context Engineering

\+

Tool Engineering

\+

Runtime Engineering

\+

Verification Engineering

\+

Agent Orchestration

\+

Control Plane

```



这就是现在所谓 “Harness Engineering” 真正开始成为独立工程领域的原因；近期行业讨论也已经把 Harness 描述为连接模型、memory、workflow context、企业数据和执行环境的控制层。(\[The Wall Street Journal]\[24])



\---



\## 推荐直接阅读的一手资料



\[OpenAI — Unlocking the Codex Harness](https://openai.com/index/unlocking-the-codex-harness/?utm\_source=chatgpt.com)



\[OpenHands — Software Agent Control Plane](https://www.openhands.dev/blog/agent-control-plane?utm\_source=chatgpt.com)



\[OpenHands — Runtime Architecture](https://github.com/OpenHands/docs/blob/main/openhands/usage/architecture/runtime.mdx?utm\_source=chatgpt.com)



\[Gemini CLI — GitHub](https://github.com/google-gemini/gemini-cli?utm\_source=chatgpt.com)



\[Goose — Architecture](https://github.com/aaif-goose/goose/blob/main/documentation/docs/goose-architecture/goose-architecture.md?utm\_source=chatgpt.com)



\[SWE-agent — Agent Computer Interface](https://swe-agent.com/latest/background/aci/?utm\_source=chatgpt.com)



\[Aider — Repository Map](https://github.com/Aider-AI/aider/blob/main/aider/website/docs/repomap.md?utm\_source=chatgpt.com)



\[Roo Code — Modes](https://github.com/RooCodeInc/Roo-Code-Docs/blob/main/docs/basic-usage/using-modes.md?utm\_source=chatgpt.com)



\---



如果把这些项目进一步抽象，其实可以得到一套非常统一的“Coding Agent Harness OS”架构：`Agent Kernel → Context Engine → Tool Bus → Policy Engine → Runtime/Sandbox → Verification Loop → Subagent Scheduler → Control Plane`。这个抽象比单独研究 Claude Code、Codex 或 OpenHands 更适合你后面自己做一个工程级 Coding Agent。



\[1]: https://www.openhands.dev/blog/agent-control-plane?utm\_source=chatgpt.com "The Software Agent Control Plane | Apr 03, 2026"

\[2]: https://github.com/OpenAutoCoder/Agentless/blob/main/README.md?utm\_source=chatgpt.com "Agentless/README.md at main · OpenAutoCoder/Agentless · GitHub"

\[3]: https://openai.com/index/unlocking-the-codex-harness/?utm\_source=chatgpt.com "Unlocking the Codex harness: how we built the App Server | OpenAI"

\[4]: https://github.com/openai/codex/blob/main/codex-rs/README.md?utm\_source=chatgpt.com "codex/codex-rs/README.md at main · openai/codex · GitHub"

\[5]: https://github.com/anthropics/claude-code/blob/main/plugins/plugin-dev/skills/plugin-structure/SKILL.md?utm\_source=chatgpt.com "claude-code/plugins/plugin-dev/skills/plugin-structure/SKILL.md at main · anthropics/claude-code · GitHub"

\[6]: https://github.com/anthropics/claude-code/issues/69283?utm\_source=chatgpt.com "\[FEATURE] Opt-in context inheritance for Agent-spawned subagents (inherit\_context flag) · Issue #69283 · anthropics/claude-code · GitHub"

\[7]: https://github.com/google-gemini/gemini-cli/blob/main/GEMINI.md?plain=1\&utm\_source=chatgpt.com "gemini-cli/GEMINI.md at main · google-gemini/gemini-cli · GitHub"

\[8]: https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/agents/local-executor.ts?utm\_source=chatgpt.com "gemini-cli/packages/core/src/agents/local-executor.ts at main · google-gemini/gemini-cli · GitHub"

\[9]: https://github.com/google-gemini/gemini-cli/blob/main/docs/changelogs/index.md?utm\_source=chatgpt.com "gemini-cli/docs/changelogs/index.md at main · google-gemini/gemini-cli · GitHub"

\[10]: https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md?utm\_source=chatgpt.com "gemini-cli/docs/reference/configuration.md at main · google-gemini/gemini-cli · GitHub"

\[11]: https://github.com/OpenHands/docs/blob/main/sdk/arch/agent.mdx?utm\_source=chatgpt.com "docs/sdk/arch/agent.mdx at main · OpenHands/docs · GitHub"

\[12]: https://github.com/OpenHands/docs/blob/main/openhands/usage/architecture/runtime.mdx?utm\_source=chatgpt.com "docs/openhands/usage/architecture/runtime.mdx at main · OpenHands/docs · GitHub"

\[13]: https://github.com/OpenHands/docs/blob/main/sdk/arch/design.mdx?utm\_source=chatgpt.com "docs/sdk/arch/design.mdx at main · OpenHands/docs · GitHub"

\[14]: https://docs.cline.bot/cline-overview?utm\_source=chatgpt.com "Cline Overview - Cline"

\[15]: https://github.com/RooCodeInc/Roo-Code-Docs/blob/main/docs/basic-usage/using-modes.md?utm\_source=chatgpt.com "Roo-Code-Docs/docs/basic-usage/using-modes.md at main · RooCodeInc/Roo-Code-Docs · GitHub"

\[16]: https://block.github.io/goose/?utm\_source=chatgpt.com "goose | Your open source AI agent"

\[17]: https://github.com/cybernetics/block-goose/blob/main/ARCHITECTURE.md?utm\_source=chatgpt.com "block-goose/ARCHITECTURE.md at main · cybernetics/block-goose · GitHub"

\[18]: https://github.com/block/goose/discussions/4389?utm\_source=chatgpt.com "Unify Agent Execution: per‑session agents, unified tasks/recipes/scheduler · aaif-goose goose · Discussion #4389 · GitHub"

\[19]: https://github.com/Aider-AI/aider/blob/main/aider/website/docs/repomap.md?utm\_source=chatgpt.com "aider/aider/website/docs/repomap.md at main · Aider-AI/aider · GitHub"

\[20]: https://github.com/Aider-AI/aider/blob/main/aider/website/docs/more/edit-formats.md?utm\_source=chatgpt.com "aider/aider/website/docs/more/edit-formats.md at main · Aider-AI/aider · GitHub"

\[21]: https://swe-agent.com/latest/background/aci/?utm\_source=chatgpt.com "Agent tools - SWE-agent documentation"

\[22]: https://prod.cursor.com/help/ai-features/background-agents?utm\_source=chatgpt.com "What are background agents? | Cursor Docs"

\[23]: https://github.com/aaif-goose/goose/blob/main/documentation/docs/goose-architecture/goose-architecture.md?utm\_source=chatgpt.com "goose/documentation/docs/goose-architecture/goose-architecture.md at main · aaif-goose/goose · GitHub"

\[24]: https://www.wsj.com/cio-journal/introducing-the-ai-model-harness-a638c65b?utm\_source=chatgpt.com "Introducing the AI Model 'Harness'"



