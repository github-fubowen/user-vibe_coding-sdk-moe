# ENGINEERING.md — user-vibe_coding-sdk-moe 工程手册

> v2.10.1 · 2026-09-01 · 与代码库逐项对齐（脚本 docstring / 状态机 / toolstack.json / 门禁实测）
> 定位：本文件是 SDK 的**工程视图**（架构 + 组件 + 数据流 + 门禁 + 操作规程）；协议行为见 SKILL.md（热路径），版本历史见 CHANGELOG.md，架构映射见 ALIGNMENT.md。

---

## 1. 定位与三分类纪律

SDK 的全部工程资产分为三类（硬约束，任何新增都先归类）：

| 分类 | 定义 | 本仓库实例 |
|---|---|---|
| **协议（doc）** | 行为规范、决策规则，由 agent 遵循 | SKILL.md / refs 01-24 / ALIGNMENT.md |
| **脚本（deterministic）** | 确定性工具，stdlib 零 LLM，可测试可门禁 | `scripts/*.py` 27 个 + `presets/` 3 个 + `.github/` |
| **排除（指针）** | 只引用不 vendored | ref-10（ARS-Codex CC BY-NC）、ref-12（public-apis）、ref-13（Strix）、ref-14（cybersecurity-skills 本地库） |

**反模式排除清单（§17）**：不建 webhook 服务 / Event Bus / Redis / Kafka / Temporal——技能层边界，状态外置到文件（task-state），反馈入库（router-stats.db），事件由 agent 轮询文件系统。

---

## 2. 架构总览：四平面

```
┌─ Product-spec 平面 ─────────────────────────────────────────────┐
│ spec-kit (specify 1.0.1) ──init──> spec.md / tasks.md           │
│        └─ spec-tasks-import.py ──> task-state.v1 (INIT)         │
├─ Execution 平面 ────────────────────────────────────────────────┤
│ task-workspace.py（每任务目录 + git worktree）                   │
│ task-state.py（28 状态机，history/blackboard/runs 外置）         │
│ verify-runner.py（确定性验证闸 diagnostic.v1）                   │
├─ Control 平面 ──────────────────────────────────────────────────┤
│ 门禁：git-pre-commit / install-hooks / ci-smoke / robustness    │
│ 诊断：ci-fail-analyze（CI 失败→diagnostic.v1→ref-18 环）         │
│ 升级：ref-22 阶梯 L0-L5 + max_repair_attempts=3 + Diff Risk     │
├─ Delivery 平面 ─────────────────────────────────────────────────┤
│ .github/reusable/{python-ci,node-ci,docker-build}.yml           │
│ .github/workflows/ci.yml（push/PR + workflow_dispatch 三输入）   │
└─ Production 反馈平面 ────────────────────────────────────────────┘
        golden-run --record ──> router-stats.db（bandit 带通带）
        router-stats recommend ──> §4 路由建议（月度校准 ref-23 §8）
```

---

## 3. 组件责任矩阵（21 脚本）

### 3.1 门禁与质量（gate）

| 脚本 | 职责 | 关键契约 |
|---|---|---|
| `robustness-suite.py` | 鲁棒性回归套件 | **184 用例**（v2.10.5：+1 patch-gate 畸形 numstat 拦截（F-53）；v2.10.4：+2 mutation-audit 自身用例；v2.10.3：+2 拦截覆盖补测（review-prefilter/toolstack-pipeline）+1 token-meter 预算闸+install-hooks 拒绝路径+1 无 --budget 计量不受影响；v2.10.2：+2 sdk_tools 差集、+1 不完整树不 traceback；v2.10.1：+2 自有脚本/stem 匹配、+2 git-push tier-4、+1 bump-version --json 契约、+2 selfcheck-static；v2.10.0：+4 patch-gate、+2 repair_confidence、+4 action-gate、+3 幂等键、+3 升级包、+1 F-41 docs 闸；v2.9.0 曾 +21），exit 0/2；`--only` 子集；`--timing` 慢点画像；`--quick` 跳过两个慢脚本（182s→81s）；夹具全临时目录 |
| `git-pre-commit.py` | 提交前门禁 | 改 SDK 脚本→robustness `--only`；数据文件→JSON+golden validate；**新文件或文档（v2.10.0 F-41）→privacy**；**任何 SDK 改动（v2.10.2 闸 4）→selfcheck-static（未登记脚本即拒）**；**fail-closed**；sanitize_env 弹出 PYTHONPATH + 5 个 git 内部变量 |
| `install-hooks.py` | 钩子安装/卸载 | 幂等；SDK_RELPATH 安装时推导（改名跟随，C0-2）；外来钩子需 --force |
| `ci-smoke.py` | 定时冒烟 | 单命令跑 **version-check（第 0 步，cheapest-first）** + **selfcheck-static（第 1 步，v2.10.1）** + robustness 全量 + golden v2/v3 validate + v3 离线 + privacy；零 LLM 离线；`--json` 时进度行走 stderr（F-45） |
| `version-check.py`（v2.8.2） | 版本串 + CHANGELOG 顺序闸 | 五处版本串一致（SKILL frontmatter/标题 · README blurb/版本行 · CHANGELOG 首个条目）+ 条目严格递减无重复；`--root` 可换文档根；exit 0/2；schema `version-check.v1`（T-16 / F-26） |
| `patch-gate.py`（v2.10.0） | 补丁规模预算闸 | numstat/diff/stat 输入；files≤5 / lines≤300 / 依赖≤1（kernel §I）；超限 exit 2 → ESCALATED；diff-risk `--verify-confidence` 合成 `repair_confidence`<0.7 → 人工（T-23 / F-29）；**F-53（v2.10.5）**：畸形 numstat 行 → 报行号干净 exit 2（原裸 ValueError traceback） |
| `action-gate.py`（v2.10.0） | 动作预执行门 | toolstack 存在性/risk_tier/args 校验（AgentOS Top4 + agentic-cicd §3.2 Tool Gateway）；tier≥4 须 --user-approved；idempotent 元数据首个消费方（T-25 / F-38 / F-35）。**v2.10.1 F-42 修正**：查表范围 = `sdk_tools` ∪ `local_tools`（原仅 `local_tools`，22 个自有脚本全被误判 DENY；现 28/28 ALLOW）+ stem 匹配（`diff-risk` ≡ `diff-risk.py`）；`git-push` 以 tier-4 登记 |
| `selfcheck-static.py`（v2.10.1 / v2.10.2 / v2.10.3 加拦截覆盖） | 静态结构自检 | frontmatter / references 完整性 / 脚本存在性 / **toolstack 一致性（双向：已登记但缺失 + 存在但未登记）** / **拦截覆盖（带非零退出路径的脚本必须有断言非零退出的用例，F-50 治本）**；秒级零 LLM；exit 2 = 结构破损；`--root` 可换检查根（fixture 可测）；**`sdk_tools` 提交时刻硬闸**：ci-smoke 第 2 步 + pre-commit 第 4 闸（F-43 治本）；豁免名单单一来源 = toolstack.json `sdk_tools_exempt` |
| `privacy-scan.py` | 隐私泄漏扫描 | 机器特定内容检出，fail-closed，`--user` 本机用户名白名单 |

### 3.2 状态与执行（state/execution）

| 脚本 | 职责 | 关键契约 |
|---|---|---|
| `task-state.py` | 任务状态机持久化 | schema task-state.v1；**28 状态**（含 CI/部署 11 态，v2.7.0 增 WAITING/CRASHED）；转移表是数据；`runs[]` 记 workflow_run_id/pr/attempt；**确定性闸门**：修复预算 / 振荡检测 / DAG 依赖；`checkpoint`+`resume` 崩溃恢复；validate 兼容旧任务 |
| `task-workspace.py` | per-task 工作区 | logs/artifacts/test-results + agent-state.json；worktree 可选；cleanup **fail-closed**（无 marker 拒绝删） |
| `verify-runner.py` | 确定性验证闸 | 分层 cheapest-first；输出 diagnostic.v1；exit 0/2；v2.1 增 `allow_missing`（缺可选工具记 skipped）+ `allow_exit_codes`（如 pytest 5）；随包预设 `scripts/presets/verify.{python,node,docs}.json`（**须带 `--cwd .`**；v2.9.0 T-18：`test` 拆为 `test-targeted` fail-fast + `test-full`，层名走显式别名匹配 `_layer_matches`）；`--confidence` 自适应深度（T-07 + T-17 security 恒保）；`--changed` 测试选择注入 targeted 层（v2.9.0 T-22，fail-open） |
| `flaky-check.py`（v2.9.0） | flaky 判别器 | N 次同输入重跑 → REAL/FLAKY/INFRA/NOT_REPRODUCIBLE/UNKNOWN 五分类（FLAKY 需 N≥5，agentic-cicd §8.4）；QUARANTINE 永不删除；exit 0=分类完成/2=用法（T-20 / F-31） |
| `regression-guard.py`（v2.9.0） | 回归测试双向闸 | `git worktree add --detach` 物化 base/head 执行：base 必须 FAIL + head 必须 PASS；WEAK_TEST / FIX_INCOMPLETE / NOT_A_REGRESSION 一律 exit 2（T-21 / F-32，kernel §B.11） |
| `diff-risk.py`（v2.7.0） | 补丁风险确定性评分 | ref-22 §8 落地：`0.30*size + 0.30*module + 0.25*history + 0.15*error_class`；`<0.3` auto / `0.3–0.7` review / `>0.7` exit 2 人工；无输入源 fail-closed |
| `bump-version.py` | 版本自管理 | 5 处版本串一致；CHANGELOG 日期头；`--commit` 本地提交，永不 push；`--sync-size`（可独立运行）回写体积声明 |

### 3.3 金标与路由反馈（eval/bandit）

| 脚本 | 职责 | 关键契约 |
|---|---|---|
| `golden-run.py` | 金标回归 | `--validate-set` 预检；`--offline` 结构性判分（零 LLM）；`--record` 入库 bandit（cell 取 8 分类 `cell` 字段）；`--baseline` A/B 回归闸（drop>2% 阻断）；v2.0 失败分类 + cost/latency/level 实算 |
| `router-stats.py` | 路由反馈与校准 | Beta 后验/Thompson `recommend`；`report` 出 cost/token/calibration/infra_rate/coverage；v2.0 增 `infra_fail`（不进后验）、`error_class`、`snapshot`（冻结先验）、`rebuild`（按日志重建 + 回溯重标） |

### 3.4 诊断与 Debug（diagnose）

| 脚本 | 职责 | 关键契约 |
|---|---|---|
| `ci-fail-analyze.py` | CI 失败分析器 | 日志→diagnostic.v1；**八类正则**（permission/dependency/unit_failure/timeout/assertion/command_missing/install_error/syntax_error）+ generic 兜底；**v2.9.0 T-19 增 origin class**（code/test/dependency/infra/environment/unknown + 日志级信号覆盖）与 `recommended_action`（origin 而非 leaf 决定动作，kernel §H） |
| `error-sig.py` | 错误签名库 | add/match，Debug L0 确定性首轮 |
| `case-search.py` | 案例库/记忆层检索 | `--layer` 分层命中（solutions/repo-facts/...） |
| `env-snapshot.py` | 环境快照 | PATH 有界，一次成型 |

### 3.5 计量与 Review（measure/review）

| 脚本 | 职责 | 关键契约 |
|---|---|---|
| `mutation-audit.py`（v2.10.4） | 门禁变异测试审计 | 对 6 个闸注入定点变异（恒放行），跑对应 robustness 子集：KILLED / SURVIVED / STALE。**补 blocking-coverage 的动态那一半**——静态检查只证明「有用例断言非零」，本脚本证明「闸坏了用例真的会红」。字节级备份还原 + sha256 校验；`--dry-run` 只校验锚点；**不可并发运行** |
| `token-meter.py` | token 计量 + 预算闸 | 指标表 + 预算闸（max_usd/max_calls）；**F-50（v2.10.2）：传 `--budget` 且超限 → exit 2**（原"0 always"只写 flags 不拦，与 coding-agent-os §16 自相矛盾）；不传 `--budget` 仍为纯计量 exit 0 |
| `review-prefilter.py` | Review 预过滤 | 差异统计+静态检查→精简关注包 |

### 3.6 spec-kit 与 CI 控制面（sdd/ci）

| 脚本 | 职责 | 关键契约 |
|---|---|---|
| `spec-tasks-import.py` | tasks.md→task-state.v1 | `- [ ] **T-xx** 标题 [P0-P3]` + 缩进验收行；不覆盖已存在（除非 --force） |
| `gh-workflow-check.py` | .github 结构校验 | dispatch 三输入契约 + reusable-only（禁 ad-hoc runs-on）+ read-only 默认 |

### 3.7 工具栈维护（toolchain）

| 脚本 | 职责 | 关键契约 |
|---|---|---|
| `toolstack-pipeline.py` | 工具栈巡检 | probe→diff→data(SHA256)→**sdk_tools 差集（v2.10.2 Stage 3b）**→report→update→commit→push-gate；gh api 上游核对 + SHA256；`--update` 自动登记未注册脚本（保守默认 tier 2 / 非幂等，**仅增不删**：缺失条目只报不删，§10.9 tier-3 需人决）；`--push` 需交互确认 |
| `probe-tools.py` | 会话工具探测 | 单次调用探全部工具，--json |

---

## 4. 数据流（四条主链路）

1. **金标→bandit**：`golden-run --set v3 --model <id> --record router-stats.db` → `router-stats recommend --cell <cell>`（Thompson 建议，仅建议，裁决留 agent）→ 月度 `report` 校准（ref-23 §8：MAE>0.1 调先验 / escalation>30% 回退 / 基础设施错误单独统计）。
2. **spec-kit→任务态**：`specify init`（spec.md/tasks.md）→ `spec-tasks-import.py` → task-state.v1（INIT，priority/acceptance 落位）→ 状态机推进（CI_QUEUED→…→DONE，`--run-id` 记 CI 串接）。
3. **CI 失败→修复环**：Actions 日志 → `ci-fail-analyze.py`（diagnostic.v1）→ ref-18 假设-证据-实验环 → `task-state transition --to REPAIRING`（runs.attempt 记账）→ 超 `max_repair_attempts=3` → ESCALATED → L5 人类。
4. **工作区↔状态**：`task-workspace create --worktree`（`task/<id>` 分支）→ 任务文件落在独立目录 → `verify` 校验隔离 + worktree 注册 → `cleanup`（fail-closed）。

## 5. 状态机（task-state.v1，26 状态）

```
本地流: INIT→UNDERSTAND→CLASSIFY→{EXPLORE,PLAN}→PLAN→IMPLEMENT→VERIFY→
        {REVIEW,DIAGNOSE,FAILED,CI_QUEUED} … REVIEW→FINALIZE→DONE
修复流: DIAGNOSE→REPAIR→REVERIFY→{REVIEW,DIAGNOSE,ESCALATED}
CI 流:  CI_QUEUED→CI_RUNNING→{CI_PASSED,CI_FAILED}→CI_FAILED→REPAIRING→{CI_QUEUED,ESCALATED}
        CI_PASSED→{MERGE_PENDING,REVIEW}
部署流: MERGE_PENDING→STAGING_DEPLOY→STAGING_VERIFY→PROD_DEPLOY→PROD_VERIFY→DONE
        (任何部署态→ROLLBACK→{REPAIRING,DONE,FAILED})
终态:   DONE / FAILED / ESCALATED
五态判定: SUCCESS / PARTIAL_SUCCESS / FAILED / REGRESSION / UNKNOWN —— 判据留 agent（§5.6）
```

## 6. 门禁体系（四层 + 版本闸）

| 层 | 触发 | 内容 | 阈值 |
|---|---|---|---|
| L0 pre-commit | 每次提交 | 改脚本→robustness 子集；数据文件→JSON+golden validate；新文件→privacy | fail-closed（exit 1 阻断） |
| L1 ci-smoke | 定时/CI | **version-check 第 0 步** + robustness 全量 + golden v2/v3 validate + v3 离线 32/32 + privacy | ALL GREEN（6/6） |
| L2 全面审计 | 每版本/专项 | audit_sdk **146 项** + extended-probe **44 项** | 100% |
| L3 版本闸 | bump 时 / 每次冒烟 | `version-check.py`：5 处版本串一致 + CHANGELOG 首条目为最新 + 顺序递减 | 一致 |
| 数据闸 | golden/基线变更 | `--validate-set` 预检 + 基线 JSON 完整性 | VALID |

**环境硬化**：子进程前 `env -u PYTHONPATH`（沙箱 shim）+ 弹出 git 内部变量；TMPDIR 用仓库外临时目录；沙箱写保护用编辑工具/sed 降级。

## 7. 风险分层（§10.9 + toolstack.json）

| tier | 含义 | 示例（toolstack.json local_tools） | 门 |
|---|---|---|---|
| 0-1 | 只读/可逆 | ocr(1) graphify(1) code-review-graph(1) context7(1) | 无门 |
| 2 | 受控修改 | specify(2) cli-hub(2) 全部 SDK 写脚本 | 自动+验证计划 |
| 3 | 破坏性 | strix(3) cleanup/rm 类 | 交叉核对+回滚验证 |
| 4 | 不可逆/凭据 | git push、凭据读写 | **结构上强制人工** |

`can_act = risk_level ≤ ceiling AND confidence ≥ threshold AND rollback validated`（ref-17）。

## 8. 操作规程

1. **新会话**：`env -u PYTHONPATH` 跑工具；新 clone/换机先 `python scripts/install-hooks.py`。
2. **每版本**：改代码 → robustness `--only` 子集 → 全量门禁（suite/privacy/audit/ci-smoke）→ `bump-version.py vX.Y.Z --apply --commit` → CHANGELOG 条目 → 验证报告 md。
3. **新增脚本**：必须配 robustness 用例（正/负向）+ audit B/C 覆盖 + README 树同步 + toolstack.json 登记（如适用）。
4. **提交**：Conventional Commits；`push` 永远显式确认（§10.2）；CI 配置推送同门槛。
5. **工具栈巡检**：月度 `python scripts/toolstack-pipeline.py --update`（push 需交互确认）。

## 9. 当前测试基线（2026-09-01，v2.9.0）

robustness **107/107**（+24 新用例：infra_fail 后验隔离 / rebuild / coverage / diff-risk 三档 / allow_missing / 修复预算 / 振荡 / WAITING / checkpoint / resume / DAG 依赖 / cost 实算 / sync-size）· audit **104/104**（A 22 / B 64 / C 18）· extended-probe **44/44** · privacy **0 残留** · ci-smoke **ALL GREEN** · golden v3 离线 **32/32** · bandit **96 条 / 8 cell 全覆盖**（capability_trials 60 / infra_fail 36 / 本地模型 qwen2.5:3b 在线基线已入库）。

**耗时画像**（`robustness-suite.py --timing`，2026-08-30 实测，全量 182s）：

| 脚本 | 耗时 | 占比 |
|---|---|---|
| git-pre-commit.py（6 用例，内部递归跑 robustness 子集） | 68.1s | 37% |
| toolstack-pipeline.py（1 用例，gh api 上游核对） | 39.9s | 22% |
| task-state.py（25 用例） | 13.7s | 8% |
| 其余 15 个脚本 | < 13s | 33% |

→ `--quick` 跳过前两个：**182s → 81s（-55%）**，供 pre-commit 子集用；全量仍由 ci-smoke 定时跑。

## 9.2 在线基线重采（2026-08-30/31）

> 流程（每次重采照抄）：备份 DB → `router-stats.py snapshot` → `golden-run --record --price-per-1k <价> --json`（本地模型慢，必须后台跑）→ `report --golden-set` 验 coverage。
> 同日踩坑：① OmniRoute 以 **0 credentials** 启动时端口在听但请求全挂（日志 `checking 0 credentials`），正常启动后才可用；② 本机 Ollama 曾丢失 `OLLAMA_MODELS` 环境（实例指向空 store，`/api/tags` 返回空模型列表），可用**隔离实例**绕开：以 `OLLAMA_MODELS` 指向本地模型库、`OLLAMA_HOST` 改用备用端口启动第二个 `ollama serve`（模型权重仍在，只是原实例指错了库），不动用户原有实例。

### 9.2.1 云池 auto/best-coding（2026-08-31 重采）

**24/32 = 75%**，quality 失败 8，infra 0（当晚免费池健康但慢：均值 36s/样本，单条最高 68s）。
存档：`baseline-golden-v3-cloud-20260831.json`。
**校准闸门首次出数：`mean|err|=0.2`（1 cell）** —— 先验快照（08-30 修复后后验）vs 快照后新观测。
此前该指标数学上恒等于 0（F-03 修复生效的直接证据）。新观测后 infra_rate 0.547 → **0.281**（低于 30% 告警线）。

### 9.2.2 本地 qwen2.5:3b（2026-08-30 重采）

云池不可用时的本地替代，32 样本 / 8 cell 全覆盖：

| cell | n | sr |
|---|---|---|
| extraction | 3 | **100%** |
| tool-use | 5 | 80% |
| code | 4 | 75% |
| qa | 4 | 75% |
| bug_fix | 5 | 60% |
| long-text | 3 | 33% |
| refactor | 3 | 0% |
| review | 4 | 0% |
| **合计** | **32** | **53%（17/32，1 例 empty 判 infra 不计）** |

- 均值延迟 **18.5s/样本**（CPU-only 低配机）；`cost_basis=flat(0)` —— 本地推理零 API 成本，如实记账。
- 基线存档：`scripts/data/baseline-golden-v3-qwen2.5b.json`（可 `--baseline` A/B 参照）。
- 重采前备份：`output/sdk-selfcheck/router-stats.db.pre-recollect-20260830`（36,864B）。

### 9.2.3 本地 minicpm5-bg:latest（1B，2026-08-31 重采）

**11/32 = 39%**（4 例 empty 判 infra 不计入能力），均值 11.5s/样本（未调优实例；用户 tuned 配置 num_thread=4 应更快）。存档：`baseline-golden-v3-minicpm5b-20260831.json`。

| cell | n | sr | 结论 |
|---|---|---|---|
| qa | 4 | **75%** | ✅ 可用（与 qwen2.5:3b 持平） |
| tool-use | 5 | **60%** | ✅ 可用 |
| extraction | 4 | **50%** | ✅ 可用（qwen 100%，1B 半程） |
| code | 4 | **50%** | 🟡 半程（qwen 75%） |
| bug_fix | 5 | 20% | ❌ 弱 |
| long-text | 3 | 0% | ❌ 不可用 |
| refactor | 3 | 0% | ❌ 不可用 |
| review | 4 | 0% | ❌ 不可用 |

**结论**：1B **有用，但只限 4 个 cell**（qa/tool-use/extraction/code）—— 简单/结构性任务的"快而省"本地档；
review/refactor/long-text 必须走云池。这正是 bandit 应该学会的分工（cheap-first 级联的本地档数据）。

## 9.1 数据修复记录（v2.7.0，F-01）

生产 `router-stats.db` 已于 2026-08-30 执行 `rebuild --retag-threshold 50`（自动备份
`router-stats.db.bak-2026-08-30T21-39-11+08-00`）：35 条 tokens<50 的空响应从"能力失败"
改判为 `infra_fail`，后验按日志重建。

| cell | 修复前 sr | 修复后 sr |
|---|---|---|
| tool-use | 40% | **100%** |
| extraction | 38% | **75%** |
| code | 34% | **69%** |
| qa | 12% | **50%** |
| long-text | 17% | **33%** |

`infra_rate=0.547` —— 超过 ref-23 §8 的 30% 线，report 会告警"供应商/网络不稳定，能力评估不可信"。
**重采基线前必须先 `router-stats.py snapshot`**，否则校准无基准。

## 10. 文档地图

| 文档 | 视角 | 读时机 |
|---|---|---|
| SKILL.md | 协议（agent 行为规范） | 每次会话热路径 |
| **ENGINEERING.md（本文件）** | 工程（架构/组件/数据流/门禁） | 改代码、评审、扩展 SDK 前 |
| ALIGNMENT.md | 架构映射（coding-agent-os → SDK） | 架构决策 |
| CHANGELOG.md | 版本时间线 | 升级/回溯 |
| refs 01-24 | 专题细则 | 按需渐进披露 |
