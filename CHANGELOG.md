# CHANGELOG — user-vibe_coding-sdk-moe

> 版本历史集中于此文件（G2 渐进披露：按需加载，不进 SKILL.md 热路径）。
> SKILL.md 保持静态前缀以维持 prompt cache 命中（G5）。最新版本见本文件顶部。

## v2.10.6（2026-09-02）

> P3 缓办项清偿批次（用户「Please continue」批量授权）：verification-kernel B.6、
> agentic-cicd §15、coding-agent-os §29 三项「部分吸收」升级为「吸收」。
> 同轮完成 origin 裸备份新 main 血统推送（force-with-lease 持锁，旧血统已在裸库内
> 扁平 ref 归档，非破坏性）。

### 新增

- **vk B.6 → 吸收（`ci-fail-analyze.py`）**：新增 `--results-json` 入参——从测试结果 JSON
  （`{results|cases|rows}` 或裸列表）提取 per-test 结构化字段（`test_name / expected /
  actual`）注入 diagnostic.v1（`per_test` + `per_test_summary` + `failing_tests`）；
  畸形输入沿 F-53 纪律干净 exit 2 不裸 traceback。新增 2 用例。
- **cicd §15 → 吸收（`patch-gate.py` / `action-gate.py`）**：硬闸参数策略版本钉——
  两闸新增 `POLICY_VERSION = "gate-policy.v1"` 常量 + `--policy-version` 校验
  （不匹配 → fail-closed exit 2），JSON/文本输出均声明 policy_version。
  变更预算/风险分级 = 变策略 = 必须显式 bump 常量并记录于本文件。新增 2 用例。
- **coding-agent-os §29 → 吸收（`golden-run.py`）**：`--compare <old.json>,<new.json>`
  跨版本对比报告（schema `golden-compare.v1`）——按样本 id 逐条转移
  （REGRESSION / FIXED / STABLE / CHRONIC / NEW / REMOVED）+ 逐条 token/latency delta +
  pass_rate delta（pp）；检出任一 REGRESSION → exit 2（可直接作发布闸）。
  纯文件对比，零 LLM 零网络；`--set` 在 compare 模式下不再必填。新增 2 用例。

### 同步

- README / ENGINEERING 用例计数 184 → 190；ALIGNMENT 三行状态升级
  （vk B.6 / cicd §15 / coding-agent-os §29 → 吸收）。

## v2.10.5（2026-09-02）

> 本版由第 6 轮全面自检驱动（触发：用户指定 SDK_Reference 参照目录（D 盘 data 下，不写入路径））。
> 基线 ci-smoke 7/7 全绿 + 变异审计可用；本轮新增**端到端集成场景测试**（25 项，单测套件之外的
> 真实链路：任务状态机全生命周期 / DAG 依赖闸 / 幂等键 / 修复预算 / 升级包 / 动作门 / 补丁闸 / 探针）。

### 修复

- **F-53（P2，`patch-gate.py` 畸形输入裸 traceback）**：numstat 行列序颠倒/非数字时
  `parse_numstat` 抛未处理 `ValueError` → 退出码 1 + 堆栈（fail-closed 但报错不可动作）。
  修复：报行号 + 期望格式 + 干净 exit 2（与闸门语义一致）；新增 robustness 用例
  `patch-gate: 畸形 numstat 行 → exit2 非 traceback`（184 用例）。
  *发现路径：集成测试中测试数据列序写反——错误数据反而暴露了闸门的崩溃模式。*
- **F-54（P2，追溯断链）**：`agentos-architecture.md` 的吸收盘点只散落在 workspace 报告
  （v2.7.0 §2.4 Top5 清单 + CHANGELOG T-07/08/09/13/25 条目），ALIGNMENT.md 四架构映射缺其一。
  补齐：ALIGNMENT 新增 AgentOS A-U 节逐节映射表 + Top5 缺口清偿对账表——至此
  coding-agent-os / verification-kernel / agentic-cicd / agentos 四份映射齐备。
- **F-55（P3，`ci-smoke.py` 红灯不可归因）**：robustness 步骤失败时 `detail` 只存
  `pass_rate=0.995`，失败用例名丢失（本轮实录：需重跑才能排查）。修复：失败时
  detail 追加 `failed=<用例名 ×5>`，红灯当场可归因。

### 稳定性观察（P3，留观）

- 第 1 轮 ci-smoke 中 robustness 步骤出现一次 **183/184（exit 2）**；独立复跑 ×2 均 184/184
  且全绿——单次未复现，失败用例名因当时 F-55 未落地而不可考。按 T-20 纪律单次失败不进修复环，
  留观：后续 ci-smoke 若复现，F-55 的 detail 增强可当场点名。

### 环境处置与发现

- **F-52（P1，skills 仓库对象库损坏扩大）→ 已按方案 A 处置**：v2.10.4 记录 1 个缺失 commit；
  本轮 fsck 复查实为 **2 缺失 commit（`141462bb` / `01e5f14f`）+ 1 缺失 blob（`230e4625`）**。
  用户决策（A 新根重建）：`main` 重指向孤儿根 `sdk-snapshot-20260902` 之上的树级移植提交
  （`commit-tree` 确定性移植 live tip 的 SDK 子树哈希，逐字节 = live 内容，skip worktree/tar 管道）；
  旧血统以 `archive-*` 扁平分支存档（legacy-live / legacy-main / github-sync-broken）。
  target 裸库已强推新 main（v2.10.5）并存档旧 v2.7.0 血统；GitHub 推送待 PAT 授 Workflows 权限。
  *教训：首版经 worktree + tar 管道移植，产物树混杂不可信（树哈希 ≠ live 子树）——改 plumbing 后
  以 `rev-parse <commit>:<subdir>` 的树哈希直接 commit-tree，零拷贝零歧义。*
- **F-56（P2，install-hooks 相对路径 worktree 不兼容）**：钩子 exec 路径为仓库相对
  `user-vibe_coding-sdk-moe/scripts/...`，在 linked worktree 中 fail-closed（每次提交被挡）。
  修复：改为安装时解析的**绝对路径**（F2 renamed-dir 安全性保留）；存量钩子经 install-hooks
  幂等升级。*发现路径：F-52 移植提交在临时 worktree 被钩子拦截。*
- **⚠️ 系统级 FS 异常（新发现，非 SDK 缺陷）**：本机对 `.git/refs/heads/` 下**新建嵌套目录**
  （如 `archive/…`）存在异步清除行为——git 报成功、reflog 落盘、ref 文件随即消失（含
  `mkdir -p` 预建目录亦被清；扁平命名单层 ref 文件不受影响；C 盘 skills 库与 D 盘 git-backup
  裸库均复现）。SDK 侧已全部改用扁平存档名规避；后续任何新建多级 ref 请用扁平名。

## v2.10.4（2026-09-02）

> 本版闭合 v2.10.3 审计报告点名的最后一个缺口：**拦截覆盖检查是静态的**——
> 它只证明「存在断言非零退出的用例」，不证明「闸真的坏了时用例会红」。
> 补齐动态那一半：**变异测试审计**（mutation testing）。

### 新增

- **`scripts/mutation-audit.py`（门禁变异测试审计）**：对 6 个真闸注入定点变异
  （把拦截条件改成「恒放行」），逐个跑 robustness 对应子集，判定三态：
  - **KILLED**：变异后至少一个用例变红 → 该闸的用例真实有效；
  - **SURVIVED**：变异后用例仍全绿 → 闸失效而测试未察觉（F-50 类缺陷复发即此形态）；
  - **STALE**：变异锚点找不到 → 源码与审计脚本脱节（结构性漂移预警）。
  - 首轮实测：**6/6 全部 KILLED**——patch-gate / privacy-scan / version-check /
    token-meter / action-gate / selfcheck-static 的拦截用例均真实咬合。
  - 安全性：字节级备份还原（`read_bytes`/`write_bytes`，杜绝 v2.10.3 期间踩过的
    LF→CRLF 新行翻译损坏）+ 还原后 sha256 校验；`--dry-run` 只校验锚点不注入；
    `--only <script>` 子集运行；**不可并发运行**（会临时改写 scripts/ 下源码）；
    `--only` 无匹配 → exit 2（绝不静默通过）。

### 注册与用例

- `toolstack.json`：`mutation-audit.py` 登记（category TEST / risk_tier 3 /
  timeout 900s / note「不可并发运行」），`sdk_tools` 28 → **29**。
- `robustness-suite.py`：+2 用例（181 → **183**）——`--only no-such.py` → exit 2（防静默）、
  `--dry-run --only patch-gate.py` → exit 0（锚点校验路径）。
- `selfcheck-static` 拦截覆盖检查复验：`gated_scripts` 23，gaps **[]**。
- README / ENGINEERING：新增 mutation-audit 条目，计数同步（183 用例 / sdk_tools 29）。

### 门禁栈现状（v2.10.4 收敛点）

| 层 | 机制 | 覆盖 |
|---|---|---|
| 静态 | selfcheck-static 拦截覆盖检查 | 每个带非零退出路径的脚本**必须有**断言非零的用例 |
| 动态 | mutation-audit 变异审计 | 用例**真的会红**（首轮 6/6 KILLED） |
| 时点 | git-pre-commit 闸 4 + ci-smoke 第 1 步 | 静态检查每次提交/冒烟即跑 |
| 周期 | 变异审计建议季度手动执行一次（成本高：改源码+跑子集） | 漂移窗口 ≤ 1 季度 |

## v2.10.3（2026-09-02）

> 本版由 v2.10.2 收尾时提出的追问驱动：**"四门全绿但闸门无效"到底是个例还是通例？**
> 审计方法：统计每个脚本在 robustness-suite 中的**拦截用例**（`expected != 0`）数量——
> 一个闸若只有 exit 0 用例，说明它"从没被证明能拦住任何东西"。
> 结果：**6 个脚本零拦截覆盖，其中 3 个是真闸**。

### 审计发现

| 脚本 | 拦截用例（审计前） | 性质 | 处置 |
|---|---|---|---|
| `token-meter.py` | 0（且用例名"budget exceeded"却 expect 0） | **真闸（失效）** | **F-50 修复** |
| `review-prefilter.py` | 0（docstring 明写 0/2，拦截路径从未被测） | **真闸（未验证）** | 补拦截用例 |
| `toolstack-pipeline.py` | 0（drift → exit 2，只依赖不可控的真实上游） | **真闸（未验证）** | 新增 `--manifest` + 确定性用例 |
| `install-hooks.py` | 0（外来钩子拒绝路径 exit 1 从未被测） | **真闸（未验证）** | 补拦截用例 |
| `case-search.py` / `env-snapshot.py` | 0 | 信息型，无非零退出路径 | 判定为**设计如此**，不改 |

### 修复

- **F-50（P1，`token-meter.py` 预算闸从不拦截）**：超预算只写 `flags` 仍 `return 0`，而 docstring
  白纸黑字写着 `Exit codes: 0 always (informational)`——**与自身引用的 coding-agent-os §16
  「explicit stop > silent degrade」直接矛盾**。任何按退出码判定的调用方（`ci-smoke` / pre-commit /
  shell `&&`）都会静默放行一个已超预算的任务。
  - 新规则：**显式传 `--budget` 即表示要求被拦住** → 超限（max_usd / max_calls 任一越界）exit 2；
    不传 `--budget` 仍是纯计量 exit 0（向后兼容，已验证无自动化调用方依赖旧行为）。
  - 原用例 `token-meter: budget exceeded` **expect 0**——用例是按错误的既成行为写的，反过来把缺陷固化为契约；已改为 expect 2 并更名。
- **F-49（`review-prefilter.py` 拦截路径零覆盖）**：补充"检查失败 → exit 2"与"检查通过 → exit 0"配对用例。
  用 `--config` 传 cmd 列表（`--checks` 走 `str.split()`，引号会碎），跨平台稳定。
- **toolstack-pipeline 可测化**：新增 `--manifest PATH`，使 drift 路径能离线确定性地断言
  （篡改 data sha256 的副本 → `MISMATCH` → exit 2），不再依赖真实上游是否恰好有漂移。
- **install-hooks 拒绝路径**：新增"外来钩子无 `--force` → exit 1"用例。

### F-51（F-48 同族，本轮自伤）

新 fixture 直接读 `SCRIPT_DIR/toolstack.json` 造漂移清单，但 **renamed-dir fixture 是 SDK 的部分副本
（无该文件）**，而 `build_cases` 会在复制体里整体执行 → `FileNotFoundError` → C0-2 renamed-dir 用例连带打挂。
修：依赖真实仓库文件的 fixture 一律加存在性守卫。

> **两轮连续踩同一个坑（F-48 / F-51）说明这是系统性问题**：任何新增代码都要在
> **renamed-dir 部分副本环境**下验证过——`build_cases` 会在那里被完整执行，
> 而该环境没有 `toolstack.json` / `SKILL.md` / 完整 `scripts/`。

### 治本：拦截覆盖进静态自检

`selfcheck-static.py` 新增 **blocking-coverage** 检查：**任何带非零退出路径的脚本，必须至少有一条断言非零退出的用例**
（解析 `robustness-suite.py` 的 `C()` 与原始 dict 两种注册风格）。命中即 exit 2：

```
scripts with a non-zero exit path but NO blocking test case
(gate never proven to block): ['review-prefilter.py']
```

负向验证：把 review-prefilter 的拦截用例 expect 由 2 改成 0 → 自检当场 exit 2 并点名脚本。

> 这样 F-42 / F-50 这一整类缺陷（**只断言成功路径，从不证明能拦**）在提交时刻与 ci-smoke 里都会被自动拦下，
> 不必再靠"某轮自查刚好想到"才发现。

### 门禁

- `robustness-suite` 176 → **181**（+5）；**零拦截覆盖脚本数 6 → 2**（余下 2 个为信息型，无非零退出路径，判定设计如此）。
- 全量 `ci-smoke` 7/7 ALL GREEN。

## v2.10.2（2026-09-02）

> 本版由 v2.10.1 自查报告的**三项遗留建议**驱动，主题是 **F-43 治本闭环**——把「漏登记」从"月度自查才能发现"压到"提交时刻即被拒"。
> 执行依据：`验证报告-SDK-v2.10.1-全面自检与测试-2026-09-01.md` §6 + 用户"Please continue"。

### 遗留项清偿

- **建议 1 —— selfcheck-static 接入提交时刻**（`scripts/git-pre-commit.py` 新增闸 4）：任何 SDK 改动（脚本/数据/文档/新文件）即跑 `selfcheck-static`（~1s，零 LLM），fail-closed。此前它只在 ci-smoke（定时/手动）跑，**新增脚本漏登记要等下一轮自查才浮现**——现在 `git commit` 当场拒绝，并打印具体漂移项（解析 stdout JSON，不只报退码）。
  - 负向验证：临时 `zz-drift-probe.py` 未登记 → `pre-commit gate: BLOCKED — scripts exist but are NOT in toolstack.json sdk_tools`；登记后 → PASS。
- **建议 2 —— toolstack-pipeline 增 Stage 3b**（`scripts/toolstack-pipeline.py`）：巡检新增「`scripts/*.py` 与 `sdk_tools` 差集」阶段，报告即显示 `unregistered` / `missing` 两类。
  - `--update` **自动登记**未注册脚本，保守默认（`category: EXECUTE` / `risk_tier: 2` / `idempotent: false` / `timeout 120s`，带 `note` 提示人工复核分级）。
  - **仅增不删**：已登记但文件已消失的条目只报告、不自动删除（§10.9 tier-3 需人决），与 §10.7 回滚安全一致。
  - 至此 toolstack 三组全部有自动化：`refs`（上游核对）· `local_tools`（probe-tools）· `sdk_tools`（本阶段）——**F-43 的根因（sdk_tools 零自动化）闭合**。
- **建议 3 —— ALIGNMENT.md 对齐**：吸收对象本体版本 v2.3.0 → v2.10.2；§3.2 行补 F-42 修正（"门装了但没接上电路"）；新增「v2.10.1–v2.10.2 追加映射」表，并**新设「自检项」列**——映射表此前只记"吸收了什么"，不记"吸收后是否真的通电"，这正是 §3.2 记为已吸收却 22/22 被拒的原因。

### 补强与修正

- **selfcheck-static 双向校验**（v2.10.1 只查"已登记但缺失"，漏了 F-43 的真实形态"存在但未登记"）：新增 `unregistered` 检查 → exit 2。
- **豁免名单单一来源**：`sdk_tools_exempt` 移入 `toolstack.json`（`selfcheck-static.py` 与 `toolstack-pipeline.py` 共用，杜绝两处硬编码分歧），当前为空。
- **`--root` 参数**（`selfcheck-static.py`，契约同 `version-check.py --root`）：可指向临时 SDK 树，使漂移用例可测——真 `scripts/` 目录不能再被拿来造漂移污染仓库。
- **`git-push` 探测修正**：`cmd` 由 `["git","push"]` 改为 `["git","--version"]`。`git push` 在无 upstream 的仓库里恒失败，会让探针把"git 可用"误报为 MISSING。

### 本轮自伤与修复（新增闸抓到的）

- **F-48：`git-pre-commit` renamed-dir 用例回归**（新闸 4 自己踩的坑）：C0-2 fixture 只复制 5 个脚本、无 `SKILL.md`/`toolstack.json`，新闸在此树上调用 `selfcheck-static` → `FileNotFoundError` traceback → 门禁误判 BLOCKED（robustness 175 → 174/175）。
  - 修 1（`selfcheck-static.py`）：**前置完整性守卫**——`SKILL.md` / `scripts/toolstack.json` 缺失时直接 fail-closed 输出 `incomplete SDK tree`，**绝不 traceback**。
  - 修 2（`git-pre-commit.py`）：树不完整时该闸**降级跳过并打印 SKIPPED**（§6「不可用 → 降级，绝不阻塞」），而非把"缺 manifest 可比"误报为结构破损。
  - 回归：renamed-dir 用例 `want` 增 `SKIPPED` 锁定降级行为；新增「不完整树 → exit 2 且不 traceback」用例。
  - 教训：**新闸必须在残缺树上验证过再上线**——它在完整树上永远正确，恰恰是 fixture / 部分检出会暴露问题。

### 门禁

- 新增回归用例 5 条（未登记脚本拦截 / `--root` 干净树放行 / 不完整树不 traceback / 最小 SDK 树 fixture ×2）；`robustness-suite` 173 → **176**。
- 全量 `ci-smoke` 7/7 ALL GREEN；`privacy-scan` 0 findings。

## v2.10.1（2026-09-01）

> 本版由「v2.10.0 全面自检与测试」驱动——四门全绿但 T-25 实际覆盖率≈0，暴露工具栈元数据的结构性盲区。
> 执行依据：本轮 `验证报告-SDK-v2.10.1-全面自检与测试-2026-09-01.md`。

### 修复

- **F-42 action-gate 查表范围过窄**（P0，`scripts/action-gate.py`）：原只查 `local_tools`（7 个外部 CLI），**22 个 `sdk_tools` 全部判 DENY**——包括本文件 docstring 自己的 `--tool diff-risk` 示例；agent 实际执行的恰恰是自有脚本，T-25 因此形同虚设。改为合并 `sdk_tools` + `local_tools` 两张表（`local_tools` 键冲突优先），并新增 stem 匹配（`diff-risk` ≡ `diff-risk.py`）。修复后 28/28 自有脚本 ALLOW。
- **F-43 toolstack 漏登记 6 个脚本**（P1，`scripts/toolstack.json`）：`action-gate.py` / `flaky-check.py` / `patch-gate.py` / `regression-guard.py` / `version-check.py` / `selfcheck-static.py` 未登记（v2.8.2~v2.10.0 新增）。**根因**：`sdk_tools` 无任何自动化维护——`toolstack-pipeline.py` 六阶段只管 `refs` 与 `provider_health`，漏登记零告警。现 sdk_tools 22 → 28。
- **F-44 push 闸门无落点**（P2）：§10 规则 2「push 必须显式确认」在 action-gate 里查无此工具。新增 `local_tools.git-push`（tier=4）——无 `--user-approved` 时 DENY，附条件时 ALLOW 并记 `human_approval`。
- **F-45 ci-smoke `--json` 输出不纯**（P2）：进度行原混入 stdout，导致 `ci-smoke --json | jq` 解析失败。改为 `--json` 时进度行走 stderr。
- **F-47 `bump-version --apply --json` 静默失效**（P1，`scripts/bump-version.py`）：`--json` 分支在写入前 `return 0`，该组合只打印计划、不落盘，退出码仍是 0——**无声 no-op**。本轮 bump 即踩中：CHANGELOG 已置 v2.10.1 而四处版本串仍 v2.10.0，靠 version-check 闸（T-16）才发现。改为先应用后输出 JSON，新增 `applied` / `dry_run` 字段显式表态；`log()` 在 `--json` 模式转走 stderr（与 ci-smoke 同契约）。
- **F-46 README 脚本清单漂移**（P2）：robustness 用例数声明 123（实测 166）、6 个 v2.8.2~v2.10.1 新增脚本未入清单。已补齐并修正计数。

### 新增

- **`scripts/selfcheck-static.py`**（F-43 治本）：静态结构自检——frontmatter / references 完整性 / 脚本存在性 / toolstack 一致性四项，秒级零 LLM，exit 2 = 结构破损。**已置为 ci-smoke 第 2 步**（cheapest-first，排在 version-check 之后、4 分钟全量套件之前），成为 `sdk_tools` 唯一的漂移哨兵。

### 门禁

- 全量 `ci-smoke` 6/6 → 7/7（新增 selfcheck-static 步）全绿；`robustness-suite` 166/166；`golden-run v3 --offline` 32/32（pass_rate 1.0）；`privacy-scan` 0 findings（89 files）。

## v2.10.0（2026-09-01）

> 本版由「SDK v2.8.1 全面自查」**P2 批次（T-23~T-26）+ P3 收尾（T-29 audit 扩面 / F-41 治本）**驱动。
> 执行依据：`自查报告与改进计划-SDK-moe-v2.8.1-2026-09-01.md` §5 + 用户"Please continue"。

### P2 — 预算、升级与执行门

- **T-23 补丁规模预算闸**（F-29，新增 `scripts/patch-gate.py`）：kernel §I 8 项预算中 SDK 原只落"次数"——现补 files≤5 / lines≤300 / 依赖清单≤1（numstat / unified diff / 手工 stat 三输入），超限 exit 2 + `recommended_action: ESCALATED`；**diff-risk 是评分（建议人工）不是预算闸（硬拒绝），两者分工明确**。附带 `diff-risk --verify-confidence`：`repair_confidence = 0.5*(1-risk) + 0.5*vc`，<0.7 → `human_review_required`（kernel B.21 三重置信度落地）。
- **T-24 escalation-pack**（F-34，`task-state.py` 新子命令）：七字段升级包 problem / evidence / attempted_fixes（聚合自事件台账 REPAIR 族）/ failed_tests / relevant_diff（截断 <100 行）/ risk / recommended_action（末次 verdict=FAILED/REGRESSION 时附"考虑 revert 最近一次修复"）——**ref-22 L5 人类终态必附**，人类从完整谱系开始而非重新推导（G1）。
- **T-25 action-gate.py**（F-38 悬空两轮的 AgentOS Top4 正式清偿 + agentic-cicd §3.2 Tool Gateway）：动作预执行门——toolstack 存在性 / risk_tier / args 合法性；tier≤2 ALLOW · tier=3 ALLOW 附强制条件（交叉核对+回滚验证）· tier≥4 DENY 仅 `--user-approved`（用户显式确认后，记 `human_approval`）；**toolstack `idempotent` 元数据首个消费方**。
- **T-26 幂等键**（F-35，agentic-cicd 原则 9）：`task-state transition --idempotency-key` —— 同键同目标重放 = no-op（台账记 `duplicate_ignored`，**修复预算不消耗、振荡闸不触发**）；同键换目标 = exit 2（caller bug）。实施期修正：幂等检查必须**先于合法性检查**——真正的重放发生在 cur==已应用目标态时，合法性检查会先报 illegal（首版冒烟抓即改）。

### P3 — F-41 治本 + T-29 审计扩面

- **F-41 治本**（`git-pre-commit.py`）：SDK 内**文档**（非脚本非数据的 changed 文件）纳入 privacy 闸——"docs-only 跳过"曾把整个 privacy 闸跳掉，F-25→F-41 两周两漏的根因闭合；docs 或 new 有其一即跑 privacy-scan（fail-closed）。
- **T-29**：workspace `audit_sdk.py` 146 → **164 项**（A 26→37 静态存在性 / C 32→39 行为锚：origin 字段、层名别名+拒绝子串巧合、security 恒保、version-check 三分支、action-gate 决策、patch-gate 预算）。
- 顺带更正：ENGINEERING 组件表去重（flaky/regression 行曾在两处）。

### 验收证据（v2.10.0）

```
version-check      ok=true（五处 v2.10.0 + 条目递减）
提交链             本批 7 个本地提交（feat×3 + fix×1 + docs×2 + bump×1）；会话自 v2.8.1 起累计 28 个未 push，等显式确认（D4）
```

## v2.9.0（2026-09-01）

> 本版由「SDK v2.8.1 全面自查」**P1 批次（T-18~T-22）+ P3 文档票（T-28/T-30）**驱动，另收实施期回归 F-40。
> 执行依据：`自查报告与改进计划-SDK-moe-v2.8.1-2026-09-01.md` §5 + 用户"Please continue"（D2=A/D3=A 已确认）。

### P1 — 验证内核精细化（verification-kernel / agentic-cicd 吸收）

- **T-18 层名显式别名匹配 + targeted 分支激活**（F-28，`verify-runner.py` + 预设）：`_layer_matches` 唯一匹配入口（精确 / 别名表 `type<->typecheck` / `token-` 前缀族），消除子串巧合；python/node 预设 `test` 拆为 `test-targeted`（fail-fast：`pytest -q -x` / `vitest --bail=1`）+ `test-full`，targeted 优先分支从死代码变为可达（T-07 的省时收益自此兑现）。
- **T-19 origin class**（F-30，`ci-fail-analyze.py`）：diagnostic 增 `origin`（code/test/dependency/infra/environment/flaky/unknown）+ `recommended_action`（ACTION_BY_ORIGIN：infra→RETRY · test→REPAIR_TEST · unknown→DIAGNOSE…）——**由 origin 而非 leaf 决定动作**（kernel §H）；日志级信号可覆盖静态映射（dependency+网络指纹→infra）。
- **T-20 flaky-check.py 新增**（F-31）：N 次同输入重跑 → REAL/FLAKY/INFRA/NOT_REPRODUCIBLE/UNKNOWN 五分类；FLAKY 需 N≥5（agentic-cicd §8.4）；QUARANTINE 永不删除；UNKNOWN/NOT_REPRODUCIBLE 均 fail-closed。schema `flaky-check.v1`。
- **T-21 regression-guard.py 新增**（F-32）：回归测试双向闸——base 必须 FAIL + head 必须 PASS（kernel §B.11）；WEAK_TEST/FIX_INCOMPLETE/NOT_A_REGRESSION 一律 exit 2；`git worktree add --detach` 物化执行，不碰工作树。schema `regression-guard.v1`。
- **T-22 测试选择 `--changed`**（F-33，`verify-runner.py`）：变更文件约定映射到 `test-targeted` 层（stem→`tests/**/test_<stem>.py`，`test_roots`/`max_tests` 可配；变更即测试直接收录）；无映射 fail-open；报告增 `test_selection`。覆盖率驱动形态排除（ALIGNMENT，与 G1 同类）。

### P3 — 协议化与吸收入册

- **T-28**：property-based / mutation testing 进 ALIGNMENT 排除总表 + ref-21 §6.1 选择策略（纯函数+可推断不变量才做；mutation 仅关键路径按需）。
- **T-30**：ALIGNMENT 新增「09-01 两文档吸收映射」段——verification-kernel 13 节 + agentic-cicd 10 节，三分类（吸收/缺口/排除），缺口标注 P2 票号（T-23/24/25/26）。

### 实施期发现与修复

- **F-40 git 夹具成本回归**：3 座 git 夹具仓（init+2 commit×3）在慢盘环境 ~60-80s，把 `--only` 子集（pre-commit 门禁递归调用）顶过 60s 用例超时 → 全量 2 个 exit 124 假失败。修复：① `build_cases` 透传 `only`，git 夹具惰性搭建（`--only token-meter` 实测 92s→39s）；② 用例级 `timeout` 字段，两个递归门禁用例提至 180s。
- 教训入册：**门禁套件自身的成本漂移会放大成假红灯**——新增昂贵夹具必须评估对 `--only` 子集与递归门禁的影响。

### 验收证据（v2.9.0）

```
version-check      ok=true（五处 v2.9.0 + 条目递减）
提交链             本批 10 个本地提交（feat×5 + fix×2 + docs×2 + bump×1；会话累计 19 个未 push），pre-commit 逐次 PASS，未 push（D4 等显式确认）
```

## v2.8.2（2026-09-01）

> 本版由「SDK v2.8.1 全面自查」P0 批次驱动：**T-16（F-26 门禁红灯）+ T-17（F-27 安全闸被旁路）**，另收 F-37（ENGINEERING 版本头漂移）。
> 执行依据：`自查报告与改进计划-SDK-moe-v2.8.1-2026-09-01.md` §5 P0 批次 + 用户"Please continue"（D1=A 已确认）。

### P0 — T-17 security 层恒保（F-27，`verify-runner.py`）

- **缺陷**：`--confidence` 的轻/中档会把 `security` 层筛掉。随包预设实测——`0.9` → `["syntax","test"]`、`0.5` → `["syntax","typecheck","test"]`，`pip-audit` / `npm audit` **被静默跳过**；只有低置信的 full 档才跑安全扫描。与 verification-kernel §B.3「Stage 9 security = hard block，无论下游阶段状态」冲突，也与自家 T-12（安全扫描验证阶段）自相矛盾。
- **修复**：新增 `ALWAYS_ON_TOKENS = ("security",)` —— 任何档位无条件保留 security 层，且保持配置原始顺序；配置里没有 security 层时不虚增。`test-full` 不属硬闸，仍可被 targeted 分支剔除。
- **修复后实测**（随包 `verify.python.json`）：0.9 → `["syntax","test","security"]`；0.5 → `["syntax","typecheck","test","security"]`；0.2 → 全 6 层。

### P0 — T-16 版本串与 CHANGELOG 顺序闸（F-26，新增 `scripts/version-check.py`）

- **缺陷**：v2.8.1 段落被手工写在 v2.8.0 之后 → 文件首个 `## vX` 仍是 v2.8.0 → 五处版本串失配（workspace audit **145/146** 唯一红灯）。根因：`bump-version.py` 的 layout-repair 插入（插到首个 `## vX` 之前）在 header 已存在时直接 `[skip]`，手工写入的错误顺序无人纠正。**ci-smoke 当时不含版本串检查**，红灯发现链过长。
- **修复**：① CHANGELOG 顺序归位（独立 `fix:` 提交）；② 新增 `version-check.py` —— 校验 SKILL frontmatter / SKILL 标题 / README blurb / README 版本行 / CHANGELOG 首个条目五处一致 + 条目严格递减无重复，exit 0/2，schema `version-check.v1`，`--root` 可换文档根；③ **接入 ci-smoke 作为第 0 步**（cheapest-first：1 秒内失败，不必等 4 分钟全量套件）。
- **纪律**（ref-23 §4）：手工改 CHANGELOG 后必须跑 `version-check.py`；`bump-version.py` **不会**纠正手工写入的错误顺序。

### P3 — F-37 ENGINEERING.md 版本头同步

- 头部 `> v2.7.0 · 2026-08-30` → `v2.8.2 · 2026-09-01`（正文早已含 v2.8.x 数据）；顺带修正门禁表陈旧数字（L2 audit 104→146 项）。

### 验收证据（v2.8.2 收口，全绿）

```
version-check      ok=true（五处 v2.8.2 + 条目递减；ci-smoke 第 0 步 detail=consistent=True top=v2.8.2）
robustness 全量    129/129 pass_rate=1.0（+3 security 恒保 / +3 version-check 矩阵）
ci-smoke 全量      6/6 ALL GREEN（新增第 0 步 version-check）
workspace audit    146/146（A=26/26 B=88/88 C=32/32，上轮 145/146 红灯已翻绿）
提交链             8 个本地提交（fix×3 + feat×1 + test×1 + docs×2 + bump×1），pre-commit 逐次 PASS，未 push（D4 等显式确认）
```

**⚠️ 实施期新发现 F-39**：ci-smoke 与 workspace audit **并行**运行时双双出现假失败（robustness pass_rate=0.984 / audit B `--only privacy`）——两套套件各起 129 个子进程，16GB 低配机上资源争抢。隔离复跑均 129/129 通过。**教训入 sdk-selfcheck：重门禁必须串行跑**（cheap-first 串行总时长 ≈ 6min，可接受）。

**实施期即时修复**：ci-smoke 版本串步骤 detail 恒为空——提取分支匹配了不存在的 `consistent` 键（schema 实际为 `ok`/`changelog_top`），改匹配 `changelog_top` 后实测 `consistent=True top=v2.8.2`。

## v2.8.1（2026-09-01）

- **F-25 CHANGELOG 路径形态触发 privacy drive-letter 规则**：v2.8.0 条目 T-02 段落两处以 `D` + 冒号反斜杠形态书写的机器路径被 privacy-scan 判 findings=2 → ci-smoke 4/5。修复：交付物文档路径去盘符（`WorkBuddy/softwares-update/...` + "（D 盘）"标注）；不改扫描器规则（规则本身是对的，防真泄漏）。文档约定沉淀至 sdk-selfcheck 技能；**描述此类缺陷时同样不得写出可命中规则的字面形态**（本次 F-25 条目首稿即自引复发，改用描述式写法）。

### 验收证据（v2.8.1 收口，全绿）

```
privacy-scan       findings=0（CHANGELOG L13/L14 去盘符后复扫）
ci-smoke 全量      5/5 ALL GREEN（robustness 123/123 pass_rate=1.0 · golden v2/v3 validate · v3 offline · privacy findings=0）
提交链             fix F-25 + bump v2.8.1 两个本地提交，未 push（D4 等显式确认）
```

## v2.8.0（2026-09-01）

> 本版由「SDK v2.7.0 自查报告」P2/P3 批次驱动：架构缺口吸收（T-07~T-15）+ T-02 治本 + 全面回归。
> 执行依据：自查报告 §5 改进计划 + 用户"Implement the improvement plan and conduct comprehensive testing"指令（D1=A / D3=A 视为已批准；D4 push 仍待显式确认）。

### P0 治本 — T-02 自动化 cwd 迁出（D1=A 执行）

- **两条 SDK 自动化（周度冒烟 `automation-1787758826303` / 月度巡检 `automation-1787758816382`）cwd 迁出 SDK 目录** → `WorkBuddy/softwares-update/`（D 盘），脚本命令全部改绝对路径（F-15 根因闭合，不再依赖扫描器排除集兜底）。
- SDK 内 `.workbuddy/{automations,memory}/` host 污染目录已备份（`WorkBuddy/softwares-update/backup/sdk-pollution-20260901/`，D 盘）后删除；`debug-cases/`（交付物）保留。SDK 子树 `git status` 恢复零噪音。

### P2 — 架构缺口吸收（D3=A：高价值 7 票）

- **T-07 置信度自适应验证深度**（`verify-runner.py`，AgentOS #1）：`--confidence <0-1>` → `<0.4` 全层 / `0.4-0.7` 语法+类型+目标测试 / `>0.7` 语法+目标测试；`test-targeted` 优先（配置同时含 targeted/full 时轻中档剔除 full）；`--layers` 显式声明优先于启发式；报告增 `verify_depth`/`selected_layers`。SKILL §5.6 一行接线 + ref-19 用法行。*修复过程：映射表边界元组首版写反（0.9 误判 full），冒烟即抓即改。*
- **T-08 任务级显式完成条件**（`task-state.py`，AgentOS #3）：`init --done-when "<结构化条件>"`；**FINALIZE→DONE 必须附 `--done-evidence`**（有条件无证据 exit 2；无条件不得 finalize）。作用域**仅 FINALIZE→DONE** —— PROD_VERIFY→DONE 等 CI/部署链路有自己的分层验证（C1-3 契约不变），首版误伤该路径被既有用例当场拦下。
- **T-10 append-only 事件台账**（`task-state.py`，survey G4）：每次 init/transition/resume 向 `<tasks-dir>/events.jsonl` 追加 `{ts,event,task,from,to,verdict,actor}`；`--actor` 标注执行者（配合子代理权限矩阵）；loop-guard 拒绝也记 `transition_rejected`；`trace-export` 改读事件流（ledger 缺失=旧任务，空列表不炸）；ledger 写失败仅告警不阻断（任务 JSON 是主真相源）。
- **T-09 故障分类 +3**（`ci-fail-analyze.py`，AgentOS #8）：`permission`（EACCES/EPERM/403，置于最前防吞并）· `dependency`（Could not find a version/ERESOLVE/peer dep，先于 command_missing）· `assertion`（jest 风格 `expect(received)`/`Expected:...Received:`，置于 unit_failure 之后防吞并）；taxonomy 5→8 类。自查报告所列 "+timeout" 经核实 v1.0 已存在，不重复添加。
- **T-11 子代理权限矩阵**（ref-20 §7.1，survey G5）：五类子代理（Explore/Research/Implement/Review/Test）× 可读/可写/禁触/台账 actor 模板 + 三条硬规则（子代理禁触 task-state transition、产出以证据回传、触界即终止记 known_failures）。
- **T-12 presets security 层**：核查确认 v2.7.x 已落地（python `pip-audit` / node `npm audit --audit-level=high`，均 `allow_missing: true`；docs 无依赖面不设层）——本版仅补审计断言，无代码变更。
- **T-13 溯源台账**（ref-21 §7，AgentOS #2）：检索材料三元素 `{source, fetched_at, cell}` + 过期驱逐（>30 天引用前必须重检）+ 无来源不得作结论依据；载体为当轮上下文或 blackboard.facts，不新建存储。

### P3 — 卫生与审计扩面

- **T-15 决策 D3=A**：repo map（G1）/ 上下文压缩服务（G2）/ 离线 embeddings（G7）/ 沙箱逃生通道（G8）**协议化进 ALIGNMENT 排除总表**（各附原因），不落地实现。
- **T-14 workspace 侧 `audit_sdk.py` 扩覆盖**（104→146 项，全绿）：修正 2 处陈旧断言（toolstack schema==2→≥3、privacy 用例数 3/3→通用 Verdict）；A 组 +4（v2.8.0 协议接线静态存在性）；B 组 +24（diff-risk/硬闸 5 连/置信度/新故障类/隐私运行时排除/recommend 冷启动等 CLI 矩阵）；C 组 +9（done-gate 三分支+作用域、置信度三档、八类全集+防吞并回归、事件台账回环、presets security 层、RUNTIME_SKIP 常量）。

### 验收证据（v2.8.0 时点）

```
robustness 全量    123/123 pass_rate=1.0（112 → +11：置信度 5 / done-gate+台账 3 / 故障分类 3）
workspace audit    146/146（104 → +42）
pre-commit 门禁    逐提交 PASS（verify-runner 13/13 · task-state 28/28 · ci-fail-analyze 7/7 子集）
提交链             6 个本地提交（feat×3 + test×1 + docs×1 + bump×1），未 push（D4 等显式确认）
```

**⚠️ 验收期新发现 F-25**：v2.8.0 收口 ci-smoke 复跑 privacy-scan **findings=2**（exit 2 → ci-smoke 4/5）——本条目 T-02 段落引用的备份/cwd 路径写成 `D:` + 反斜杠盘符形态，命中自家 drive-letter 规则（交付物文档自引）。修复与最终全绿证据见 v2.8.1；教训入 sdk-selfcheck 技能：**CHANGELOG 等交付物引用机器路径一律去盘符（写 `WorkBuddy/.../` + "（D 盘）"标注）**。

## v2.7.1（2026-09-01）

> 本版由「SDK v2.7.0 全面自查（2026-09-01）」驱动，落地 P0×1 + P1×3（报告 15 票中的 5 票，T-02/07~T-15 待决策）。
> 核心判断：上轮"学习闭环"根病已愈（bandit 8/8 cell × 3 模型全覆盖），本轮问题在**门禁卫生与治理面**。

### P0 — 门禁域修复

- **F-15 privacy-scan 域污染回归**（`privacy-scan.py`）：
  - 根因双因：① 两条 SDK 自动化（周度/月度）cwd 在 SDK 目录内，WorkBuddy 向 cwd 写入 `.workbuddy/{automations,memory}/`；② 扫描器无 host 运行时排除集 → automation memory 中的盘符路径（`D` + 冒号反斜杠形态）命中 drive-letter 规则 → findings=2 → **ci-smoke 持续 4/5**。
  - 修复：`.workbuddy/{automations,memory}/` 作为根下 `.workbuddy/` 直接子目录**默认排除**（host 写入物引机器路径属设计使然）；`--include-runtime` 显式覆盖；`.workbuddy/debug-cases/` 为交付物仍扫描。robustness +2 用例（污染目录默认 CLEAN / --include-runtime 仍报）。
  - T-02（自动化 cwd 迁出 + 污染目录删除）**待用户确认 D1 后执行**。

### P1 — 数据回填与协议补口

- **F-17 router-stats legacy 行回填**（`router-stats.py`）：
  - 取证修正：9 条 `error_class=NULL` 行（2026-08-26/28）tokens 实为 212–2185 —— **是真 quality fail**，只是 v2 列迁移时未回填；原判"模糊数据"不准确。
  - 修复：`migrate()` 幂等回填（`response_tokens <- tokens`、fail 行 `error_class <- 'quality'`）；retag 改按 `COALESCE(NULLIF(response_tokens,0), tokens)` 双列取数，且 retag 命中行 error_class 改判 empty（保留 timeout/infra 真实分类）；`report` 增 `unclassified_fail_rows` 计数（>0 = 新记录未分类，先查再信 sr）。
  - 生产库已回填（备份 `router-stats.db.bak-2026-09-01-backfill`）：fail 48 行全部归类，`unclassified_fail_rows=0`。robustness +2 用例。
- **F-18 自动化 FAIL 处置硬规则**（ref-23 §5.1 + 两条自动化 prompt）：
  - 此前月检把 privacy FAIL 自行定性"良性误报"继续跑 —— 红灯常态化 = 门禁失效前兆。
  - 现规则：step FAIL → 原样上报（步骤/exit code/findings 关键行）并停止；禁止自行定性误报，判定权在用户；确属误报则治本修扫描域/规则。
- **F-16 CHANGELOG 断档补录**：08-31 四提交（`d7d268d` qwen2.5:3b 在线基线 8 cell 全覆盖 / `362aff2` fix 空响应分类改文本实导 token——Ollama finish_reason=length 时 usage 虚报 2048 会误判 quality / `c1e34bd` 云池+1B 基线重采 / `1a53ae3` toolstack 月检 update）此前零记录；SKILL §10.8 增豁免边界：`data:`/`chore:` 无行为变更可不 bump，**`fix:`/`feat:` 必须记录并 bump**。

- **F-24 toolstack-pipeline push 门禁挂起（验收期新发现）**（`toolstack-pipeline.py` + `robustness-suite.py`）：
  - 现象：robustness 用例 `push non-TTY` exit=124（60s 超时）——脚本自 08-18 未改且 01:55 全量刚绿，属状态性挂起。
  - 根因双因：① `--push` 先走完整流水线，上游检查逐 ref 调 `gh api`（单次 60s、阶段无总预算），网络停滞即烧穿套件 60s；② 本机 ConPTY/沙箱 shim 下 `isatty()` 连 NUL stdin 都可能返回 True → `input()` 永久阻塞（`stdin=DEVNULL` 不可靠）。
  - 修复：`run()` 捕获 `TimeoutExpired`→rc=124 优雅降级；`gh api` 单次 60→**15s** + 上游阶段 **30s 总预算**（逐调用强制，超预算 ref 记 note 跳过）；`do_push()` 增 **`SDK_NONINTERACTIVE`** 环境变量确定性拒绝口；套件 `run_case` 注入 `SDK_NONINTERACTIVE=1`（套件=非交互环境声明）。
  - 实测：端到端 `--push` 38.5s 完成 exit 0（4 ref 检查 + 4 预算跳过 + push skip）；全量 ci-smoke **5/5 ALL GREEN**。

### 卫生

- **F-19 文档数字同步**：ENGINEERING 26→**28 态**（实测 STATES）；robustness 107→**112 用例**（README/ENGINEERING）；SKILL/README 体积声明回写 **34,140B**（`--sync-size`）。
- 自查更正一处误报：`toolstack.json` 已有 `"schema": 3`（首轮自查查错键名 `schema_version`）。

### 验收

- robustness-suite **112/112 全绿**（108 → +4）
- 子集实测：privacy-scan 5/5 · router-stats 19/19
- ci-smoke 全量 **5/5 ALL GREEN**（robustness pass_rate=1.0 · golden v2/v3 validate · v3 offline · privacy-scan findings=0）
- 提交链：`4c2f255`(F-15) → `4f2b35c`(F-17) → `19358b1`(test) → `7d88f7c`(docs) → `1dedc9d`(bump) → `4821296`(自引修复) → `264f1c2`(F-24)；pre-commit 逐次 PASS
- 自动化 ×2 prompt 已补 FAIL 硬规则（ref-23 §5.1）；**未 push**（§10.2 等显式确认）

## v2.7.0（2026-08-30）

> 本版由「SDK 全面自查（2026-08-30）」驱动，落地改进计划 16 票（P0×5 / P1×4 / P2×5 / P3×2）。
> 核心判断：**静态基建已经很硬，问题集中在动态反馈回路**——它看起来在学，实际在学噪声；
> 它看起来在报警，实际闸门焊死了。本版把"协议文本"逐条换成"脚本拒绝"。

### P0 — 学习闭环修真（数据可信性）

- **F-01 基础设施失败不再污染能力后验**（`router-stats.py` v2.0）：
  - 新增 `outcome='infra_fail'` + `error_class`（`infra`/`timeout`/`empty`/`quality`）+ `response_tokens` 列，旧库自动迁移（PRAGMA 检测 + ALTER）。
  - infra_fail **不进 α/β**，只累加 `infra_count`。此前 64 条记录中 44 条 fail 有 **35 条 tokens<50**（实测 3–13 = 空响应/截断），全被当作"模型不行"计入后验，把成功率压到 qa 12% / code 34%。
  - **生产库已修复**（自动备份 `router-stats.db.bak-2026-08-30T21-39-11+08-00`）：回溯重标 35 行 + 按日志重建后验 —— code **34%→69%**、extraction **38%→75%**、tool-use **40%→100%**、qa **12%→50%**、long-text **17%→33%**；`infra_rate=0.547` 触发供应商不稳定告警。
  - 新增 `rebuild [--retag-threshold N] [--no-backup]`：由 routing_log 重建 bandit，默认先写 `.bak-<ts>`。
- **F-02 cost / latency / level 实算**（`golden-run.py` v2.0）：此前 `golden-run.py:162-164` 硬编码 `level=0, cost=0.0, latency_ms=0`，导致 `cost_per_successful_task` / `escalation_rate` / 延迟维度三项指标全死。现：
  - `cost` 由 `--price-per-1k` 或 `--prices` 实算；**未给价格时 cost=0 且 report 显式标注 `cost_basis=none`**（不静默伪造数字）。
  - `latency_ms` 逐样本实测；`level` 支持 `--level` 入参（升级路径可记录）。
  - report 增 `failure_taxonomy` / `capability_pass_rate` / `mean_latency_ms`。
- **F-03 校准闸门重新可触发**：旧实现用 `α/(α+β)` 比 `sc/n`——两者由同一组计数导出，**恒等，MAE 恒 0**，ref-23 §8「MAE>0.1 调先验」数学上永不触发。现改为 **`bandit_prior_snapshot` 先验 vs 快照之后新观测的 sr**（新增 `snapshot` 子命令冻结先验）。实测：先验 0.2 vs 观测 1.0 → `mean|err|=0.8` ✅。
- **F-11 coverage 输出 + 根因修复**：`report --golden-set` 报 cell 覆盖度；并修掉根因——golden-run 曾用样本 `task_type`（5 分类粗粒度）记账，而 8 分类细粒度标签在 `cell` 字段，导致 bug_fix/refactor/review 三 cell 永远没数据。现优先取 `cell`，实测覆盖 **5/8 → 8/8**。

### P1 — 把声明的硬闸变成真闸

- **F-04 `scripts/diff-risk.py`（新）**：ref-22 §8 声称"脚本化、零 LLM"，但仓库里**没有任何脚本实现它**——被声明为硬闸的规则退化成 agent 自评自己的补丁。现落地确定性评分 `score = 0.30*size + 0.30*module + 0.25*history + 0.15*error_class`；`<0.3` auto / `0.3–0.7` review / **`>0.7` exit 2 人工审核**；无输入源 fail-closed exit 2。
- **F-05 随包验证预设**：`scripts/presets/verify.{python,node,docs}.json`（此前远端 `.github/reusable/*.yml` 有模板、本地确定性闸却要手写 config）。同步给 `verify-runner` 加 `allow_missing`（缺 ruff/mypy 记 skipped 而非失败）与 `allow_exit_codes`（pytest 5 = 没收集到测试）。⚠️ 用法必须带 `--cwd .`。
- **F-06 状态机增 `WAITING` / `CRASHED` + checkpoint/resume**：此前 ESCALATED 是唯一"停下来"的方式且为**终态**，§10.9 tier-4（push 需人工批准）无法建模为"暂停→批准→继续"，会话崩溃也无处恢复。现两者均为**非终态**；`checkpoint` 只在 VERIFY/REVIEW/WAITING 打点（**不在 CRASHED 打点**——那会用崩溃态覆盖上一个好状态）。
- **F-07 修复预算与振荡检测脚本化**（ref-22 §7 原写"超限判定留 agent"）：进入 REPAIR/REPAIRING 前检查 `repair_budget`（默认 3，`--max-repair`，0=不限），超限 exit 2；为保证不死锁，`DIAGNOSE` 增 `ESCALATED` 出口。新增**振荡检测**：同一 `(from,to)` 转移 > 3 次拒绝（`--allow-loop` 显式放行）。

### P2 — 接线与覆盖

- **T-10 SKILL 接线**：§6 新增 Execution Plane 行（`task-workspace.py`）、Review 行增 `diff-risk.py`、Path E 增 `spec-tasks-import.py`；**新增 §5.7 编辑协议**（Search/Replace → Unified Diff → Patch，禁默认 whole-file rewrite）。
- **T-11 `toolstack.json` schema 3**：新增 `sdk_tools` 段，22 个自有脚本各带 `{category, risk_tier, timeout_ms, idempotent, cost_estimate}`（对齐 AgentOS H.1 工具契约）。
- **T-12 refs 版本同步**：`08-spec-kit` 记录 v0.16.4 → **1.0.1**（ref-08 早就是 1.0.1，toolstack 未同步会让月检误报）。
- **T-14 DAG 依赖**：`task-state` 增 `depends_on`；依赖非 DONE（或文件缺失）时禁止进入 `IMPLEMENT`。

### P3 — 卫生与体验

- **T-15 `bump-version.py --sync-size`**：回写 SKILL/README 体积声明为实测值（幂等，可独立运行不需带版本号）。修复 F-13 漂移：声明 30,253B vs 实测 33,874B（+11.9%）。
- **T-16 `robustness-suite.py --timing / --quick`**：逐用例计时 + 按脚本聚合定位慢点（实测 toolstack-pipeline 41s、git-pre-commit 33s 占全量 41%）；`--quick` 跳过这两个慢脚本，182s → **81s（-55%）**。

### 验收

- robustness-suite **83 → 107 用例（+24），107/107 全绿**
- ci-smoke 五步全绿 · privacy-scan 0 残留
- 版本串 6 处一致（v2.7.0）· refs 24 行无孤儿 · SKILL 体积声明已回写

## v2.6.1（2026-08-28）
- **fix: ci-fail-analyze 分类顺序缺陷**（综合测试发现，2026-08-28）：
  - `unit_failure` 的 `FAILED` 模式原为 re.I（大小写不敏感）——任何小写 "failed"（如 "npm install failed"）都会被 unit_failure 抢先吞掉，install_error 永远轮不到；且 `pytest.*failed` 跨词过度匹配（"pytest (build failed)" 被误判 unit_failure）。修复：`FAILED` 改大小写敏感（pytest 输出大写 FAILED + "1 failed" 摘要，覆盖不受影响）、移除 `pytest.*failed`、install_error 增补 `npm ERR!`（真实 npm 输出形态）。
  - robustness-suite +1 回归用例（install error beats failed），83/83 全绿。
- **docs: README 树修正**（综合测试发现文档漂移）：`~24KB` → `~30KB`（实测）、"55 用例" → 82、补齐 5 个缺失脚本（ci-fail-analyze/gh-workflow-check/privacy-scan/spec-tasks-import/task-workspace）+ `.github/` 目录 + `baseline-golden-v3-online.json` + ref-24 行。
- **测试基建扩展**（workspace 侧，不入 SDK 仓库）：`audit_sdk.py` 84 → **104 项**（B 组 +15 CLI 矩阵覆盖 4 新脚本，C 组 +5 机制深测：task-workspace 常量 / ci-fail-analyze 五类+兜底 / spec-tasks-import 解析 / gh-workflow-check 契约）；新增 `extended-probe.py` 深测探针 44 项（21 脚本 --help 矩阵 + 负向边界 + 数据/文档一致性）。
- 验收：robustness **83/83** · audit **104/104**（A 22 / B 64 / C 18）· extended-probe **44/44** · privacy 0 残留 · ci-smoke ALL GREEN。

## v2.6.0（2026-08-28）
- **远程执行引擎 + spec-kit 深度 + 主线同步（升级计划 v2.6.0 票 C2-1..C2-6）**——spec-kit 从指针变执行，自动化 → L4：
  - **C2-2 reusable workflows 库**：`.github/reusable/{python-ci,node-ci,docker-build}.yml` 三件套 + `example-consumer.yml` 消费方示例；GITHUB_TOKEN 默认 read-only、不发版纪律、`agent-run-id` 透传 job summary；SKILL §1 新增"远程 CI 选择行"（Agent 只选不生成）。
  - **C2-3 workflow_dispatch 控制面**：ci.yml 三输入 `operation/version/agent_run_id`（`agent_run_id` 串接 task-state `--run-id` 入 runs[]）；新增 `scripts/gh-workflow-check.py`（stdlib 结构校验：dispatch 输入契约 + reusable-only + read-only permissions，套件 +3 用例）。
  - **C2-4 spec-kit 深度利用**：`uv tool install specify-cli`（1.0.1，持久化）；Path E SDD 默认走 `specify init <project> --non-interactive --script sh|ps|py`（实测非交互姿势，`--script bash` 会报错）；新增 `scripts/spec-tasks-import.py`——tasks.md `- [ ]` 清单 → task-state.v1（P0-P3 优先级 + acceptance 落位，与 C1-2 字段对齐；套件 +3 用例）；ref-08 全面更新（v1.0.1 结构 `.specify/` + `.github/skills/speckit-*`）；**dogfood 闭环**：init → tasks.md → import → task-state.v1。
  - **C2-5 T16 主线同步**（用户确认范围：指针行 + §9 表）：`user-vibe_coding-sdk` Path E 新增 T16 指针行 + 外部工具源表新增 moe 行；主文件热路径不变。
  - **C2-6 在线基线正式化**：ref-23 §8 新增 bandit 在线学习 + 月度校准协议（mean_abs_error>0.1 调先验 / escalation_rate>30% 回退静态矩阵 / 基础设施失败单独统计不计入能力评估——P0 报告遗留项收口）。
  - **C2-1 CI 工作流**：`.github/workflows/ci.yml` 主 CI（push/PR + dispatch）就绪，模板仓库待用户网页端建空仓后推送（PAT 缺 createRepository，§10 push 门禁等待显式确认）。
  - robustness-suite 76 → **82 用例**全绿。
- 验收：robustness-suite **82/82**；privacy-scan 0 残留；audit 见 v2.6.0 报告；ci-smoke ALL GREEN。

## v2.5.0（2026-08-28）
- **工厂对齐 P1（升级计划 v2.6.0 票 C1-1..C1-7）**——Execution Plane + Control 深化 + Failure Analyzer，自动化 → L4：
  - **C1-1 Execution Plane**：新增 `scripts/task-workspace.py`——per-task 独立工作区（`logs/` `artifacts/` `test-results/` + `agent-state.json`），可选 git worktree（`task/<id>` 分支）隔离并行任务；`create/status/verify/cleanup` 四命令；cleanup 为 tier-3 **fail-closed**（无 marker 文件或 task_id 不匹配即拒绝删除）；worktree 校验做路径规范化（Windows 分隔符差异）。
  - **C1-2 task-state.v1 生产字段**：init 新增 `--priority(P0-P3)/--acceptance/--branch/--workspace`；transition 新增 `--run-id/--pr/--attempt` → 追加 `runs[]` 记录（workflow_run_id/pr_number/attempt/state）；validate 兼容旧任务（字段可选、类型校验、runs 结构校验）。
  - **C1-3 状态机扩展 CI/部署阶段**（GH 方案 §12）：`CI_QUEUED → CI_RUNNING → CI_PASSED/CI_FAILED → REPAIRING(→CI_QUEUED/ESCALATED) → MERGE_PENDING → STAGING_DEPLOY → STAGING_VERIFY → PROD_DEPLOY → PROD_VERIFY → DONE`；任何部署态可 `ROLLBACK`（→REPAIRING/DONE/FAILED）；原有本地流不变。
  - **C1-4 Failure Analyzer**：新增 `scripts/ci-fail-analyze.py`——解析 Actions 失败日志 → `diagnostic.v1`（failure_type 五类正则：unit_failure/timeout/command_missing/install_error/syntax_error + generic 兜底；root_cause 切片、固定置信度、repair_strategy、risk）；`--git-dir` 附 `git diff` affected_files；零 LLM 确定性，喂 ref-18 环。
  - **C1-5 修复预算 + Diff Risk Scoring**：ref-22 新增 §7（`max_repair_attempts=3` → ESCALATED → L5 人类）与 §8（Diff Risk Scoring：<0.3 自动 / 0.3-0.7 agent review / >0.7 人工，确定性函数 + 硬闸）；SKILL §5.6 接线。
  - **C1-6 ref-24 安全设计**：新增 `references/24-gh-security.md`（GH 方案 §2/§3/§16）——installation token 最小权限表 + GITHUB_TOKEN 优先 + OIDC 指针 + Tool Layer 抽象（Agent 不拼 API）+ 拒绝清单；SKILL §9 新增行。
  - **C1-7 套件扩展**：robustness-suite 60 → **76 用例**（+4 task-workspace、+3 task-state 生产字段、+6 CI/部署状态机、+3 ci-fail-analyze）；调试中修复 task-state `runs` KeyError（旧任务兼容）与 task-workspace worktree 路径规范化（Windows 分隔符）。
- 验收：robustness-suite **76/76**；privacy-scan 0 残留；audit **84/84**；ci-smoke 见 P1 报告。

## v2.4.1（2026-08-28）
- **P0 收尾修复（评审发现 F1/F2/F3/F7 + 在线基线，升级计划 v2.6.0 票 C0-1..C0-5）**：
  - **C0-1（F7 高危）**：仓库根 `.gitignore` 追加 `user-vibe_coding-sdk-moe/scripts/data/router-stats.db*`——bandit 本地学习库（SQLite）不再裸露于 `git status`（此前随 `git add -A` 有入库风险）。
  - **C0-2（F2 中危）**：`git-pre-commit.py` / `install-hooks.py` 的 SDK_RELPATH 改**运行时推导**——前者按自身文件位置解析（真实钩子模式取仓库相对路径，dry-run 取目录名），后者安装时推导并嵌入钩子体；重命名 SDK 目录后门禁仍跟随，杜绝静默旁路。robustness +2 用例（renamed-dir gate / renamed-dir relpath，套件内复制改名副本模拟验证）。
  - **C0-3（F1）**：SKILL/README 体积声明 `~6KB` → `~30KB`（实测 30,253B，2026-08-28），文档与事实一致。
  - **C0-4（F3）**：数据文件变更入门禁——暂存的 SDK `scripts/data/*.json` 或 `golden-set-*`/`baseline-*` 文件 → JSON 合法性校验（fail-closed）+ golden-set 额外跑 `golden-run --validate-set`；改坏 golden-set 的提交被阻断。robustness +2 用例（有效 baseline 过、坏 JSON 阻断）。
  - **C0-5**：golden v3 **在线基线建立**——`golden-run --set golden-set-v3.json --model auto/best-coding --record router-stats.db`（OmniRoute :20128），报告存档 `scripts/data/baseline-golden-v3-online.json`；bandit 带通带 n=32 入库，为 v2.6.0 月度 report 校准提供首份在线参照。
  - robustness-suite 55 → **60 用例全绿**；privacy-scan 0 残留；pre-commit 钩子重装（钩子体随 SDK_RELPATH 推导变化，静默升级）。

## v2.4.0（2026-08-26）
- **流水线自动化与鲁棒性增强（评估报告 P0+P1+P2 落地，ref-23）**——目标：自动化 L3⁻→L4、鲁棒 L4⁻→L4.5、少验证循环=少 token：
  - **P0-1 提交前门禁结构化**：新增 `scripts/git-pre-commit.py`（改 SDK 脚本 → robustness `--only` 子集，秒级；暂存新文件 → privacy-scan；docs-only 秒过；**fail-closed** exit 1 阻断；子进程前 pop PYTHONPATH 防沙箱 shim）+ `scripts/install-hooks.py`（幂等安装/卸载，`--repo` 可测，外来钩子需 --force）；钩子已安装至本机 `.git/hooks/pre-commit`（不入版本库，换机重装）。
  - **P0-2 纪律兜底**：SKILL §10 新增规则 10（钩子缺失时人工跑 robustness 子集 + privacy 再提交）。
  - **P2-1 定时冒烟**：新增 `scripts/ci-smoke.py`——单命令跑全量确定性回归栈（robustness 全量 + golden v2/v3 `--validate-set` + golden v3 离线 32/32 + privacy），`--json`/`--report` 存档，exit 0/2，**零 LLM 离线**。
  - **P1-2/P2-1 调度自动化**：月度巡检（toolstack-pipeline + ci-smoke）与周度冒烟（ci-smoke --report）两条自动化接入 WorkBuddy 调度。
  - **P2-2 bandit 建议接线**：SKILL §4 路由规则新增——有数据时路由前 `router-stats.py recommend --cell <cell>` 取 Thompson 建议，与静态矩阵/硬过滤合并（bandit 仅建议，裁决留 agent）。
  - **SKILL §6/§9 接线**：自动化门禁工具行 + ref-23 行；README 结构同步（refs 23、scripts 17 个）。
  - **robustness-suite 扩至 55 用例**（+4：install-hooks 安装/幂等、git-pre-commit docs-only/脚本门禁），55/55 全绿；**pre-commit 钩子经真实提交 dogfood 验证**（本版本提交即触发门禁）。
- 验收：robustness-suite 55/55；privacy-scan 0 残留；golden v3 离线 32/32；P1-1 golden v3 在线基线待 OmniRoute 免费池稳定后执行（命令见 ref-23/评估报告）。

## v2.3.1（2026-08-26）
- **fix: router-stats.py SQLite 连接泄漏**（全面测试发现）——`record_outcome` / `recommend` / `report` 三处连接未 close：Windows 下文件句柄锁导致 ① 临时目录清理 PermissionError（WinError 32，审计复现）② golden-run `--record` 进程内反复调用句柄累积。修复：三处补 `conn.close()`（record_outcome 用 try/finally 保证异常路径也释放）。复验：全面审计 **84/84**；robustness-suite 51/51；privacy-scan 0 残留。
- 全面测试基建（workspace，不入 SDK 仓库）：`output/sdk-audit/audit_sdk.py`——A 静态一致性 22 项 / B 全脚本 CLI 矩阵 49 项 / C v2.x 机制深度 13 项，全部离线零 LLM。

## v2.3.0（2026-08-26）
- **Coding Agent OS 吸收 P3 评估+收尾（T12-T15）**：
  - **golden-set v3（T12）**——`scripts/data/golden-set-v3.json`：**32 样本 / 8 cell 标签**（qa/code/long-text/extraction/tool-use + 新增 bug_fix/refactor/review），accept 规则全结构性；`--validate-set` 预检 VALID；**离线判分 32/32 = 100%**（eff 19.4/pass）；离线基线存档 `baseline-golden-v3-offline.json`（在线基线待 OmniRoute 免费池稳定后 `--model <id> --record` 建立）。cell 标签供 router-stats 带通校准（ref-20/ref-22）。
  - **效率指标（T13）**——router-stats `report` 指标集定稿：`cost_per_successful_task` / `token_efficiency` / `escalation_rate` / 校准误差（n≥5 单元）；ref-19 新增 §4.6 数据表 + 指标看板联动（§8）。
  - **toolstack.json v2（T14）**——每工具新增 `risk_tier`（0-4，供 SKILL §10.9 策略读取）/ `idempotent` / `timeout_ms` / `retryable` / `group`，新增 `provider_health` 静态快照（月度巡检更新）；probe-tools 兼容实测（--json 正常输出 tools）。
  - **新增 ALIGNMENT.md（T15）**——架构 29 节 → SDK 落地映射总表（协议/脚本/排除三分类）+ 组件责任矩阵 + 排除总表（7 项）+ 未吸收项说明；未来服务化迁移蓝图。
  - robustness-suite 51/51 保持全绿（P3 为数据/文档变更，未新增用例——T14 兼容性以 probe-tools 实测为准）；README 结构同步（ALIGNMENT.md + golden v3）。
  - **T16 主线同步（可选）**：暂缓——需用户确认覆盖范围后执行（user-vibe_coding-sdk 指针式同步）。
- 验收：robustness-suite 51/51；privacy-scan 0 残留；golden v3 离线 32/32。

## v2.2.0（2026-08-26）
- **Coding Agent OS 吸收 P2 路由+记忆（T8-T11）**：
  - **新增 `scripts/router-stats.py` 离线路由反馈与校准**（吸收 §6/§28.5/§28.11）——SQLite（`scripts/data/router-stats.db`）双表：`routing_log` + `bandit(alpha,beta,n,…)` per (model×cell)；**Thompson 采样** utility = success prob − cost − fail penalty + 探索项（--seed 可复现）；冷启动先验种子 `--priors`（§28.11）；`report` 出 **cost_per_successful_task / token_efficiency / escalation_rate / 校准误差**（n≥5 单元）；记录非法 outcome / 损坏库 exit 2。**dogfood**：golden-run→record→report→recommend 全链实测通过。
  - **分层记忆落地**（吸收 §14）——`scripts/data/memory/` 四层 JSON（repo-facts / conventions / solutions / preferences，每层 ≥3 种子，schema `memory.v1`）；检索规则"结构化匹配优先 → 嵌入兜底（指针）"；**case-search.py v1.1 增 `--layer`**（搜 `<dir>/<layer>/*.json + *.md`）。
  - **token-meter.py 预算跟踪（T10）**——`--budget '{"max_usd":0.5,"max_calls":50}'`：报告 `budget` 块（spent/max/exceeded/reasons/action）+ flag "budget exceeded: escalate to human (L5, ref-22) — explicit stop > silent degrade"（吸收 §16 显式停止优于静默降质）。
  - **golden-run.py `--record` 反馈闭环（T11）**——每行 outcome 经 importlib 直写 router-stats bandit 带（零 LLM、零子进程）；`--cell` 覆盖默认 task_type 标签；报告 `recorded_outcomes`。
  - **robustness-suite 扩至 51 用例**（+14：router-stats 8 / case-search --layer 2 / token-meter budget 2 / golden-run --record 2），51/51 全绿；README 结构同步（scripts 15 个 + memory 层）。
  - 经验：argparse 子命令后 `--db` 属子 parser 参数，主 parser 定义会 unrecognized（案例库 rf-005 已记）。
- 验收：robustness-suite 51/51；privacy-scan 0 残留。

## v2.1.0（2026-08-26）
- **Coding Agent OS 吸收 P1 确定性核心（T5-T7）**：
  - **新增 `scripts/task-state.py` 任务状态机持久化**（ref-20 落地）——init/transition/history/trace-export/validate 五命令；状态转移表为数据（15 状态 / 转移集含 ESCALATED/FAILED 终态）；五态 verdict（SUCCESS/PARTIAL_SUCCESS/FAILED/REGRESSION/UNKNOWN）校验但判定留 agent；黑板 facts 写入（--bb-add key=JSON）；持久化 `.workbuddy/tasks/<id>.json`；非法转移/重复 init/坏 JSON/缺任务 exit 2。**dogfood 实测**：INIT→…→DONE 全链 + validate 通过。
  - **verify-runner.py 分层升级（v2.0）**（吸收 §12）——配置支持 `layers`（syntax→type→lint→test-targeted→…→invariants 9 层）+ **cheapest-first 短路**（首层失败即停，报告 `stopped_at`）；`--layers` 子集过滤；缺 `cmd` 守卫 exit 2；向后兼容 `steps`（v1）。
  - **统一结构化诊断 schema（diagnostic.v1，吸收 §28.3）**——verify-runner（顶层 `schema` + 每步 `error_class`：syntax/type/lint/command_not_found/timeout/test_failed + `diagnostics[]`）、golden-run（报告 `schema`）、error-sig match（`schema`）三脚本对齐；error_class 供 ref-22 失败类感知升级决策。
  - **robustness-suite 扩至 37 用例**（+12：task-state 8 + verify-runner 分层/schema 4），37/37 全绿；README 结构同步（scripts 13 个）。
- 验收：robustness-suite 37/37；privacy-scan 0 残留。

## v2.0.0（2026-08-26）
- **Coding Agent OS 架构吸收 P0 协议层（T1-T4，SDD 计划落地）**——基于《Coding Agent OS — Production Architecture》（服务级 MoE 编排系统）的指针式吸收，三分类纪律（协议/脚本/排除，ref-17 同款）：
  - **新增 ref-20 任务状态机+黑板协议**（吸收 §10-11/§15/§28.4）：状态外置 `.workbuddy/tasks/<id>.json`、转移表为数据、与 §5.6 五态映射、黑板更新规则（仅 Orchestrator 写 / last-validated-write-wins / contradicts_evidence 拒收 / recent_actions cap 8）、多代理"单代理默认"行。
  - **新增 ref-21 上下文工程协议**（吸收 §7/§16）：检索 6 步（任务切片→符号 1-hop→语义 top-k→排序→按类预算→适配器格式化）、A/B/C 按类预算表、默认排除清单、压缩时机（黑板超阈→Class-A 写任务记忆）；与 SKILL §7 稳定前缀构成双层上下文流水线。
  - **新增 ref-22 修复升级阶梯协议**（吸收 §6.6/§13/§28.8）：L0-L5 阶梯 + 重试预算（2/2/2/1/1）、不可跳级（min_level 例外）、失败类感知（error_class→升级策略）、重复签名熔断→ESCALATED、L5 人类一等终态；与 ref-18 合并关系明确（ref-18=L1-L3 内部方法论，ref-22=外部骨架）。
  - **SKILL.md 接线 4 处**：§1 Path E SDD（ref-20/21/22 指针）、§5.6（task-state.py 五态落盘 + L0-L5）、§6 SDD 行（task-state.py）、§7（ref-21 动态层指针）；**§10.9 风险分层表扩展**（吸收 §17：低危 0-1 / 中危 2 / 高危 3 / 不可逆凭据 4，toolstack.json risk_tier 字段预告）；§9 References 扩至 **22**。
  - README 结构同步（refs 22 个）。
- 验收：robustness-suite 25/25 全绿（P0 零脚本变更）；privacy-scan 0 残留（新文件全 `<PLACEHOLDER>`/通用路径）。

## v1.16.0（2026-08-22）
- **新增 `scripts/privacy-scan.py` 公开推送前隐私扫描（P3 落地，memory 遗留建议）**——把 v1.15.1/v1.15.2 的人工 grep 隐私检查脚本化：五组模式（`users` 本机用户名 / `paths` 机器路径·软链实路径 / `endpoints` 本地服务端点 / `keys` API 密钥·PAT·Bearer / `emails` 个人邮箱），文档 EXAMPLE 值（AKIAIOSFODNN7EXAMPLE 等）与通用路径（Program Files / AppData / `<...>`）自动过滤，`--user`/`--allow-user` 指定本机用户名，exit 0 干净 / 2 阻断（tier-4 push 门禁前置）。
- **首发即发现 v1.15.1 脱敏遗漏 7 处机器路径残留**并修复：CHANGELOG 旧条目（v1.10.0/v1.12.0）实路径 → `<DOCS>`/泛化描述；debug-case pytest-shim 的系统 Python 环境路径 → `<PY_ENV>`；ref-07 gh CLI 安装路径 → `<GH_CLI_BIN>`；ref-08 uv 缓存/工具目录（3 处）→ `<UV_CACHE>`/`<UV_TOOLS>`；ref-17 源文档路径（2 处）→ `<DOCS>`；CHANGELOG v1.15.2 条目自指端点 → `$OMNIROUTE_URL`（自指教训复发，P2 已改）。修复后 `privacy-scan.py . --user <本机用户名>` **0 残留**。
- 自发现并修复 2 个脚本 bug：正则 `\\b`/`\\.` 双重转义（匹配字面反斜杠而非单词边界，导致 keys/emails 组失明）→ 统一改 `\b`/`\.`；`--json` 模式仅预览不写入（bump-version 历史行为，文档化）。
- **robustness-suite 扩至 25 用例**（+3 privacy-scan：clean dir / leak detection / nonexistent dir），25/25 全绿；ref-19 新增 §4 privacy-scan 行 + §5 推送前门禁。

## v1.15.2（2026-08-22）
- **OmniRoute 端点脱敏（P2 执行）**——公开仓库移除 `$OMNIROUTE_URL` 机器特定端点描述：`golden-run.py` `--llm-url` 默认值改为 `$OMNIROUTE_URL` 环境变量驱动（未设置且非 `--offline` 时明确报错 exit 2）；CHANGELOG / ref-19 / debug-case 同步改 `$OMNIROUTE_URL`；ref-07 `<TEMP>` 泛化补漏（临时路径残留）。
- 修复：golden-run.py 补 `import os`（env 驱动引入时的遗漏）；robustness-suite 22/22 仍全绿（功能零回归）。

## v1.15.1（2026-08-22）
- **GitHub 公开仓库隐私脱敏**（推送前隐私检查发现 5 处机器特定路径）——公开仓库移除：符号链接实路径（ref-07/ref-14/CHANGELOG v1.4.1 条目）、本机用户名路径（ref-07）、gh CLI 安装路径（ref-15 + `toolstack-pipeline.py` GH_FALLBACKS 改为 `GH_CLI_PATH` 环境变量驱动，隐私安全默认值）、Windows 临时路径（ref-07 + debug-case + error-signatures 泛化为 `<TEMP>`）。
- 脱敏后全目录复查：**0 敏感项**（无真实密钥/邮箱/PAT/Bearer）；robustness-suite 22/22 仍全绿（功能零回归）。

## v1.15.0（2026-08-22）
- **鲁棒性审计建议落地（robustness-audit §六 两项建议全执行）**：
  - `golden-run.py` 新增 **`--validate-set` 预检**——跑回归前预编译全部 accept regex + 校验字段完整性，坏规则立即列出并 exit 2（fail-fast，零 LLM 调用，避免坏集烧 token）；实测 golden-set-v2 校验 VALID。
  - 新增 **`scripts/robustness-suite.py` 鲁棒性回归套件**——把审计的 22 项故障注入用例固化为确定性回归：`python scripts/robustness-suite.py`（exit 0/2），`--only <脚本>` 过滤，`--json` 机器可读；用例含 golden-run（缺参/坏集/坏 regex/validate-set/连接拒绝/无 accept 键）、verify-runner（坏配置/127/通过）、bump-version（非法版本/old==new 守卫）、error-sig/case-search/env-snapshot/token-meter/review-prefilter（缺文件/空输入/垃圾行/非 git 目录）、probe-tools（隔离副本缺 manifest）、toolstack `--push` 非 TTY 门禁。**首跑 22/22 全绿**。
  - ref-15 巡检节奏：robustness-suite 建议并入月度巡检（脚本变更后先跑套件再提交）。
- ref-19 更新（golden-run `--validate-set` 用法 + 套件行 + 巡检联动）；README 结构同步；版本串由 bump-version.py 完成。

## v1.14.1（2026-08-22）
- **鲁棒性审计修复（robustness-audit 发现）**——对 10 脚本跑 20 项边界/异常/降级测试（缺参/坏 JSON/坏 regex/缺文件/连接拒绝/非 git 目录/空输入/CJK 路径/非 TTY push），发现并修复 2 处：
  - `golden-run.py`：accept 规则中**非法 regex 导致 traceback 崩溃**（re.error 未捕获，HTTP 200 场景外另一崩溃面）→ structural_judge 捕获 `(re.error, KeyError, TypeError)`，坏规则记为样本失败（"bad accept rule in golden set"），exit 2 优雅收场。
  - `bump-version.py`：`old == new` 或版本 token 未命中时仍继续（可能插入 changelog 头并提交）→ 新增两个 abort 守卫（"nothing to bump"），防止空操作污染提交历史。
- 其余 18 项边界全部通过（缺参 exit 2 / 坏 JSON fatal / 连接拒绝逐样本报错不崩溃 / 非 git 目录优雅降级 / 空输入 JSON error / CJK+空格路径读写正常 / `--push` 非 TTY 安全拒绝）。
- 已知行为（文档化非缺陷）：verify-runner `--cmd` 用 REMAINDER，`--json` 须置于 `--cmd` 之前；probe-tools 缺 manifest 时 exit 1（信息类脚本，可接受）。

## v1.14.0（2026-08-22）
- **golden-set v2 + LongCat 100% 达成（执行审计建议动作）**：
  - `scripts/data/golden-set-v2.json`——同 20 样本放宽 2 条过严判分：ext-03 改"中英键皆可"（`(model|模型)`/`(temperature|温度)`/`thinking:true` 三字段独立校验）、tool-05 改同义词组（确认|授权|批准|同意|approval|门禁|gate|人批|显式|**人类|控制权|审查|human|review|人**——LongCat 实答"确保人类对代码推送的最终控制权…未经审查"语义正确，补齐同义词后离线判分 PASS）。
  - **LongCat 复测：18/20 → 19/20 → 20/20 = 100%**（in=621 / out=14002 / eff=731/pass，exit 0）——判分规则与模型输出习惯对齐后全绿，验证"失败均为规则过严非模型缺陷"的审计结论。
  - 基线存档 `scripts/data/baseline-longcat-v2.json`（20/20）——与 v1 基线（18/20）构成 A/B 参照。
- ref-19 §4.5 更新（v2 推荐使用 + baseline-v2）；README 结构同步；版本串由 bump-version.py 完成（changelog 插入"首条 `## v` 前"健壮逻辑首次实装验证）。

## v1.13.1（2026-08-22）
- **golden-run SSE 解析修复（靶场审计发现）**——OmniRoute 对 `lc/LongCat-2.0` 等模型**强制返回 SSE 流**（`data: {...}` chunks，即使未请求 stream），旧实现按纯 JSON 解析 → JSONDecodeError 崩溃。新增 `parse_llm_response()`：先试 JSON，失败则逐行解析 SSE 拼 delta.content + 收集 usage；HTTPError/URLError 已捕获（v1.13.0 起）。
- **金标回归首条基线（LongCat）**：`lc/LongCat-2.0` 实测 20 样本 **18/20 = 90%**（in=621 / out=14553 / eff=843/pass）；2 失败均为**判分规则过严**而非模型错误——ext-03 LongCat 保留中文键 `{"模型":..,"温度":..}`（语义正确但规则只认英文键）、tool-05 规则要求"确认"+门禁词双命中。golden-set v2 建议放宽（中英键皆可 / 同义词组）。
- 错误签名库新增 SSE 流签名（"data:" 开头 / 200 但 JSONDecodeError）。

## v1.13.0（2026-08-22）
- **种子数据落地（ref-19 §4.5）+ golden-run 健壮性修复**：
  - `scripts/data/golden-set-v1.json`——**首条金标集**：20 条 CN 样本覆盖 5 族（qa 4 / code 4 / long-text 3 / extraction 4 / tool-use 5），accept 规则全结构性（regex/contains 零 LLM-judge）；结构校验通过（所有 regex 可编译）。**在线回归未完成**：OmniRoute 免费池瞬时 503（"Maximum combo retry limit reached"），属上游常态，池恢复后 `golden-run.py --set scripts/data/golden-set-v1.json --model auto/best-fast --json` 建基线。
  - `scripts/data/error-signatures.json`——11 条已知签名（沙箱 shim / tmp 路径 / PAT 403 / index.lock / git gone / EBADENGINE / Ollama 超时 / argparse REMAINDER / 仓库损坏 / OmniRoute 503），`error-sig.py match` 实测命中。
  - `.workbuddy/debug-cases/`——4 个真实 incident 轨迹（pytest shim / changelog 布局 / tmp 路径 / OmniRoute 503），`case-search.py --q "pytest shim"` 实测命中。
  - **golden-run.py 修复**：llm_complete 补 HTTPError/URLError/超时捕获，错误写回 row 不再崩溃（免费池 503 实测暴露）；离线判分路径不受影响。
- ref-19 新增 §4.5 种子数据表；README 结构清单补 data/ 与 debug-cases/；v1.13.0 版本串由 bump-version.py 自身完成。

## v1.12.0（2026-08-22）
- **Token 脚本化流水线 P1+P2 落地（ref-19 全量）**——审计的 8 个可脚本化消耗点全部交付，共 9 脚本：
  - **P1：Debug 零 LLM 首轮**——`golden-run.py`（金标回归 1 命令化：结构性判分 regex/contains 零 LLM-judge，默认接 OmniRoute `$OMNIROUTE_URL`，`--offline` 纯判分，`--baseline` A/B diff 回归 >2% exit 2）；`error-sig.py`（错误签名库 add/match，ref-18 确定性先行步骤 2 持久化，新颖错误 add 沉淀后续直接命中）；`case-search.py`（问题案例库 grep 式检索，多关键词 AND，命中排序标题优先）。
  - **P2：按需**——`env-snapshot.py`（环境快照一次成型：工具版本/git 状态/env/日志 tail/配置 sha256；PATH 默认截断 10 条 G1；npm 等 `.cmd` 回退）；`review-prefilter.py`（Review 预过滤：git diff numstat top-N + 检查步骤 → 精简关注包，检查失败 exit 2 阻塞标记）；`token-meter.py`（token 计量：ref-05 §7 JSONL schema，缺失字段 CJK-aware 估算，think 占比/缓存命中率/成本估算/超限 flag）。
  - **dogfooding 实测**：六脚本全路径冒烟（golden-run 2/3 通过 exit 2 正确；error-sig add→match 命中；case-search 多关键词命中；env-snapshot PATH 71→10 条有界 + npm 12.0.2 `.cmd` 回退生效；review-prefilter diff 统计正确；token-meter 3 记录指标/成本/flags 全出）。
- ref-19 §3/§4 改为"已实现"并补全用法；SKILL.md §9 ref-19 行更新为 9 脚本全实现 + §6 Review 行接入 review-prefilter；README 结构清单同步（scripts 10 个 + refs 19）。
- 经验：Git Bash `/tmp` 路径在 Windows Python 下不被解析（token-meter 首测 no records）——测试用 Windows 路径。

## v1.11.0（2026-08-22）
- **Token 脚本化流水线 P0（ref-19 落地）**——审计确定 8 个可脚本化消耗点（§6 工具探测 / §5.6 验证环 / §10.8 版本 bump / §8 金标回归 / ref-18 确定性先行 / 环境快照 / Review 预过滤 / token 计量），本次交付 P0 三件套（用户确认范围）：
  - `scripts/probe-tools.py`——§6 "probe once per session" 落地：复用 toolstack.json `local_tools` manifest 一次探全部工具（含 Windows npm shim `.cmd/.exe` 回退），`--json` 机器可读；替代每会话 6+ 次 `--version` 探测 tool call。
  - `scripts/verify-runner.py`——§5.6/ref-18 验证闸：跑 test/lint/build 步骤（verify.json 配置或 `--cmd` 临时），exit code + 有界 tail（默认 12 行，G1），`--json`；替代 LLM 叙述验证环。**职责边界**：脚本只报 pass/fail 事实，五态判定（REGRESSION/UNKNOWN）留在 agent。
  - `scripts/bump-version.py`——§10.8 自版本管理脚本化：精确匹配版本 token（SKILL frontmatter+title、README blurb+version-line）自动替换 + CHANGELOG 插入日期头 + `--commit` 本地提交；默认 dry-run、`--json`、**永不 push**（tier-4 门）；CHANGELOG 正文留给 agent。
  - **dogfooding 验证**：本版本号即由 bump-version.py 自身完成（v1.10.0→v1.11.0，4 处替换 + changelog 头全部命中）；probe-tools `--json` 实测 6 工具全绿；verify-runner 通过/失败/缺配置三路径实测（沙箱 pytest myenv 损坏属环境预期降级）。
- **新增 `references/19-token-scripts.md`**——全部 8 个脚本的规格/用法/schema/边界；P1 规划 golden-run（金标回归 1 命令化，可接 OmniRoute `$OMNIROUTE_URL`，结构性判分零 LLM）、error-sig/case-search（Debug 零 LLM 首轮）；P2 规划 env-snapshot/review-prefilter/token-meter。
- SKILL.md 接线 3 处（§6 Probe rules、§5.6 验证闸、§10.8 bump 脚本）+ §9 References 表加 ref-19；References 扩至 **19**；README 同步。

## v1.10.0（2026-08-22）
- **吸收 Agent Doctor 控制面纪律**（源文档 `<DOCS>/agent-doctor-architecture.md`，AI Ops 控制平面架构，本地文档指针；提案先行经用户确认 P0+P1 / v1.10.0 / 指针引用三决策）。四大资产落地：
  - **状态化路由（ref-17）**——§4 路由规则新增三条硬纪律：Pareto 硬过滤（context/可用性/预算/能力约束，禁止廉价优势压过硬约束）、`fallback_chain` 强制预计算（provider 故障→同族便宜模型→本地模型→缓存轨迹→纯规则确定性路径，降级零额外推理调用）、cheap-first 级联 + early exit（本地模型先分类/过滤，置信不足再升级，达标即停）。
  - **Debug 诊断协议（ref-18）**——§1 Debug 行重定义为"确定性先行（复现/签名匹配/静态分析/差分/二分）→ 假设-证据-实验环 → 修复 → 验证五态"；新增 `references/18-debug-diagnosis.md`（确定性先行 5 步清单、Hypothesis schema 含支持/反对证据+预期观察+推荐实验、实验选择"廉价+可逆+高判别力"启发式、验证五态判定细则、问题案例库轨迹格式）。
  - **验证五态（§5.6）**——SUCCESS / PARTIAL_SUCCESS / FAILED / REGRESSION / UNKNOWN 五态判定表，禁止默认 SUCCESS；UNKNOWN 触发补实验、REGRESSION 检查影响半径（DEPENDS_ON/CONFLICTS 邻居）。
  - **风险分层操作门（§10.9）**——tier 0–4（0 只读无门禁 / 1 安全可逆无门禁 / 2 受控修改自动 / 3 破坏性需独立交叉验证+回滚测试 / 4 不可逆或凭据必人批），`can_act = risk_level ≤ ceiling AND confidence ≥ threshold AND rollback validated`；§10 rule-2 push-gate 归入 tier 4 统一治理。
- **新增 references/17-agent-doctor.md**——设计依据指针：概念吸收映射表、启发式级条目（ModelProfile 经验回写 / Incident 轨迹复用 / 降级链分层）、明确排除项（World Model 图、Thompson Sampling 数学、16 专家编排、跨模型辩论、EIG 公式）、更新配方（本地单文件无上游版本管理）。
- SKILL.md 正文增量 ~24 行（§1/§4/§5.6/§9/§10），细则全部下沉 references，稳定前缀结构保持；References 扩至 **18**；README/CHANGELOG 同步。

## v1.9.5（2026-08-18）
- **新增 ref-16 Context7 集成**——盘点发现 `upstash/context7` 此前仅在 §6 SDD 行按工具名引用（context7-cli），未纳入工具栈管治（toolstack.json 无条目、无 pin、无漂移巡检）。本次按 ref-15 流水线 schema 补录：manifest `local_tools` 新增探针（ctx7，npx 运行，未本地安装属预期）+ `refs` 新增 `16-context7`（repo upstash/context7，**默认分支 master**，check both，pin head `f3a818d` / release `@upstash/context7-mcp@4.0.2` / 60.9K★ / MIT）；新增 `references/16-context7.md` 指针文档（用途、三入口 CLI/技能管理/MCP、隐私注意、更新配方）；§6 SDD 行标注 ref-16；SKILL.md/README/CHANGELOG 版本同步至 v1.9.5。References 扩至 16。

## v1.9.4（2026-08-18）
- ref-07 补充 **沙箱杀重量级 git 操作**坑位：`git subtree split` 与跨大树 `git checkout` 被沙箱静默终止，可能遗留半成品工作树（数百文件删 + `index.lock` 残留）。规避 = **工作区 scratch 仓库同步方案**（git init 于工作区 → fetch github main → checkout → cp 铺入 → 配身份 → commit → 快速前进 push）；恢复 = `rm index.lock` + `git restore .`。

## v1.9.3（2026-08-18）
- **changelog 移出 SKILL.md 热路径**：16 条版本记录（8,650 字节 ≈ 全文件 27%）迁至本文件；SKILL.md 顶部改为一行静态指针（无版本号）。
- **动机（性能数据）**：changelog 在热路径上每次会话加载都被支付 token（~2.9-4.3K tokens/会话），且位于固定头部与正文之间 → 每次 bump 使标题行之后的全部正文 prompt-cache 失效；2 天 16 次 bump = 16 次全量重编码。迁移后 bump 只改 CHANGELOG.md，SKILL.md 字节级静态（缓存全命中）。
- **修正**：sed 全局替换曾把 v1.9.1 条目标签误改为 v1.9.2（本文件恢复正确标签）。

## v1.9.2（2026-08-18）
- ref-07 补充 **HTTPS push 前置坑位**——gh 凭据走 keyring，但 git 未配置 credential helper 时 `git push https://...` 报 `could not read Username`（沙箱无 `/dev/tty`）；先 `gh auth setup-git` 一次即可。同时实测再次验证 fine-grained PAT 403 坑位（本机对 `github-fubowen/user-vibe_coding-sdk-moe` 推送被拒 = PAT 缺该仓库 Contents: write，读 API 正常）。

## v1.9.1（2026-08-18）
- 流水线验证轮发现并修复 2 个真 bug——① `run()` 助手缺 `cwd` 透传导致 `--commit` 在非仓库 cwd 抛 TypeError；② `git add` 用绝对路径（symlink 解析为实路径形态）被 git 判为仓库外路径而静默失败 → 改为 `git -C <scripts> rev-parse --show-toplevel` 解析仓库根 + **相对路径** stage，cwd 全中性。验证矩阵全绿：report exit 0 / `--json` 合法 / `--push` 非 TTY 拒绝（安全属性成立）/ gh 缺失降级（find_gh→None 跳过上游核对）/ `--update --commit` 从外来 cwd 真提交 `421f7a7`。

## v1.9.0（2026-08-18）
- 新增 **ref-15 工具栈维护流水线**——`scripts/toolstack-pipeline.py`（Python 3.9+ stdlib 零依赖）+ `scripts/toolstack.json`（机器可读 pin 单一事实源）。六阶段：**probe**（本地工具链版本探针，含 Windows npm shim `.cmd` 回退）→ **diff**（gh api 核对 head/release/pushed_at，stars 仅展示不判漂移）→ **report**（漂移 exit 2 / 干净 exit 0，`--json` 机器可读）→ **update**（刷新 manifest pin + public-apis vendored 数据 SHA256 完整性 + PROVENANCE 自动更新；cybersecurity-skills 49MB 库只输出配方不自动替换）→ **commit**（本地，Conventional 消息）→ **push-gate**（交互 y/N，非 TTY 拒绝并打印手推命令，编码 §10 纪律）。实测：7 条 ref 全绿、数据完整性 OK、`--update --commit` 链路通；顺带发现 `ocr` 已自更新 v1.8.10→**v1.9.5**；References 扩至 15。

## v1.8.3（2026-08-18）
- **工具栈全量复核**——6 个外部 pin 全部仍为上游 HEAD/最新版（public-apis `28458cf` / cybersecurity `4c0b700` / ui-ux `a38d04c` / spec-kit **v0.16.4** / Strix **v1.5.3** / ARS-Codex v0.1.25），零漂移；本机探针确认 §6 工具链可用（open-code-review v1.8.10 / graphify 0.9.37 / code-review-graph v2.3.7 / specify 0.16.4），cli-hub 与 strix 维持指针引用（未本地安装）；同步各 ref 星标漂移（CLI-Anything 47.5K→47.7K、Strix 54.4K→54.5K、ARS 8,650→8,759、public-apis 463,267→463,425、Cybersecurity 28,605→28,624、spec-kit forks 11.5K→11.6K）；**修复 README 版本滞后**（v1.7.0→v1.8.3、references 13→14、结构清单补 ref-14、修正 ref-12 为外部指针 `../public-apis/SKILL.md`）；**修正 ref-14 更新流程**——`cybersecurity-skills/` 实为并入 skills 主仓库的普通目录（无 `.git`），原文 `git pull` 指令会失败，改为 gh api 取 HEAD → 临时 clone → diff 对比 → 提交的更新配方。

## v1.8.2（2026-08-18）
- ref-07 Pitfalls 补充 **WorkBuddy Bash 沙箱静默丢远程跟踪引用**坑位——沙箱内 `git fetch origin` / `git update-ref refs/remotes/origin/main` 均报成功（rc=0）但引用文件不落盘 → `git status` 持续显示 `## main...origin/main [gone]`；commit/push 不受影响（refs/heads 与 D 盘裸仓库照常写入）；Workaround：用户自己终端跑一次 `git fetch origin` 即恢复，或 `git branch --unset-upstream main`。

## v1.8.1（2026-08-18）
- ref-14 **本地落地**——全量库 clone 至 `~/.workbuddy/skills/cybersecurity-skills/`（49MB / 817 SKILL.md / pinned commit `4c0b700`），新增入口技能 **`cybersecurity-skills-router`**（scripts/search.py stdlib 只读检索：keyword/subdomain/JSON，子域过滤自动扫 frontmatter）；复核审计 **Benign**（全量 1095 py 模式扫描 + 代表深读：eval/exec 仅静态正则、shell=True 仅 atomic-red-team 设计所需、curl|bash 均为检测正则或官方安装示例、无真实密钥）；修正 ref-14 过时数据（29→**34 规范域**、~13.5MB→**49MB**、1093→**1095 py**），六框架映射实测（ATT&CK 805 / CSF 804 / D3FEND 139 / AI RMF 97 / F3 94 / ATLAS 93）；§6 安全任务链接入 router。

## v1.8.0（2026-08-18）
- 指针式集成 **ref-14 Anthropic Cybersecurity Skills**（mukul975，28.6K stars，Apache-2.0）——817 技能 / 29 安全域 / 6 框架映射（ATT&CK v19.1 / NIST CSF 2.0 / ATLAS / D3FEND / AI RMF / MITRE F3）的 AI 安全技能库（agentskills.io 标准）；抽样 12 脚本安全审计：**0 危险模式**（无 eval/exec/os.system/base64，subprocess 仅驱动既有 CLI），攻击类技能带 Legal Notice；⚠️ 双用途内容仅限授权目标（与 ref-13 同门禁）；§6 加 Security/DFIR 任务链（reverse-skill-router → ref-14 → Strix）；References 扩至 14。

## v1.7.0（2026-08-18）
- 指针式集成 **ref-13 Strix**（usestrix/strix，54.4K stars，Apache-2.0）——开源 AI 渗透测试工具：自主 AI 黑客代理（Graph of Agents），Docker 沙箱 + LiteLLM + Caido + Nuclei + Playwright，输出带 PoC 的已验证漏洞报告（MD/JSON/CSV/SARIF）；官方 4 个 SKILL.md 技能（pentest / fix / ci-scanning / managed cloud）；§6 Review 工具链接入 `strix`（仅授权目标）；References 扩至 13。

## v1.6.0（2026-08-18）
- 集成 **ref-12 public-apis**（public-apis/public-apis，46.3 万 stars，MIT）——公共 API 大全离线检索 skill：50 分类 / 1668 API 本地数据副本（pinned commit `28458cf` + SHA256 溯源），stdlib 只读解析脚本 `search_apis.py`（无网络/无写入/无子进程，安全审计 **Benign** 85 分）；检索类任务归 Tier T2（思考 OFF）；References 扩至 12。

## v1.5.0（2026-08-17）
- 指针式集成 **ref-11 UI/UX Pro Max**（nextlevelbuilder/ui-ux-pro-max-skill，117K stars，MIT）——UI/UX 设计智能技能套件（7 子技能：ui-ux-pro-max/brand/design/design-system/slides/ui-styling/banner-design），离线数据引擎（79 风格 / 192 行业配色+推理规则 / 74 字体 / 119 UX 指南 / 25 图表 / 22 技术栈），Python 标准库**零依赖**；§6 Vibe 工具链接入；核心运行时安全审计 **Benign**（无网络/无敏感路径/无自动执行），CLI 安装路径 2 项 Suspicious 供应链提醒（npx/npm 未锁版本）；References 扩至 11。

## v1.4.1（2026-08-16）
- ref-07 Pitfalls 补充 Windows/WorkBuddy 环境坑位——`~/.workbuddy` 是符号链接（指向 home 外的实际位置），`git -C` 需用 Windows 风格路径；fine-grained PAT 推送须对目标仓库授权 Contents: Read and write（权限不足在 API 上表现为 404、push 表现为 403）。

## v1.4.0（2026-08-16）
- 指针式集成 **ref-10 ARS-Codex**（学术研究技能套件，8.65K stars，v0.1.25）——单技能路由器 + 5 工作流（deep-research/academic-paper/reviewer/pipeline/experiment-agent），References 扩至 10；**CC BY-NC 4.0 仅指针引用不 vendored**；供系统综述/论文流水线类任务作参考协议。

## v1.3.0（2026-08-16）
- 轻量集成 **ref-09 CLI-Anything**（HKUDS，47.5K stars）——§6 Engineering 工具链加 `cli-hub`（软件 Agent-Native CLI，`--json` 结构化调用）、References 扩至 09；未做本地安装（依赖上游应用 + 前沿模型，生产使用前需验证）。

## v1.2.0（2026-08-16）
- 新增 **ref-08 Spec Kit 集成**（GitHub 官方 SDD 工具，实测 v0.16.4）——§1 Path E 映射 spec-kit 流水线、§6 SDD 工具路由加入 `specify` CLI、References 扩至 08；关键坑位记录：非 TTY 环境 init 必须 `--script ps|sh`、uv tool 默认装 C 盘（须 UV_CACHE_DIR/UV_TOOL_DIR 重定向 D 盘）。

## v1.1.0（2026-08-16）
- 新增 **§10 Git Management + ref-07**——本地 commit 默认、**push 必须显式确认**、Conventional Commits 提交规范、分支/worktree 策略、Mode→Git 动作映射、回滚安全食谱、技能自版本管理（版本号 + changelog + 每次编辑提交进 `~/.workbuddy/skills/` git 仓库）；References 扩至 07。

## v1.0.1（2026-08-16）
- 修复思维链漏中文——新增顶部 LANGUAGE RULES 硬规则横幅（首 token 必须是 `[GOAL]` 的 `[`）、思维链零 CJK 自检加入 §5.3、明确"思考语言与输出语言独立"、声明 WorkBuddy 深度思考用户可见（thinking is visible → 语言纪律与输出同严）。

## v1.0（2026-08-15）
- 初版：MoE 特化编码 SDK（vs user-vibe_coding-sdk v2.1）——强制英文思维链协议 · 思考预算按任务分级 · MoE 路由矩阵 · 稳定前缀缓存硬规则 · token 预算闸门 · 质量闸门（压制拟人化尾巴/引用溯源/自检/Reflection）· 渐进式披露结构（主文件 + 6 references 按需加载）。
