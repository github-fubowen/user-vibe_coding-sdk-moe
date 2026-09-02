# ref-19 — Token 脚本化流水线（scripted pipelines for token reduction）

> Load when: 任何"降低 token 消耗 / 脚本化 / pipeline"需求；Debug 验证、工具探测、版本 bump、金标回归、token 计量。
> 依据：Agent Doctor 控制面纪律（ref-17）"确定性先行、LLM 后置" + SDK §3 G-gates + ref-05 指标。
> 实现状态：**P0 三件 + P1 两件 + P2 三件全部实现（v1.12.0）**，共 9 个脚本。

---

## 1. 原则（所有脚本共同遵守）

1. **stdlib-only Python 3.9+**，零第三方依赖，放 `scripts/`（对齐 ref-15 先例）。
2. **JSON 进出**：`--json` 机器可读输出；后续阶段/agent 直接消费，中间零 LLM 叙述。
3. **Exit code 门禁**：0=干净/通过，2=失败/漂移（对齐 toolstack-pipeline）。
4. **绝不自动 push**：写操作最多到本地 commit（tier-4 门，§10.9）。
5. **输出有界**：tail 截断（默认 12 行），禁止全量日志倾倒（G1）。
6. **稳定前缀保护**：SKILL.md 只加指针行，规格全在本文件（渐进披露）。

## 2. 已实现（P0 三件，v1.11.0）

### 2.1 `scripts/probe-tools.py` — 会话级工具探测单次化
- **替代**：§6 每会话 6+ 次 `--version` 探测 tool call → 1 次确定性调用。
- **数据源**：`toolstack.json` `local_tools` manifest（单一事实源，与 ref-15 共用，防双份漂移）。
- 用法：`python scripts/probe-tools.py --json`（agent 会话首步跑一次）；`--group <g>` 过滤。
- 特性：Windows npm shim `.cmd/.exe` 回退；缺失工具不致命（G3 降级原则）。

### 2.2 `scripts/verify-runner.py` — 确定性验证闸
- **替代**：§5.6/ref-18 §4 的 LLM 叙述验证环 → 1 次调用拿 pass/fail 事实。
- 用法：
  ```bash
  python scripts/verify-runner.py --config verify.json --json   # 项目内 verify.json
  python scripts/verify-runner.py --cmd pytest -q --tail 8      # 临时单步
  python scripts/verify-runner.py --config verify.json --confidence 0.9  # 自适应深度（v2.8.0 T-07：>0.7 light / 0.4-0.7 medium / <0.4 full；--layers 显式优先；**v2.8.2 T-17：security 层任何档位恒保**）
  python scripts/version-check.py --json     # 版本串 + CHANGELOG 顺序闸（v2.8.2 T-16，F-26；ci-smoke 第 0 步）
  python scripts/verify-runner.py --config scripts/presets/verify.python.json --cwd . \
      --changed src/auth.py                  # 测试选择（v2.9.0 T-22）：约定映射 -> test-targeted 层，无映射 fail-open
  ```
- **T-17（v2.8.2）security 恒保**：`--confidence` 的轻/中档曾剔除 security 层（实测 0.9 → `["syntax","test"]`，随包预设的 pip-audit/npm audit 被静默跳过），与 verification-kernel §B.3「Stage 9 硬闸」冲突。现 `ALWAYS_ON_TOKENS=("security",)` 无条件保留；配置里没有 security 层时不会虚增。
- **T-18（v2.9.0）层名显式别名匹配**：`_layer_matches` 是唯一匹配入口（精确 / 别名表 `type<->typecheck` / `token-` 前缀族），消除子串巧合（"type" in "typecheck" 属拼写巧合，改名即静默失效）；`select_by_confidence` 与 `--layers` 统一走它。随包 python/node 预设的 `test` 层拆为 `test-targeted`（fail-fast）+ `test-full`（全量），targeted 分支从此可达。
- **T-16（v2.8.2）version-check.py**：校验 SKILL frontmatter / SKILL 标题 / README blurb / README 版本行 / CHANGELOG 首个条目五处版本串一致 + CHANGELOG 条目严格递减无重复；exit 0/2，输出 `version-check.v1`。`--root` 可指向任意文档根（供测试与复用）。
- **T-22（v2.9.0）--changed 测试选择**：变更文件 stem → `tests/**/test_<stem>.py` / `<stem>_test.py`（`test_roots` 可配，默认 tests/ 存在用之、否则顶层非递归；变更文件本身是测试则直接收录）；映射结果只注入 `test-targeted` 层；无映射 fail-open（层按原 cmd 跑，绝不静默跳过验证）；报告增 `test_selection` 块。verification-kernel §B.5：inner repair loop 通常只到 Stage 0-6 —— 这是低配机最大的省时项。
- `verify.json` schema：`{"steps":[{"name":"test","cmd":["pytest","-q"],"timeout":120}]}`
- **职责边界**：脚本只报 pass/fail 事实；五态判定（REGRESSION/UNKNOWN，ref-18 §4）留在 agent。

### 2.3 `scripts/bump-version.py` — 版本 bump 单命令化
- **替代**：§10.8 每次 bump 的 6-10 次手工编辑+提交 → 1 命令。
- 用法：`python scripts/bump-version.py v1.12.0 --apply --commit`
  - 自动改：SKILL.md（frontmatter+title）、README（blurb+version-line）、CHANGELOG 插入日期头。
  - 默认 dry-run；`--json` 机器可读；**永不 push**（§10 纪律内置）。
  - ⚠️ header 已存在时 `[skip]`（**不会**纠正手工写入的错误顺序，F-26 教训）——手工改 CHANGELOG 后必须跑 `version-check.py`。

### 2.4 `scripts/flaky-check.py` — flaky 测试判别器（v2.9.0，T-20 / F-31）
- **替代**：§5.6/ref-18 的"一次失败即修代码"反模式 → N 次同输入重跑的确定性分类。
- 用法：`python scripts/flaky-check.py --runs 5 --json --cmd pytest -q tests/test_x.py`
  （`--json` 必须在 `--cmd` 之前 —— `--cmd` 是 REMAINDER，吞掉其后所有参数）。
- 分类：REAL（全失败→REPAIR）/ FLAKY（混合且 N≥5→QUARANTINE，永不删除）/ INFRA（失败全带超时/网络指纹→RETRY）/ NOT_REPRODUCIBLE（全通过→TREAT_AS_UNKNOWN，fail-closed 不跳过验证）/ UNKNOWN（混合但 N<5→TREAT_AS_REAL）。
- schema `flaky-check.v1`；`flaky_probability = 2*min(fail_rate, 1-fail_rate)`（确定性代理，非二项检验）。

### 2.5 `scripts/regression-guard.py` — 回归测试双向闸（v2.9.0，T-21 / F-32）
- **替代**：无法拦截"自证式弱测试"的空白 —— verification-kernel §B.11 双向机械验证。
- 用法：`python scripts/regression-guard.py --cwd <repo> --base HEAD~1 --json --test pytest -q tests/test_x.py`
  （`--test` 是 REMAINDER，放最后）。
- 判定：VALID_REGRESSION_TEST（base FAIL + head PASS，exit 0）/ WEAK_TEST（两边都过，exit 2）/ FIX_INCOMPLETE（两边都挂，exit 2）/ NOT_A_REGRESSION（base 过 head 挂，exit 2）。
- 机制：`git worktree add --detach` 物化 ref 到临时目录执行，finally 清理；**未提交的修复不在覆盖范围**（先 commit 再过闸，§10 规则 1）。

### 2.6 `scripts/patch-gate.py` — 补丁规模预算闸（v2.10.0，T-23 / F-29）
- 用法：`git diff --numstat > n.txt && python scripts/patch-gate.py --numstat-file n.txt --json`（也支持 `--diff-file` / `--stat "7,320"`）。
- 预算（默认 kernel §I）：files≤5 / changed lines≤300 / 依赖清单≤1；超限 exit 2 + `recommended_action: ESCALATED`。
- 与 diff-risk 的分工：**评分 vs 预算闸**——diff-risk 建议人工，patch-gate 硬拒绝；`--verify-confidence` 让 diff-risk 合成 `repair_confidence`（<0.7 → `human_review_required`，B.21）。

### 2.7 `scripts/action-gate.py` — 动作预执行门（v2.10.0，T-25 / F-38）
- 用法：`python scripts/action-gate.py --tool ocr --args-json '{}' --json`。
- 决策：未知工具→DENY；tier≤2→ALLOW；tier=3→ALLOW 附强制条件（交叉核对+回滚验证）；tier≥4→DENY，仅 `--user-approved`（用户显式确认后）放行并记 `human_approval`。
- toolstack.json `idempotent` 元数据的首个消费方：非幂等工具附"重试需幂等键（T-26）"。
- 注意：CHANGELOG 条目**正文**留给 agent 填写（叙述性内容不脚本化），脚本只插头部。

## 3. 已实现 P1（Debug 零 LLM 首轮）

### 3.1 `scripts/golden-run.py` — 金标回归 1 命令化
- **替代**：§8/ref-05 金标回归（手动/LLM-as-judge 多回合）→ 1 命令。
- 结构性判分（regex/contains，**零 LLM-judge**）；默认接 OmniRoute `$OMNIROUTE_URL`（OpenAI 兼容），`--offline` 纯判分模式。
- 用法：
  ```bash
  python scripts/golden-run.py --set golden-set.json --model auto --json
  python scripts/golden-run.py --set golden-set.json --offline        # 判分预填 response 的样本
  python scripts/golden-run.py --set golden-set.json --baseline base.json --json  # A/B diff（回归 >2% exit 2）
  python scripts/golden-run.py --set golden-set.json --validate-set   # 预检 accept 规则（v1.15.0，fail-fast，零 LLM 调用）
  ```
- 输出：pass rate / in/out tokens / token efficiency / baseline diff（ref-05 §2 指标表）。
- 金标集 schema：`{"samples":[{"id","task_type","prompt","accept":[{"type":"regex|contains","pattern"}],"expected","difficulty"}]}`。
- **`--validate-set`（v1.15.0）**：跑回归前预编译全部 accept regex + 校验字段，坏规则立即列出并 exit 2——避免把坏集跑进 LLM 烧 token。

### 3.2 `scripts/error-sig.py` — 错误签名库 add/match
- **替代**：ref-18 确定性先行步骤 2（日志/签名匹配）→ 持久化零 LLM 查询。
- 用法：`add --pattern "a,b" --label .. --fix ..`（写 `scripts/data/error-signatures.json`）｜`match --text "..." --json`｜`list`。
- 首次 Debug 遇到新颖错误 → `add` 沉淀；后续 `match` 直接命中已知修复，跳过一次完整诊断。

### 3.3 `scripts/case-search.py` — 问题案例库检索
- **替代**：ref-18 §5 案例库手工翻查 → grep 式检索（按命中数排序，标题优先）。
- 用法：`case-search.py --q "症状关键词"`（默认 `.workbuddy/debug-cases/`，可 `--dir` 指定）；多关键词空格分隔 = 文件内 AND。

## 4. 已实现 P2（按需）

| 脚本 | 替代的 LLM 消耗 | 用法 |
|---|---|---|
| `env-snapshot.py` | ref-18 "查环境"多轮 → 一次性快照 | `--json --log app.log --configs "a.json,b.json"`；PATH 默认截断 10 条（G1），npm 等 `.cmd` 回退 |
| `review-prefilter.py` | Review 大 diff 全量注入 → 精简关注包 | `--base main --json`（diff 统计 top-N + 检查步骤）；检查失败 exit 2（阻塞标记） |
| `token-meter.py` | G4/G6 人工计量 → 自动指标 | `--log calls.jsonl --prices '{"model":x}' --json`；ref-05 §7 JSONL schema，缺失字段 CJK-aware 估算 |
| `diff-risk.py`（v2.7.0） | ref-22 §8 补丁风险分层从"协议文本"→真闸门 | `git diff \| python scripts/diff-risk.py --stdin --json`；`--files/--lines/--stat/--diff-file` 四种输入；`>0.7` → exit 2 人工审核。fail-closed：无输入源也 exit 2 |
| `robustness-suite.py` | 鲁棒性回归套件（v1.15.0） | `python scripts/robustness-suite.py`（exit 0/2）；`--only <脚本名>` 过滤；`--json` 机器可读；**v2.7.0**：`--timing`（逐用例计时 + 按脚本聚合，定位慢点）、`--quick`（跳过 toolstack-pipeline/git-pre-commit 两个实测占全量 41% 的慢脚本） |
| `privacy-scan.py` | 公开推送前人工 grep 隐私扫描 → 脚本化（v1.16.0） | `python scripts/privacy-scan.py <dir> [--user <名>] [--allow-user <名>]`；五组模式（users/paths/endpoints/keys/emails），文档 EXAMPLE 与通用路径自动过滤，exit 0 干净 / 2 阻断。**v2.7.1（F-15）**：`.workbuddy/{automations,memory}/` host 运行时目录默认排除（自动化 cwd 写入物引机器路径属设计使然），`--include-runtime` 覆盖；`.workbuddy/debug-cases/` 为交付物仍扫描 |
| `bump-version.py`（v2.7.0） | 体积声明漂移人工核对 → 脚本回写 | `python scripts/bump-version.py --sync-size [--apply]`（独立模式，不需带版本号）；回写 SKILL/README 的 `实测 xB` 与 `~xKB`。幂等，可入 ci-smoke |

### 4.1 随包验证预设（v2.7.0，T-07）

`scripts/presets/verify.{python,node,docs}.json` —— 远端 CI 早有 `.github/reusable/*.yml`
模板，本地确定性闸却要每个项目手写 config，导致没人用。现随包提供：

```bash
python scripts/verify-runner.py --config scripts/presets/verify.python.json --cwd .
python scripts/verify-runner.py --config scripts/presets/verify.docs.json    --cwd .
```

- ⚠️ **`--cwd .` 必填**：verify-runner 默认 cwd = config 所在目录（presets/），不指定会把命令跑在预设目录里。
- `allow_missing: true`：ruff/mypy/eslint 等可选工具未安装（exit 126/127）记 `skipped` 而非失败——否则预设在缺工具的机器上必然红灯。
- `allow_exit_codes: [5]`：pytest 的 5 = "没有收集到测试"，不是测试失败。
- 阶梯顺序对齐 harness §21：format → lint → typecheck → test → security（短路由 cheapest-first）。
- ⚠️ **JSON 内嵌 Python 的 privacy 陷阱**（实测）：`privacy-scan` 的 `drive-letter` 规则匹配
  「单词边界 + 单字母 + 冒号 + 反斜杠或斜杠」。而 JSON 里的换行是**字面反斜杠 + 字母 n**，
  所以 `except ... as e:` 后接换行会被读作"盘符 e + 反斜杠" → 误报（本文件若直接写出该形态
  同样会被扫到，故此处改用描述而不写字面量）。规避：内联脚本不要写
  `except X as <单字母>:`（改用不带 `as` 的 `except X:`，或变量名 ≥2 字母）。
  已修：`verify.docs.json` 的 encoding 层。

## 4.5 种子数据（v1.13.0，v2 于 v1.14.0 更新）

| 路径 | 内容 | 用途 |
|---|---|---|
| `scripts/data/golden-set-v1.json` | 20 条 CN 样本，5 族（qa 4 / code 4 / long-text 3 / extraction 4 / tool-use 5），全结构性 accept 规则 | 初版判分规则（个别过严，已被 v2 取代） |
| `scripts/data/golden-set-v2.json` | 同 20 样本，放宽 ext-03（中英键皆可）与 tool-05（同义词组） | **推荐使用**：`golden-run.py --set scripts/data/golden-set-v2.json --model <id> --json` |
| `scripts/data/baseline-longcat-v1.json` | LongCat（lc/LongCat-2.0）首条基线（v1 集，18/20=90%） | `--baseline` A/B 对比参照 |
| `scripts/data/error-signatures.json` | 12 条已知签名（沙箱 shim / tmp 路径 / PAT 403 / index.lock / OmniRoute 503 / SSE 流等） | `error-sig.py match --text "$(cat err.log)"` 直接命中已知修复 |
| `.workbuddy/debug-cases/` | 4 个真实 incident 轨迹（pytest shim / changelog 布局 / tmp 路径 / OmniRoute 503） | `case-search.py --q "关键词"` 复用；新 Debug 收尾按 ref-18 §5 模板追加 |

## 4.6 Coding Agent OS 吸收（v2.x，T8-T13）

| 路径 | 内容 | 用途 |
|---|---|---|
| `scripts/data/golden-set-v3.json` | **32 样本 / 8 cell 标签**（qa/code/long-text/extraction/tool-use/bug_fix/refactor/review），全结构性 accept 规则，离线判分 32/32 | **推荐使用**：`golden-run.py --set scripts/data/golden-set-v3.json --offline --json`（零 LLM）；在线建基线接 `--model <id> --record <db>` |
| `scripts/data/baseline-golden-v3-offline.json` | v3 离线基线（32/32，eff 19.4） | `--baseline` A/B 参照（在线基线待免费池稳定后补） |
| `scripts/data/memory/` | 分层记忆 4 层 JSON（repo-facts / conventions / solutions / preferences，schema `memory.v1`） | `case-search.py --q "..." --layer solutions --dir scripts/data/memory` 结构化匹配检索（ref-20/ref-21） |
| `scripts/data/router-stats.db` | 路由反馈带（runtime 生成，**不提交**）：routing_log + bandit(α,β,infra_count) + bandit_prior_snapshot | `golden-run --record` 写入 → `router-stats.py report/recommend/snapshot/rebuild` 读（ref-20/ref-22/ref-23） |
| 效率指标（T13） | router-stats report：`cost_per_successful_task` / `token_efficiency` / `escalation_rate` / `infra_rate` /校准误差 | 每阶段收尾采集，纳入 §8 指标看板；cache hit 仍由 token-meter 管 |

### 4.6 router-stats v2.0 数据修复（v2.7.0，F-01/F-03/F-11）

自查发现 bandit 在**用噪声学习**：64 条记录里 44 条 fail 中有 35 条 `tokens < 50`
（实测 3–13 tokens = 空响应/截断），全部被当作"模型能力不行"计入 α/β，把成功率压到
qa 12% / code 34%。修复方式：

```bash
# 1) 备份 + 回溯重标（tokens<50 的 fail → infra_fail/empty）+ 按日志重建后验
python scripts/router-stats.py rebuild --db scripts/data/router-stats.db --retag-threshold 50
# 2) 冻结先验快照，使校准闸门重新可响
python scripts/router-stats.py snapshot --db scripts/data/router-stats.db
python scripts/router-stats.py report  --db scripts/data/router-stats.db \
    --golden-set scripts/data/golden-set-v3.json
```

| 子命令 | 作用 |
|---|---|
| `record --outcome infra_fail --error-class {infra,timeout,empty,quality}` | 非能力失败**不进 α/β**，只累加 `infra_count` |
| `rebuild [--retag-threshold N] [--no-backup]` | 由 routing_log 重建 bandit；默认先写 `.bak-<ts>` |
| `snapshot` | 冻结当前后验为校准先验（**重采基线前必须跑**，否则校准无基准） |
| `report --golden-set <path>` | 增 `coverage`（golden cell 覆盖度），暴露零数据 cell |

**校准指标重定义**：v1 用 `α/(α+β)` 比 `sc/n`——两者由同一组计数导出，**恒等，MAE 恒 0**。
v2 改为 `bandit_prior_snapshot` 的先验均值 vs 快照之后新观测的 sr，误差才可能为 0 之外的值
（ref-23 §8 的「MAE>0.1 调先验」因此重新可触发）。

**F-11 根因**：golden-run 曾用样本的 `task_type`（5 分类粗粒度）记账，而 8 分类细粒度标签在
`cell` 字段 → bug_fix/refactor/review 三个 cell 永远没数据。现改为优先取 `cell`。

## 5. 与 SDK 其他部分的关系

- **§6 工具路由**：probe-tools 是 §6 "probe once per session" 的落地实现（G3 静态路由）。
- **§5.6/ref-18**：verify-runner 是验证阶段的确定性事实源；五态判定仍在 agent。
- **§8/ref-05**：golden-run（P1）把"回归纪律"变成 1 命令，指标表按 ref-05 §2 定义输出。
- **§10.8**：bump-version 把自版本管理脚本化；push 门禁纪律原样保留。
- **ref-15**：probe-tools 复用 toolstack.json；所有新脚本应纳入 toolstack 管治（防漂移）；**robustness-suite.py 建议并入月度巡检**（脚本变更后先跑套件再提交，即 ref-15 probe 阶段前置自检）。
- **公开推送前门禁（v1.16.0）**：`privacy-scan.py` 作为推送前置检查——公开仓库推送前跑一次（`--user <本机用户名>` 等），0 项才允许 push；v1.15.1 脱敏、v1.15.2 OmniRoute 端点脱敏均由人工 grep 完成，脚本化后防复发（sdk-snapshot 分支教训）。

## 6. 已知边界

1. verify-runner 判定只含 exit code——不解析测试断言文本（保持确定性，不依赖脆 regex）。
2. bump-version 只替换与旧版本**精确匹配**的版本 token，不做正则横扫（防误伤）；changelog 头插入**布局健壮**（v1.13.1 起：插到首条 `## v` 之前，不再依赖标题位置）；CHANGELOG 仍建议保持规范布局（标题最上、新条目最上）。
3. 沙箱 PYTHONPATH shim 可能干扰系统 python 的包（实测 pytest 在其 myenv 下报 `__spec__`）——脚本自身零依赖不受影响，但**被探测的工具**可能因环境损坏而报失败，属预期降级。
4. Git Bash `/tmp` 路径在 Windows Python 下不被解析（token-meter 首测 no records）——测试/调用请用 Windows 风格路径。
