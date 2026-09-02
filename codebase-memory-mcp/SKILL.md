---
name: codebase-memory-mcp
description: "Codebase Memory MCP -- a high-performance code intelligence MCP server that builds knowledge graphs from codebases (158 languages) for sub-millisecond queries with 99% token savings. This skill should be used when the user wants to install, configure, or use the codebase-memory-mcp MCP server, or when the user asks to index a codebase, analyze code architecture, trace call paths, detect dead code, or perform semantic code search."
agent_created: true
---

# Codebase Memory MCP

## Overview

Codebase Memory MCP is the fastest code intelligence engine for AI coding agents.
It indexes codebases into a persistent knowledge graph (SQLite) using tree-sitter
AST analysis across 158 languages, with Hybrid LSP type resolution for Python,
TypeScript, Go, Java, Rust, and more. All processing is 100% local — code never
leaves the machine.

## Quick Reference

- **Binary**: `codebase-memory-mcp`
- **Install**: `curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash`
- **Windows Install**: Download and run `install.ps1` from the repo
- **Config**: `~/.workbuddy/mcp.json`
- **Cache**: `~/.cache/codebase-memory-mcp/`
- **Docs**: https://deusdata.github.io/codebase-memory-mcp/
- **Repo**: https://github.com/DeusData/codebase-memory-mcp
- **Tools**: 15 MCP tools (index, search, trace, architecture, Cypher, etc.)
- **Supported languages**: 158 (via vendored tree-sitter grammars)
- **Token savings**: ~99% vs file-based search (3,400 tokens vs 412,000 for 5 queries)

## Installation

### Step 1: Install the Binary

For macOS / Linux, use the one-liner:
```bash
curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash
```

For Windows (PowerShell, run as Administrator for per-machine install):
```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.ps1" -OutFile "$env:TEMP\install.ps1"
Unblock-File "$env:TEMP\install.ps1"
& "$env:TEMP\install.ps1"
```

Alternative package managers: npm (`npm install -g codebase-memory-mcp`), Homebrew, pip, Scoop, Chocolatey, Winget, AUR.

To include the 3D graph visualization UI, append `-- --ui` to the install command.

### Step 2: Configure in WorkBuddy

Read the existing MCP config at `~/.workbuddy/mcp.json` (create it if missing).
Add the server entry under `mcpServers`:

```json
{
  "mcpServers": {
    "codebase-memory-mcp": {
      "command": "<absolute-path-to-binary>",
      "args": []
    }
  }
}
```

To find the binary path:
- macOS/Linux: `which codebase-memory-mcp` (typically `~/.local/bin/codebase-memory-mcp`)
- Windows: `where codebase-memory-mcp` (typically `%LOCALAPPDATA%\Programs\codebase-memory-mcp\codebase-memory-mcp.exe`)

NOTE: The command path MUST be absolute. Relative paths will not work.

### Step 3: Verify

After writing the config, instruct the user:
- Open the connector management page in WorkBuddy
- Find `codebase-memory-mcp` in the custom connectors list
- Click "Trust" to enable it

The new MCP server will NOT activate automatically — the user must manually trust it.

## Workflow: First-Time Indexing

When the user asks to index a project or codebase:

1. Ensure the MCP server is installed and configured (see Installation above).
2. Use the `index_repository` tool with the absolute path to the project:
   ```
   mcp__codebase-memory-mcp__index_repository({ "repo_path": "/absolute/path/to/project" })
   ```
3. After indexing, use `list_projects` to confirm the project appears with node/edge counts.
4. Suggest enabling auto-index for future projects:
   ```bash
   codebase-memory-mcp config set auto_index true
   ```

Performance benchmark: Linux kernel (28M LOC, 75K files) indexed in ~3 minutes.

## Using the MCP Tools

### Indexing Tools

| Tool | Purpose |
|------|---------|
| `index_repository` | Index a codebase into the knowledge graph |
| `list_projects` | List all indexed projects with node/edge counts |
| `delete_project` | Remove a project and its graph data |
| `index_status` | Check indexing status of a project |

### Query Tools

| Tool | Purpose |
|------|---------|
| `search_graph` | Structured search by label, name pattern, file pattern, degree filters |
| `trace_path` | BFS traversal — who calls a function and what it calls (depth 1-5) |
| `detect_changes` | Map git diff to affected symbols with risk classification |
| `query_graph` | Execute read-only Cypher queries (openCypher subset) |
| `get_graph_schema` | Node/edge counts, relationship patterns, property definitions |
| `get_code_snippet` | Read function source code by qualified name |
| `get_architecture` | Codebase overview: languages, packages, entry points, routes, hotspots, clusters, ADRs |
| `search_code` | Grep-like text search within indexed project files |
| `manage_adr` | CRUD for Architecture Decision Records |
| `ingest_traces` | Ingest runtime traces to validate HTTP_CALLS edges |

### Common Query Patterns

**Find a function by name:**
```
search_graph({ "project": "my-project", "name_pattern": ".*Handler.*", "label": "Function" })
```

**Trace call paths (who calls / what it calls):**
```
trace_path({ "project": "my-project", "function_name": "Search", "direction": "both", "depth": 3 })
```

**Architecture overview:**
```
get_architecture({ "project": "my-project" })
```

**Detect dead code:**
```
query_graph({ "project": "my-project", "query": "MATCH (f:Function) WHERE NOT EXISTS { (other)-[:CALLS]->(f) } RETURN f.name, f.file LIMIT 20" })
```

**Impact analysis (uncommitted changes):**
```
detect_changes({ "project": "my-project" })
```

**Semantic code search (requires embeddings index):**
```
semantic_query({ "project": "my-project", "query": "how does authentication work" })
```

For detailed tool schemas and all Cypher capabilities, load `references/tools_reference.md`.

## Configuration

### CLI Runtime Settings

```bash
codebase-memory-mcp config list                     # View all settings
codebase-memory-mcp config set auto_index true       # Auto-index new projects
codebase-memory-mcp config set auto_index_limit 50000 # Max files for auto-index
codebase-memory-mcp config set auto_watch false      # Disable background watcher
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CBM_ALLOWED_ROOT` | (unset) | Restrict indexing to a specific directory |
| `CBM_CACHE_DIR` | `~/.cache/codebase-memory-mcp` | Override cache directory |
| `CBM_LOG_LEVEL` | `info` | Log level: debug/info/warn/error/none |
| `CBM_WORKERS` | auto | Override parallel indexing workers |
| `CBM_MEM_BUDGET_MB` | auto | Memory budget in MiB |

### File Extension Mapping

Create `~/.config/codebase-memory-mcp/config.json` (global) or `.codebase-memory.json` (per-project) to map custom extensions to languages:
```json
{
  "extra_extensions": {
    ".blade.php": "php",
    ".mjs": "javascript"
  }
}
```

### Team Sharing

Commit `.codebase-memory/graph.db.zst` to the repository. Teammates import it without re-indexing by copying to the cache directory. The file is a zstd-compressed SQLite graph snapshot. A `.gitattributes` entry with `merge=ours` is auto-created to prevent merge conflicts.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tools not visible in `/mcp` | Ensure binary path is absolute; restart WorkBuddy; check Trust is enabled |
| `index_repository` fails | Pass absolute path; check `CBM_ALLOWED_ROOT` if set |
| `trace_path` returns 0 results | Use `search_graph(name_pattern=".*PartialName.*")` to find exact function name first |
| Query returns wrong project data | Add explicit `project="name"` parameter |
| UI not loading | Install UI variant with `--ui` flag and pass `--ui=true` |
| Slow indexing | Set `CBM_WORKERS` to higher value; check `CBM_MEM_BUDGET_MB` |

## Updating

```bash
codebase-memory-mcp update
```

The server also auto-checks for updates on startup.

## Uninstalling

```bash
codebase-memory-mcp uninstall
```

Removes agent config entries, hooks, instructions, and the binary. Graph indexes are deleted after confirmation.
