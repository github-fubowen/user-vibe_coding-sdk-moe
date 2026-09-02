# Codebase Memory MCP — Tools Reference

## Graph Data Model

### Node Labels
`Project`, `Package`, `Folder`, `File`, `Module`, `Class`, `Function`, `Method`, `Interface`, `Enum`, `Type`, `Route`, `Resource`

### Edge Types
`CALLS`, `IMPORTS`, `DEFINES`, `IMPLEMENTS`, `INHERITS`, `HTTP_CALLS`, `ASYNC_CALLS`, `EMITS`, `LISTENS_ON`, `DATA_FLOWS`, `SIMILAR_TO`, `SEMANTICALLY_RELATED`, `CROSS_*` (cross-repository)

### Qualified Name Format
`<project>.<path_parts>.<name>`

---

## Tool Details

### index_repository
Index a repository into the knowledge graph. After initial indexing, the auto-sync watcher keeps it up to date.

Parameters:
- `repo_path` (string, required): Absolute path to the repository

Example:
```json
{ "repo_path": "/home/user/projects/my-app" }
```

### list_projects
List all indexed projects with their node and edge counts.

Parameters: none

### delete_project
Remove a project and all its graph data.

Parameters:
- `project` (string, required): Project name

### index_status
Check the indexing status of a project.

Parameters:
- `project` (string, required): Project name

### search_graph
Structured search by label, name pattern, file pattern, and degree filters.

Parameters:
- `project` (string, optional): Limit search to a specific project
- `label` (string, optional): Node label filter (e.g., "Function", "Class")
- `name_pattern` (string, optional): Regex pattern for name matching
- `file_pattern` (string, optional): Regex pattern for file path matching
- `min_degree` (integer, optional): Minimum number of edges
- `max_degree` (integer, optional): Maximum number of edges
- `limit` (integer, optional): Max results (default varies)
- `offset` (integer, optional): Pagination offset

Example:
```json
{ "project": "my-app", "name_pattern": ".*[Hh]andler.*", "label": "Function", "min_degree": 1 }
```

### trace_path
BFS traversal showing callers and callees of a function.

Parameters:
- `project` (string, required): Project name
- `function_name` (string, required): Function name (partial match supported)
- `direction` (string, optional): "incoming", "outgoing", or "both" (default: "both")
- `depth` (integer, optional): Traversal depth 1-5 (default: 2)

Example:
```json
{ "project": "my-app", "function_name": "authenticate", "direction": "both", "depth": 3 }
```

### detect_changes
Map uncommitted git changes to affected symbols with risk classification.

Parameters:
- `project` (string, required): Project name

Example:
```json
{ "project": "my-app" }
```

### query_graph
Execute read-only Cypher queries (openCypher subset).

Parameters:
- `project` (string, required): Project name
- `query` (string, required): Cypher query string

Supported Cypher clauses:
- `MATCH`, `OPTIONAL MATCH`, `WHERE`, `WITH`, `RETURN`, `ORDER BY`, `SKIP`, `LIMIT`, `DISTINCT`, `UNWIND`, `UNION`
- Aggregations: `count`, `sum`, `avg`, `min`, `max`, `collect`
- Variable-length paths: `[*1..3]`
- Existence checks: `EXISTS { (n)-[:TYPE]->() }`

Examples:
```cypher
-- Top 10 most-called functions
MATCH (caller)-[:CALLS]->(callee:Function)
RETURN callee.name, count(caller) AS callers
ORDER BY callers DESC
LIMIT 10

-- Dead code detection (functions with no callers, excluding entry points)
MATCH (f:Function)
WHERE NOT EXISTS { (other)-[:CALLS]->(f) }
AND NOT f.name IN ['main', 'init', 'run']
RETURN f.name, f.file
LIMIT 20

-- Find all HTTP routes and their handlers
MATCH (r:Route)-[:DEFINES]->(h)
RETURN r.name, h.name, h.file

-- Find indirect callers of a function (2 hops)
MATCH (caller)-[:CALLS*2]->(target:Function {name: 'logger'})
RETURN DISTINCT caller.name, caller.file
```

### get_graph_schema
Return node/edge counts, relationship patterns, and property definitions per label.

Parameters:
- `project` (string, optional): Project name

Run this first when exploring a newly indexed project to understand available labels and properties.

### get_code_snippet
Read the source code of a function by its qualified name.

Parameters:
- `project` (string, required): Project name
- `qualified_name` (string, required): Fully qualified function name

Example:
```json
{ "project": "my-app", "qualified_name": "my-app.src.auth.login" }
```

### get_architecture
Single-call codebase overview.

Parameters:
- `project` (string, required): Project name

Returns: languages, packages, entry points, routes, hotspots, boundaries, layers, clusters, and ADRs.

### search_code
Grep-like text search within indexed project files.

Parameters:
- `project` (string, required): Project name
- `query` (string, required): Text pattern to search
- `file_pattern` (string, optional): Limit to files matching this pattern
- `limit` (integer, optional): Max results

Example:
```json
{ "project": "my-app", "query": "TODO|FIXME", "file_pattern": "*.py" }
```

### manage_adr
CRUD operations for Architecture Decision Records.

Parameters:
- `project` (string, required): Project name
- `action` (string, required): "create", "read", "update", "delete", "list"
- Additional parameters depend on action (title, content, status, id)

### ingest_traces
Ingest runtime traces to validate HTTP_CALLS edges.

Parameters:
- `project` (string, required): Project name
- `traces` (array, required): Trace data in supported format

### semantic_query
Built-in Nomic `nomic-embed-code` embedding vector search (40K tokens, 768d int8). No API key required.

Parameters:
- `project` (string, required): Project name
- `query` (string, required): Natural language query

Example:
```json
{ "project": "my-app", "query": "how does the authentication middleware work" }
```

---

## Indexing Pipeline

```
File Discovery → Structure Parsing → Definition Extraction → Call Extraction → HTTP Linking → Configuration → Testing
```

1. **Tree-sitter AST parsing**: 158 languages with vendored grammars
2. **Hybrid LSP semantic type resolution**: Python, TypeScript/JavaScript, PHP, C#, Go, C, C++, Java, Kotlin, Rust, Perl
3. **RAM-first pipeline**: LZ4-compressed reads, in-memory SQLite, single-pass disk write

## Ignoring Files

Hierarchical: hardcoded patterns (`.git`, `node_modules`, etc.) → `.gitignore` hierarchy → `.cbmignore` (per-project, gitignore syntax). Symlinks are always skipped.
