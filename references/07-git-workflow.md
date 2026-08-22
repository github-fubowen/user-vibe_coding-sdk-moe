# ref-07 — Git Workflow & Version Control (v1.1.0)

> Load when: starting any coding session's commit/push step, planning branch strategy,
> needing undo/rollback, or versioning the SDK itself. Complements SKILL.md §10.
> Authoritative user conventions: **local commit = default; git push = explicit user confirmation ONLY.**

---

## 1. Session lifecycle — when to commit

A "logical unit" is the smallest change that is independently correct and independently revertible:

| Unit | Example | Commit when |
|------|---------|-------------|
| Feature | new module / API endpoint | done + tests green |
| Bug fix | root cause patched | verified (repro → fix → re-test) |
| Refactor | rename / extract / restructure | behavior preserved, tests still green |
| Review feedback | suggestions landed | after verification, one commit per theme |
| Docs | README / spec / changelog | content coherent |
| Session end | any state | EVERYTHING committed or explicitly stashed — never leave the tree dirty |

Rules:
- **Never commit broken code** — run the verification step first (§5.3 self-check / verification-before-completion).
- **Never commit secrets** — `.env`, tokens, credentials go to `.gitignore` (pitfalls §7).
- **Small commits > big ones** — a 3-line fix deserves its own commit; a 500-line feature deserves several.

---

## 2. Commit message conventions (Conventional Commits)

```
type(scope): summary        # ≤ 72 chars, lowercase type
```

| type | use when | example |
|------|----------|---------|
| `feat` | new capability | `feat(skill): add git management section (v1.1.0)` |
| `fix` | bug fix | `fix(thinking): repair CJK leak in chain` |
| `refactor` | behavior-preserving change | `refactor(routing): extract vendor adapter layer` |
| `docs` | docs only | `docs(ref-06): update token math formula` |
| `chore` | maintenance / version bump | `chore(skill): bump to v1.1.0` |
| `test` | test-only changes | `test(eval): add golden-set cache case` |
| `perf` | performance | `perf(index): batch embedding writes` |

Guidelines:
- Scope = module/area (`skill`, `api`, `storage`, `retrieval`) — optional but recommended.
- Summary in Chinese OK (matches user's existing repo style); body optional, `why` not `what`.
- **No emoji in commit messages** (machine-parse friendly, clean `git log --oneline`).
- Existing user style precedent: `v2.1 P3: 新增 handoff/triage 技能；全量验收通过（…）` — keep summaries dense and information-carrying.

---

## 3. Branch & worktree strategy

| Task size | Strategy |
|-----------|----------|
| Small / 1-2 commits | commit directly on `main` |
| Feature / multi-step | `feature/<name>` branch → commit per ticket → verify → merge |
| Hotfix | `fix/<name>` from `main` → merge back |
| Experimental / throwaway | git worktree (see `using-git-worktrees`) or scratch branch, delete if abandoned |
| Parallel work | worktree per branch — zero checkout churn |

Merge discipline:
- `main` is **stable-only**: every commit on main must pass verification.
- Merge feature branches via **squash or rebase-merge** to keep main linear (unless user prefers merge commits — ask once, then follow).
- Delete merged/abandoned branches locally after merge; never leave zombie branches.

---

## 4. Mode → Git action map

| Mode | Git behavior |
|------|--------------|
| **Vibe** | throwaway branch/worktree → commit at each working milestone → keep (merge) or delete; no ceremony |
| **Engineering** | `feature/<name>` → ticket-granular `feat:`/`refactor:` commits → verification → merge to main |
| **SDD** | spec commit first (`docs(spec): …`) → implement per ticket → each ticket = one commit → triage commits as `fix:` |
| **Debug** | one bug = one commit: repro → fix → `fix(<module>): …` → verify; revert-friendly |
| **Review** | feedback → grouped by theme → one `refactor:`/`fix:` per theme after verification |
| **Quick Edit** | commit directly on current branch, tiny message: `fix: typo in docs` |

---

## 5. Undo recipes (safety-first)

| Scenario | Command | Caution |
|----------|---------|---------|
| Working tree messy, want to pause | `git stash` → fix → `git stash pop` | pop conflicts possible; keep stash name (`git stash push -m "wip: …"`) |
| Commit message typo (NOT pushed) | `git commit --amend -m "…"` | amend only unpushed commits |
| Last commit wrong (NOT pushed) | `git reset --soft HEAD~1` → recommit | soft reset preserves working tree |
| Pushed commit is wrong | `git revert <sha>` | **NEVER `reset --hard` on shared/pushed history** |
| Accidentally deleted a file | `git checkout -- <path>` / `git restore <path>` | discards uncommitted edits to that file — check first |
| Abandon a branch | `git branch -D <name>` | force-delete only with user confirmation |
| WIP across sessions | stash or WIP commit on a feature branch | never WIP on `main` |
| Everything broken, want last good state | `git log --oneline` → pick good sha → `git revert` range | avoid `reset --hard` entirely unless user confirms |

Golden rule: **revert > reset**. Anything that has left your machine stays in history — `revert` is the only safe way to fix it.

---

## 6. Push & remote policy (user hard rule)

1. **Local commits happen freely; pushing does NOT.**
2. Every push request is preceded by a stop-and-ask: remote + branch + commit count + **deploy side-effects** (CI runs, Cloudflare/Vercel auto-deploy quota consumption).
3. Only after explicit user confirmation: `git push` / `gh pr create`.
4. Environment notes: `gh` CLI v2.97.0 at `<GH_CLI_BIN>`, GitHub account `github-fubowen` (fine-grained PAT). Ask before any remote interaction.
5. If push fails mid-way, diagnose (auth / upstream / non-fast-forward) — never `push --force` without user confirmation.

---

## 7. Skill self-versioning (this SDK)

The SDK lives at `~/.workbuddy/skills/user-vibe_coding-sdk-moe/`, inside the `~/.workbuddy/skills/` git repo.

Version bump flow (every change to SKILL.md or references):
1. Edit content (SKILL.md main file + reference file if needed — progressive disclosure, keep main file lean).
2. Bump version: title `vX.Y.Z` + frontmatter `description` `(vX.Y.Z)`.
3. Append changelog entry at top of changelog block: `> **vX.Y.Z 变更（date）**: …`.
4. If prompts/logic changed → run golden-set regression before release (§8 / ref-05).
5. Commit locally: `chore(skill): bump to vX.Y.Z` (or `feat(skill): …` for new capability).
6. Push only with user confirmation (§6).

Version semantics: `MAJOR` = breaking protocol change · `MINOR` = new capability/section · `PATCH` = fix/tune. Production configs pin dated IDs (`deepseek-v4-pro-0813` style, §8) — never bare semantic aliases.

---

## 8. Pitfalls

- **Secrets in commits**: `.env`, API keys, tokens → `.gitignore` them; if leaked, rotate + rewrite history carefully (ask user first).
- **Large binaries**: models / zips / datasets → keep out of repo or use git-lfs (repo size balloons fast; user's D: disk is at 97% — be economical).
- **Windows line endings**: set `.gitattributes` or `core.autocrlf=true` once per repo to avoid whitespace noise.
- **Caches & memory**: `.workbuddy/memory/` and runtime caches are NOT source — do not commit unless intended.
- **Force-push on shared branches**: forbidden without explicit user confirmation.
- **Mixed commits**: fix + refactor + docs in one commit = impossible rollback — split them.
- **Dirty tree at session end**: verify with `git status` — every file is committed, stashed, or deliberately ignored.
- **Windows `~/.workbuddy` symlink**: on this machine `~/.workbuddy` → a symlinked location outside the home dir. `git -C ~/.workbuddy/...` fails ("cannot change to") — always use the Windows-style real path, e.g. `git -C "C:/Users/<user>/.workbuddy/skills"`.
- **WorkBuddy Bash 沙箱静默丢远程跟踪引用**: inside the WorkBuddy Bash sandbox, `git fetch origin` and `git update-ref refs/remotes/origin/main` both report success (rc=0) but the ref file under `.git/refs/remotes/origin/` is silently never written (new file in a new subdir gets dropped by the sandbox overlay) → `git status` keeps showing `## main...origin/main [gone]`. Commits and pushes are unaffected (refs/heads updates and the D: bare remote both write fine). Workaround: run `git fetch origin` once from the user's own terminal (no sandbox), or `git branch --unset-upstream main` to drop the tracking config.
- **Fine-grained PAT push 403/404**: read-only PATs return 404 on repo API and 403 on `git push`. Fix = grant the token access to the target repo with **Contents: Read and write**. Verify with `gh api user/repos --jq '.[]|select(.name=="<repo>")|.permissions'` — expect `"push":true`. `createRepository` is a separate permission; fine-grained PATs usually lack it → create repos manually on web.
- **HTTPS push 需先 `gh auth setup-git`**（2026-08-18 实测）：未配置 credential helper 时 `git push https://github.com/...` 报 `could not read Username`（沙箱内无 `/dev/tty`）；先跑一次 `gh auth setup-git` 即可让 git 走 gh 的 keyring token，之后 push 直达 GitHub 认证层（403 再按上条查 PAT 仓库权限）。
- **沙箱杀重量级 git 操作**（2026-08-18 实测）：`git subtree split`（内部 fork 大量子进程）与跨大树 `git checkout`（切换 119 技能的整树）会被沙箱静默终止（空输出 + exit 1），且可能留下**半成品工作树**（数百文件被删、`index.lock` 残留）。规避：① subtree split 尽量在用户终端跑；② 必须沙箱内做子树同步时，用**工作区 scratch 仓库**方案——`git init 工作区/.gh-sync-tmp` → `git fetch <github-url> main` → checkout FETCH_HEAD → `cp -r` 铺入目标目录 → 配置 user.name/email → commit → push（快速前进，零 force）；③ 恢复半成品：确认无 git 进程后 `rm .git/index.lock` + `git restore .`（索引完好时零损失）。⚠️ 沙箱对 Windows 临时目录（如 `<TEMP>`）的 ls 不可见（git 可写）——scratch 目录务必放工作区而非 /tmp。

---

## 9. Quick reference (cheat line)

```
git status                          # always start here
git log --oneline -10               # read history before branching
git checkout -b feature/<name>      # feature branch
git add <files> && git commit       # per logical unit (Conventional Commits)
git stash / stash pop               # pause / resume WIP
git revert <sha>                    # safe undo of shared history
git push  ← STOP: ask user first   # hard rule
```
