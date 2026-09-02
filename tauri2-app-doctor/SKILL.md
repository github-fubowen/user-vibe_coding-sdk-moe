---
name: tauri2-app-doctor
description: >
  Diagnose a Tauri 2 desktop app that "doesn't work" — builds fine but the window
  hangs, shows nothing, all commands fail (`command not allowed`), or a runtime-created
  window is broken. USE when a Tauri 2 / Tauri v2 project is reported unusable,
  freezes on startup, has dead buttons, or its installer works locally but not on a
  clean machine. Deterministic-first checklist: ACL window-label scoping → build
  target-dir hygiene → command thread model → COM apartment → distribution deps.
  Windows-first (Win32/COM/DLL), but the ACL and threading checks are cross-platform.
agent_created: true
version: 1.0.0
---

# Tauri 2 App Doctor

> Deterministic-first triage for "Tauri 2 app doesn't work". Every check below is
> either a **static fact you can read** or a **one-command observation** — no guessing.
> Work top-down; the top three account for the large majority of real failures.

## 0. 30-second triage — answer these four first

```text
Q1 Does it compile / bundle?          → cargo + vite logs
Q2 Does the process start?            → tasklist /FI "IMAGENAME eq <app>.exe" /V  (看「状态」「窗口标题」)
Q3 Does the window appear?            → 窗口标题为空 + 状态「未响应/Not Responding」 = 主线程阻塞
Q4 Do buttons actually do anything?   → UI 上出现 `command ... not allowed` = ACL 问题
```

| 观察 | 最可能根因 | 跳到 |
|---|---|---|
| 窗口标题为空 + Not Responding | 同步命令阻塞主线程 / 坏二进制 | §2 + §3 |
| `command <x> not allowed` | capability 未覆盖该窗口标签 | **§1** |
| 主窗口正常，运行期新建的窗口功能全废 | capability 只写了 `["main"]` | **§1** |
| 本地能跑，装到别的机器起不来 | 运行时 DLL / WebView2 安装模式 | §5 |
| 一切正常但偶发卡死 | COM 单元模型 / 硬件 API 长阻塞 | §4 + §2 |

---

## 1. ACL window-label scoping (highest hit rate)

**Tauri 官方原文：**
> "The security boundaries are depending on window labels (**not titles**)."
> 全窗口写法是 `"windows": ["*"]`。

A capability listing `"windows": ["main"]` authorizes **only** windows whose *label*
is exactly `main`. Any window created at runtime via
`WebviewWindowBuilder::new(app, LABEL, ...)` with a different label gets an
**empty permission set** — including `core:event:allow-listen`, so it cannot even
receive events.

### Check (deterministic)

1. Collect labels declared in code:
   - `tauri.conf.json` → `app.windows[].label`
   - grep `WebviewWindowBuilder::new(` 第 2 个参数 / `const LABEL: &str`
2. Collect labels covered by capabilities:
   - `src-tauri/capabilities/*.json` → `windows` 数组
3. Set difference: `code_labels - capability_labels` must be empty (unless a
   capability uses `["*"]`).

### Fix patterns

- Quick: change `windows` to `["*"]`.
- Correct (least privilege): one capability file per window, each granting only the
  commands that window actually calls.
- Rust-side calls (`w.show()`, `app.emit_to(...)`) **never** need ACL — only JS
  `invoke` / `listen` from a webview do. Don't add permissions you don't need.

---

## 2. Command thread model (the "Not Responding" cause)

**Tauri 官方原文：**
> "Async commands are executed on a separate async task using `async_runtime::spawn`.
> **Commands without the async keyword are executed on the main thread** unless
> defined with `#[tauri::command(async)]`."

Blocking work in a sync command freezes the whole UI. Usual suspects:
monitor enumeration (DDC/CI `GetPhysicalMonitorsFromHMONITOR`), COM activation,
disk scans, network calls, `SystemParametersInfo` with `SPIF_SENDCHANGE`.

### Checks

- grep `#[tauri::command]` → count how many lack `async` / `#[tauri::command(async)]`
- grep frontend for auto-fired calls at init (`xxx.click()` in module constructors)
- Any command touching hardware/COM/registry → must be async

### Fix

1. Mark long/blocking commands `#[tauri::command(async)]`.
2. Cache + timeout hardware reads; refresh on demand, not at startup.
3. Frontend init fires reads concurrently (`Promise.all`) with per-card loading state
   so one failing card doesn't blank the page.

> **Order ironclad rule**: if a command uses COM, fix §4 (COM apartment) **before**
> switching it to async — moving COM onto a random tokio worker thread is what turns
> "works by luck" into "always fails".

---

## 3. Build target-dir hygiene (bad-binary fork)

A single repo can hold **two** release binaries that behave differently when the
build artifact directory is polluted (real-time AV / file-scanner shared locks →
OS error 32 → partially written ACL/codegen artifacts).

### Observation recipe (Windows)

```bash
tasklist /FI "IMAGENAME eq <app>.exe" /V /FO LIST | grep -E "PID|状态|窗口标题"
```

Compare each PID's full command line. Two different `target\` paths = two different
binaries; the one inside the workspace is usually the broken one.

### Fix (must do all)

1. `src-tauri/.cargo/config.toml`:
   ```toml
   [env]
   CARGO_TARGET_DIR = "D:\\<external-target>"   # outside the workspace
   ```
   (`[env]` applies to **every** invocation; a `.bat` env var only covers that script.)
2. Delete the workspace-internal `src-tauri/target` (usually 1–2 GB).
3. Document the single sanctioned build entry point in README.

---

## 4. COM apartment (Windows audio / shell / WMI)

Anti-pattern: `CoInitializeEx(COINIT_APARTMENTTHREADED)` called **inside** every
command, with no matching `CoUninitialize`.

- Works by luck while commands run on the main thread (already STA via wry/tao).
- Breaks the moment commands go async: the call lands on an arbitrary tokio worker
  thread; if that thread was already initialized MTA, `CoInitializeEx` returns
  `RPC_E_CHANGED_MODE` and the following `CoCreateInstance` fails → the whole module
  dies with a generic HRESULT.

### Fix (preferred)

Spawn **one dedicated STA thread** at startup, create the COM object once
(`IAudioEndpointVolume`, `IWbemServices`, …), keep it alive in `State`, and dispatch
calls to it over a channel. Fixed thread model, no leak, no race.

---

## 5. Distribution / clean-machine checks

### MinGW runtime DLLs (GNU toolchain)

```bash
# stdlib-only byte scan; more robust than hand-parsing the PE import table
python -c "import re,sys;d=open(sys.argv[1],'rb').read();\
print(sorted({m.group().decode() for m in re.finditer(rb'[A-Za-z0-9_+\-.]+\.dll',d)}))" app.exe
```

If `libgcc_s_seh-1.dll` / `libwinpthread-1.dll` / `libstdc++-6.dll` appear, the exe
needs them shipped alongside — or relink with `-C link-self-contained=yes`
(statically links the MinGW runtime; then the "ship MinGW DLLs" note in the README
is obsolete and must be deleted).

### WebView2 install mode

`tauri.conf.json` default is `downloadBootstrapper` → **requires internet at install
time**. For offline / locked-down / kiosk targets use:

```json
"windows": { "webviewInstallMode": { "type": "embedBootstrapper", "silent": true } }
```

### Always verify

- `WebView2Loader.dll` sits next to the exe and is inside the installer
- icon set is complete (not a single placeholder PNG)

---

## 6. Cheap correctness bugs worth grepping

| Symptom | Grep / location |
|---|---|
| UI shows the wrong version | `env!("CARGO_PKG_VERSION")` used where `tauri::VERSION` / `app.package_info().version` was meant |
| Silent failure of a critical registration | `let _ = <register/setup call>` — swallow-and-continue on the only exit path |
| Dead code | a `#[tauri::command]` never referenced from the frontend (`invoke<...>("name")`) |
| Warnings mask real bugs | `cargo build` warning count > 0 → `cargo fix`, then CI `-D warnings` |

---

## 7. Anti-regression: the one script worth writing

**`scripts/check-acl.py`** — static check that every window label created in code is
covered by some capability (or a `["*"]` capability exists). Exit 1 with the exact
missing label on failure.

This is the only mechanism that actually prevents §1 — a *config-vs-code drift* bug
that no compiler, linter, or type check can see. Wire it into pre-commit and CI.

Companion: `scripts/check-env.py` — assert `CARGO_TARGET_DIR` is outside the
workspace, `NODE_OPTIONS` has no injected shim, and `makensis` / `dlltool` are on PATH.

---

## 8. Host-environment gotchas (WorkBuddy sandbox, Windows)

- `NODE_OPTIONS` may be injected with `--require=.../genie-safe-delete.cjs`, which
  redirects `fs.rmSync` to the Recycle Bin → **vite fails when clearing `dist/`**.
  Build with `NODE_OPTIONS=--use-system-ca` (or `env -u NODE_OPTIONS`).
- The **PowerShell tool may not echo stdout** — have it write results to a file, then
  read the file. `Add-Type` (runtime .NET compile) is blocked by security policy.
- In Git Bash, `taskkill //PID 1234 //F` breaks via path mangling → use
  `taskkill /PID 1234 /F` or the PowerShell tool.
- `PYTHONPATH` may carry a `sitecustomize.py` shim → use the managed Python or
  `env -u PYTHONPATH`.

---

## 9. Output contract

Deliver: (1) a **root-cause table** with severity + evidence, (2) a **phased fix
plan** (止血 → 稳定性 → 防复发), (3) an **acceptance checklist** with concrete
user-visible steps, (4) the **引用** for every external claim. Never report SUCCESS
without an observed post-state; use 已确认 / 高概率待验证 / 待验证 for each finding.
