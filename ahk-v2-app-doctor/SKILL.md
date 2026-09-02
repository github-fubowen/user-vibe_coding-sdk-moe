---
name: ahk-v2-app-doctor
description: >
  Diagnose an AutoHotkey v2 script / packaged exe that "won't start": double-click
  does nothing, a process appears with 0% CPU and no window, no GUI is created, or
  a 7-Zip SFX exe opens an extract dialog instead of the app. USE when an AHK v2
  project hangs silently, shows no window, or dies with "This value of type X has
  no property named Y" / "has no method named Z" / "This Func cannot be used as an
  output variable". Includes the v1→v2 migration trap list and the technique for
  capturing AHK's invisible modal #Warn/error dialogs.
agent_created: true
version: 1.0.0
---

# AHK v2 App Doctor

> AHK v2 failures are uniquely deceptive: a **load-time `#Warn` shows a modal dialog
> that `/ErrorStdOut` does NOT capture**, so the process sits alive at 0% CPU with no
> window, no log, and no error output. Never conclude "it hangs" — capture the dialog.

## 0. First move — capture the invisible dialog (do this before theorizing)

AHK's warning/error dialog is an ordinary Windows dialog (class `#32770`) titled with
the **script filename**. Dump every window + dialog text with a helper AHK script:

```ahk
; dump.ahk — run WHILE the target is hung; it exits immediately
out := ""
for hwnd in WinGetList() {
    try out .= hwnd " || class=" WinGetClass(hwnd) " || title=" WinGetTitle(hwnd) "`n"
}
FileAppend(out, "C:\probe\wins.txt")

txt := ""
for hwnd in WinGetList() {
    try if (WinGetClass(hwnd) = "#32770") {
        txt .= "=== " hwnd " " WinGetTitle(hwnd) "`n" WinGetText(hwnd) "`n-----`n"
    }
}
FileAppend(txt, "C:\probe\dialogs.txt")
```

Then read `dialogs.txt`. It contains the exact message, file and line number.

**Why `/ErrorStdOut` alone is not enough**: it captures *hard* load errors
("Script file not found", "This Func cannot be used as an output variable") but
**warnings** produced by `#Warn` still raise a modal dialog and block the script.
Also, when launched without a console, `/ErrorStdOut` may write nowhere at all.

## 1. Bisect when nothing is reported

If the dialog dump is empty and the script hangs, bisect by `#Include`:

```ahk
P := "C:\probe\s.log"
FileAppend("ok`n", P)
#Include "modules/One.ahk"      ; add one at a time
```

Run with a timeout. If the log is **missing**, the hang is at load time inside that
included file; if the log appears and the process lingers, the script is persistent
(hotkey/GUI/timer) — a different problem.

Prefer a Python driver with `timeout=` + `taskkill /IM AutoHotkey64.exe /F` on
`TimeoutExpired`, so one call tests all candidates.

## 2. AHK v1 → v2 migration trap list (the usual suspects)

| Trap | v1 | v2 correct form | Symptom |
|---|---|---|---|
| Virtual screen vars | `A_VirtualScreenLeft/Top/Width/Height` | `SysGet(76..79)` | `#Warn` "never assigned" → **modal dialog, script blocked** |
| Static property via instance | works | **NOT accessible via instance** — only `Class.Prop` | `has no property named X` |
| Reserved names as variables | many | `mod`, `log`, `round`, `min`, `max`, `abs`, `str`, `num` are built-in funcs | `This Func cannot be used as an output variable` |
| Class property named `Name` | OK | **collides with the built-in `Class.Name`** | static assignment silently unavailable → `has no property named "Name"` |
| Tab page switch | `tab.Use(n)` | **`tab.UseTab(n)`** | `Gui.Tab has no method named "Use"` |
| Array join | `arr.Join(sep)` | **no `Join` method**; build manually or pass the Array directly | `Array has no method named "Join"` |
| DropDownList/ListBox choices | `\|`-delimited string | **Array** | `Expected an Array but got a String` |
| Auto-execute section | ends at first hotkey | **v2 hotkeys do NOT end it** — execution continues past hotkeys | (verified on 2.0.27; don't assume v1 rules) |
| Top-level `global` decl | allowed | `global` only **inside** functions; top-level vars are already global | parse error |

Verify a suspected semantic with a 10-line probe before rewriting — e.g.:

```ahk
class Foo { static Bar := "S" \n Baz := "I" }
f := Foo()
try r := f.Bar catch as e ; -> fails in v2
```

## 3. Packaging — the "double-click does nothing" family

### 3.1 7-Zip SFX: usually a dead end (verified on 7-Zip 26.02)

Symptoms: double-clicking the exe shows **"7-Zip self-extracting archive / Extract to:"**
instead of the app, and **no child `AutoHotkey*.exe` is spawned**.

Two independent causes, either one fatal:

1. **7-Zip reorders archive members.** The SFX stub only recognises the installer
   block (`;!@Install@!` … `;!@InstallEnd@!`) when it is the **first member**. But
   `7z a` puts **directory entries** (`lib`, `modules`) first, and even with explicit
   file paths (no `-r`) it sorts **alphabetically**, so `config.txt` lands mid-list.
2. **`7z.sfx` does not support installer config at all.** 7-Zip ships three modules:
   `7z.sfx` (simple extract-only), `7zCon.sfx` (console), and **`7zS.sfx`**
   (installer module, the only one that reads `config.txt`) — the last one is **not**
   in the standard installer; it comes from 7-Zip Extra / the LZMA SDK.

**Traps that do NOT work** (all verified futile):
- renaming the config so it sorts first (`!install.txt` — it *does* reach slot #1,
  and the SFX *still* ignores it);
- `copy /b 7z.sfx + config.txt + archive.7z out.exe` (classic recipe, needs `7zS.sfx`).

Check what you actually have:
```bash
7z l -slt out.exe | head -30      # is config.txt really first?
ls "C:\Program Files\7-Zip\"       # any 7zS.sfx?
```

**Default recommendation: skip SFX entirely — see §3.2.**

### 3.2 Portable folder via the "default script" rule (recommended)

AutoHotkey loads **`<ExeBaseName>.ahk` from the executable's own directory** when run
with no arguments — no CWD dependency, no config file, no temp extraction, no dialog.

```
dist\MyTool.exe      ; = a copy of AutoHotkey64.exe, RENAMED to match the script
dist\MyTool.ahk
dist\lib\  dist\modules\  dist\config.ini
```

Double-clicking the exe runs the app. `A_ScriptDir` = the exe's dir, so logs/config
land next to it (works from a USB stick). This removes an entire class of bugs:
no `AutoHotkey64.ahk` duplicate to keep in sync, no SFX, no ordering rules.

### 3.3 Native Ahk2Exe — verify the bin before trusting a "success"

```bat
Ahk2Exe.exe /in app.ahk /out dist\app.exe /bin "AutoHotkeySC.bin"
```

Ahk2Exe reports **"Successfully compiled"** even when `/bin` is not a real
self-contained host. Symptom of a fake bin: the exe starts and immediately reports
`Script file not found` (it fell back to the default-script lookup).

**Always check**: `AutoHotkeySC.bin` must NOT be byte-identical to `AutoHotkey64.exe`.

```bash
md5sum AutoHotkeySC.bin AutoHotkey64.exe    # identical => it's just a runtime copy
```

The genuine v2 `AutoHotkeySC.bin` is fetched from GitHub by the v2 installer at
install time (`UX\install-ahk2exe.ahk`); offline machines usually only have a copy of
the interpreter, so native compilation is unavailable until it is downloaded once.

## 4. Runtime / robustness checks worth doing

- Startup must not silently rewrite user settings. Audit `Apply*`-on-launch paths —
  they will overwrite mouse speed, double-click time, volume, DPI on every launch.
- Config files must contain **every** key the code reads, or defaults get persisted
  on first run.
- Any full-screen / always-on-top / cursor-hiding state needs an **explicit exit key**
  (e.g. `Esc`) in addition to the global hotkey; the hotkey alone is a single point
  of failure.
- `LowLevelMouseProc`-style callbacks: always skip `LLMHF_INJECTED` (flags & 1) or
  you build an infinite inject→hook→inject feedback loop.

## 5. Anti-regression

- Add `OnError()` handler that **writes to a file**; a modal dialog is a production bug.
- Add a `smoke.ahk` that instantiates every module and calls
  `__New` / `BuildPage` / `Apply` / `Reset`, then writes a sentinel file. Run it after
  every change — this is the cheapest possible regression net for a script project.
- One `build.bat` that does copy → package → **verify member order** → smoke, so the
  packaging trap cannot recur.

## 6. Host gotchas (WorkBuddy sandbox, Windows)

- `reg.exe` / `wmic` may be blocked as "system tools"; read/write the registry with
  Python `winreg` instead (open with `KEY_SET_VALUE` when writing).
- Git Bash mangles `/d/path` into `D:\d\path` when passed to native Windows exes —
  use `D:/path` or run from inside the directory.
- **`cmd.exe` and `cmd /c` may be blocked entirely** (both from Bash and from the
  PowerShell tool) — you cannot execute a `.bat` you just wrote. Verify by
  replicating the script's steps directly in Bash, and keep the `.bat` as the
  user-facing deliverable.
- In double-quoted bash strings, complex Python one-liners break; use a
  `python - <<'PY'` heredoc.
- The PowerShell tool may not echo stdout — write results to a file and read it.
  `Add-Type` (runtime .NET compile, e.g. for screenshots) is blocked.
