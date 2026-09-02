---
name: pi-extension-dev
summary: Author pi-coding-agent / pi-web extensions (registerTool/registerCommand, bridge external MCP servers), with the jiti + Windows trash gotchas already solved.
description: |
  Use when building or debugging a pi-coding-agent extension (the harness behind pi-web at
  ~/.pi/agent/extensions/). Covers the ExtensionAPI surface (registerTool/registerCommand),
  how to bridge WorkBuddy MCP servers into pi as tools, and two environment-specific traps:
  (1) `import type` is erased by jiti so runtime `new X()` throws "X is not defined";
  (2) pnpm's safe-delete hits the WorkBuddy vendored genie-trash.exe and times out on Windows,
  so install deps with the managed node's bundled npm instead. Also: verify an extension loads
  by running `pi --help` and grepping for its [prefix] console.error logs.
---

# pi extension dev (pi-coding-agent / pi-web)

## When to use
- Adding a tool/command to the pi agent harness or to pi-web (same runtime, `~/.pi/agent`).
- Bridging an MCP server (WorkBuddy's `~/.workbuddy/mcp.json`) into pi, which has NO native MCP support.

## Extension layout
- Global extensions: `~/.pi/agent/extensions/<name>/` (or `.ts` file directly).
- Auto-discovered + hot-reloaded by jiti file-watch (`/reload` also reloads).
- Default export is the entrypoint: `export default async function (pi: ExtensionAPI) { ... }`
  (sync also allowed, but use async when you await connections).

## Key API (`@earendil-works/pi-coding-agent`, aliased — free to import)
- `pi.registerTool({ name, label, description, promptSnippet?, parameters, execute })` —
  `execute(toolCallId, params, signal, onUpdate, ctx)` returns
  `{ content: [{ type: "text", text }], details? }`.
- `pi.registerCommand(name, { description, handler: async (args, ctx) => {} })`.
- `pi.on("session_shutdown" | "session_start" | ..., cb)` for lifecycle.
- `ctx.ui.notify(text, "info"|"warning"|"error")` to surface messages.
- `typebox` is ALIASED by the loader — import `Type` from `"typebox"` directly (do NOT install it).
- `ExtensionContext`, `ExtensionAPI` are type-only imports (fine as `import type`).

## Bridging MCP servers (no native MCP in pi)
- Install the SDK locally inside the extension dir (scoped):
  `cd ~/.pi/agent/extensions/<name> && npm install @modelcontextprotocol/sdk`
  (use the MANAGED node's bundled npm: `C:/Users/fu268/.workbuddy/binaries/node/versions/22.22.2`).
  Do NOT use pnpm here (see gotchas).
- `import { Client } from "@modelcontextprotocol/sdk/client/index.js"` ← VALUE import, never `import type`.
- `import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js"`
- `import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js"`
- Connect: stdio servers use `{ command, args, env: {...process.env, ...cfg.env} }`;
  http/streamableHttp use `new StreamableHTTPClientTransport(new URL(url))`.
- Register each tool as `mcp__<server>__<tool>` (sanitize non `[a-zA-Z0-9_]` → `_`).
- Convert MCP `inputSchema` (JSON Schema) → TypeBox: handle string/number/integer/boolean/array/object,
  `enum`→`Type.Union(Literal)`, required→include, optional→`Type.Optional`, `additionalProperties:true`→`Type.Any()`.
  Fallback to `Type.Any()` on unknown shapes (never throw).
- `client.callTool({ name, arguments }, undefined, signal ? { signal } : undefined)`.
- Read servers from `~/.workbuddy/mcp.json` (`mcpServers` map; skip entries with `disabled:true`).
- ALWAYS wrap connect in a timeout + try/catch; on failure `console.error` + skip (never crash harness load).
- Add `process.on("SIGINT"|"SIGTERM"|"exit", closeAll)` so spawned stdio `.exe` servers don't orphan.

## Verification (no TUI needed)
- Run `pi --help` from the pi install dir (`D:/Software/pi_global/pi`). Extension load fires
  during startup even for --help, so your `console.error("[mcp-bridge] ...")` logs print.
  Grep them to confirm registration counts. (This also spawns stdio servers — kill orphans
  by image name afterwards, or rely on the process-exit cleanup handler.)
- In live pi-web (node :30141), the extension stays loaded; `/mcp` (or your status command)
  reports registered tool counts. pi-web's file-watch reloads the extension on edit.

## GOTCHAS (already solved — do not re-debug)
1. **jiti erases `import type`**: `import type { Client }` → at runtime `Client` is undefined →
   `new Client` throws "Client is not defined". Fix: value-import the SDK class.
2. **pnpm safe-delete timeout on Windows**: `pnpm add` fails linking with
   `[ERR_PNPM_LINKING_FAILED] ... genie-trash/win32-x64.exe ETIMEDOUT`. The vendored trash tool
   hangs. Fix: `rm -rf node_modules pnpm-lock.yaml` then install with the managed node's npm
   (`PATH="C:/Users/fu268/.workbuddy/binaries/node/versions/22.22.2:$PATH" npm install`).
3. **Orphaned stdio servers**: a transient `pi --help` run spawns servers that outlive the process
   unless you add the process-exit cleanup handler. pi-web (persistent :30141) legitimately keeps
   its own bridge alive — do not kill those.

## Reference: confirmed working state (2026-08-27)
- `~/.pi/agent/extensions/mcp-bridge/` bridges codebase-memory-mcp (8 tools) + code-review-graph
  (30 tools) = 38 tools; connector-proxy (:55557 down) and lighthouse-ops (auth) skip gracefully.
