---
name: sdk-selfcheck
description: user-vibe_coding-sdk-moe 定期自查工作流（周/月/版本升级前）。触发词：SDK 自查、sdk selfcheck、SDK 体检、全面回归、upgrade audit。产出结构化自查报告（结论先行 + 缺陷清单 F-xx + 票项 T-xx + 决策点 D-x + 回归证据）。
agent_created: true
version: 1.1.0
---

# sdk-selfcheck — SDK moe 定期自查工作流

对 `~/.workbuddy/skills/user-vibe_coding-sdk-moe` 做静态一致性 + 门禁实测 + 数据取证 + 架构对齐的自查，产出机构级报告。全程离线零 LLM 判分（脚本给事实，判定留 agent）。

## 0. 环境硬约束（先读，每次都踩过的坑）

1. **python 用管理版绝对路径**：`C:\Users\fu268\.workbuddy\binaries\python\versions\3.13.12\python.exe`（沙箱 PYTHONPATH shim 会污染系统 python）。
2. **全量套件 JSON 必须重定向文件再解析**——管道竞态会截断。
3. **pre-commit 门禁耗时上台阶**：git commit 超时给 ≥600s；**禁止 `--no-verify`**（绕闸=纪律违规，误用了必须 soft reset 带闸重提）。
4. **MSYS 路径转换**：给 python 脚本传路径用 `D:/...`/`C:/...` 显式形态，不用 `/tmp`、`/d/...`。
5. **ci-smoke 没有 `--quick`**（那旗标属 robustness-suite）。
6. **沙箱丢 git 远端跟踪引用** → 未推数只能本地数 commit 估算。
7. skills 仓库当前分支 `ai-painting-workflow-models`（非 main）；工作区有 ~48 个非本任务技能漂移（WorkBuddy 应用侧同步产物）→ **全程显式 pathspec**（`git add <具体文件>`，绝不 `git add -A`）。
8. **交付物文档（CHANGELOG/报告/SKILL）引用机器路径一律去盘符**：写 `WorkBuddy/.../` + "（D 盘）"标注，不写 `D:\` / `D:/` 形态——privacy-scan drive-letter 规则（`[A-Za-z]:[\\/]`，仅豁免 example/sample/test/mock 前缀）对两种斜杠都命中（v2.8.0 验收 F-25 教训：CHANGELOG 自引路径 → findings=2 → ci-smoke 4/5）。
9. 工具栈巡检 JSON 报告存 `D:\WorkBuddy\softwares-update\output\`（smoke 报告、audit 脚本均在 `output/sdk-audit/audit_sdk.py`）。
10. **git 修复操作纪律（F-26 实战）**：全量 push 失败先 `git fsck` 查对象缺损；闭包验证用严格 rc（`rev-list --objects ... > /dev/null 2>err` 后查 rc——`|wc` 管道会把 stderr 计入行数且丢退出码）；历史重写走**裸副本路线**（robocopy 复制 .git + core.bare=true + filter-branch，本机工作树重写类操作 stash/checkout 会挂起数分钟）；filter-branch 残留 `.git-rewrite` 被 safe-delete 护栏拦截时用 `mv` 重命名绕开；万级小文件复制用 robocopy /MT 不用 cp -r；恢复活仓前先把坏 .git `mv` 保留（绝不直接删）。
11. **活仓被宿主实时破坏的识别特征**：HEAD 由可读→不可读、refs/heads 分支 ref 被清空、缺损行数持续增长、来历不明的 refs/replace 出现——立即停止在活仓操作，转移到 D 盘副本修复，并把"活仓受损+恢复路径"写进报告交用户处置。
12. **SDK 子目录内没有 `.git/`**：仓库根在 skills 目录（`git rev-parse --show-toplevel` → `D:/softlink/.workbuddy/skills`）。查钩子必须 `ls "$(git rev-parse --show-toplevel)/.git/hooks/"`，在技能目录里 `ls .git/hooks` 必定 No such file → **会误判"钩子未安装"**（v2.8.1 自查踩过）。同理 `git status --short -- user-vibe_coding-sdk-moe` 必须带 pathspec（仓库根有几十个其他技能的漂移）。
13. **`ci-smoke.py --report` 必须带路径参数**（`--report <file>`，无默认值）——裸写 `--report` 直接 argparse error，且 `--json` 才输出机器报告到 stdout。
14. **给 verify-runner 传 `--cwd` 用 Windows 显式形态**（`D:/...`），MSYS 形态 `/d/...` 会让子进程落点漂移。
15. **重门禁必须串行跑（F-39，v2.8.2 实施期实证）**：ci-smoke（内含 129 例 robustness）与 workspace audit_sdk（也跑 robustness `--only`）**并行**时双双假失败（pass_rate=0.984 / B 组 FAIL）——两套套件各起上百子进程，16GB 低配机资源争抢。隔离串行复跑全部通过。串行总时长 ≈6min，不要为了省时间并行。
16. **陈旧 `index.lock` 处置**：先 `tasklist | grep git` 确认无 git 进程 + 锁文件 mtime 明显早于当前时间，再 `mv .git/index.lock .git/index.lock.stale-<时间戳>`（**重命名不删除**，可回溯），然后重试。
17. **门禁套件的成本漂移会放大成假红灯（F-40，v2.9.0）**：新增昂贵夹具（如 git 仓库 init+commit）会拖慢 `--only` 子集 → pre-commit 门禁递归调用撞 60s 用例超时 → exit 124 假失败。对策已内置：git 夹具惰性搭建（`build_cases(only=...)`）+ 用例级 `timeout` 字段。自查时见到 exit 124 先怀疑资源/超时，再怀疑逻辑。
18. **"路径去盘符"约定两次复发（F-25 → F-41）**：写交付物文档时只要引用机器路径就会再犯——修复后必须复跑 privacy-scan 单项确认 findings=0 再提交；治本方向 = 文档形态闸进 pre-commit docs 链（下批待办）。

## 1. 七步自查清单（顺序执行）

### S1 静态一致性
- 版本串 grep：SKILL（frontmatter/title）、README（blurb/version-line）、CHANGELOG 顶部 —— 六处必须一致。
- **CHANGELOG 顺序检查（必做，别只看版本串）**：文件首个 `^## vX.Y.Z` 必须是最新版。v2.8.1 唯一红灯（audit 145/146）即源于此——**手工把新版本段写在旧版本段之后**，`bump-version.py` 随后检测到 header 已存在 → `[skip]`，其 layout-repair 插入逻辑（插到首个 `## vX` 之前）根本没执行。纪律：**手工写条目后必须跑 `bump-version.py --sync-size` 校验顺序**，不能只靠肉眼看版本串。
- 体积声明：`wc -c SKILL.md` == SKILL/README 声明值（bump-version --sync-size 维护）。
- refs 完整性：SKILL §9 表行 ↔ `references/*.md` 双向比对（ref-12 是外部指针，跳过文件存在性）。
- CHANGELOG 断链检查：`git log --oneline <上次自查点>..HEAD` 逐条对 CHANGELOG；**fix:/feat: 必须有记录且 bump**（data:/chore: 豁免但月度合并一条）。

### S2 门禁实测
```bash
PY="C:/Users/fu268/.workbuddy/binaries/python/versions/3.13.12/python.exe"
cd "C:/Users/fu268/.workbuddy/skills/user-vibe_coding-sdk-moe/scripts"
$PY robustness-suite.py --json > <output>/robustness-<date>.json   # 全量 ~4-6min
$PY ci-smoke.py --report <output>/sdk-smoke/<date>.json            # 5 步全量
$PY privacy-scan.py . --user fu268 --json                          # 单独取证（findings 应=0）
$PY probe-tools.py --json                                          # 工具探测（缺失工具记缺陷）
```

### S2.5 接线可达性实测（v2.8.1 新增 — 门禁"能跑通"≠"语义正确"）

全绿门禁下仍可能藏着**死分支与语义反例**。每次自查必跑两类实测：

1. **反例实测**：对有"自适应/筛选"语义的脚本，用**随包预设**跑全档位，检查被剔除的层是否合规。
   - 案例（F-27，P0）：`verify-runner.py --confidence {0.9,0.5,0.2} --config scripts/presets/verify.<lang>.json --cwd <tmp> --json` → 实测 0.9 选 `["syntax","test"]`、**security 层被筛掉**，与"安全扫描是硬闸"冲突。全量 ci-smoke 抓不到（用例用的是 canonical 名配置）。
2. **可达性实测**：协议/文档承诺的分支，用随包配置验证是否真能触发。
   - 案例（F-28）：`grep -c targeted scripts/presets/*.json` = 0/0/0 → `verify-runner.py:130-133` 的 "targeted 优先剔除 full" 分支**从未执行过**；canonical `LAYER_ORDER`（9 层）与随包预设层名（6 层）不一致，`typecheck` 仅靠子串 `"type" in "typecheck"` 巧合命中（改名即失效）。

> 判据：**canonical 名 vs 预设名必须显式映射**，禁止依赖子串巧合；文档描述的分支必须有随包配置能触发，否则记 P2。

### S3 数据取证（SQLite 直读）
- `scripts/data/router-stats.db`：routing_log 分类分布（pass/fail/infra_fail/unclassified）、bandit 覆盖（cell×模型）、prior snapshots 数。`router-stats.py report --db ... --json` 看 `unclassified_fail_rows`（>0 = 有新未分类行，先查再信）。

### S4 git 卫生
- `git log --oneline -20` + `git status --short -- .`（SDK 子树必须零噪音；`.workbuddy/` 未跟踪目录=自动化 cwd 回潜，查 F-15 复发）。
- 对照 CHANGELOG 找无记录提交。

### S5 自动化侧审计
- 两条自动化（周度 `automation-1787758826303` / 月度 `automation-1787758816382`）：cwd 必须在 `D:\WorkBuddy\softwares-update`（不在 SDK 内）；prompt 必须含 ref-23 §5.1 FAIL 处置硬规则（FAIL→原样上报停止，禁自行定性误报）。
- 月检若自行定性门禁失败 → 记 P1 缺陷（F-18 类）。

### S6 workspace 深测（可选加速轮）
```bash
cd "D:/WorkBuddy/softwares-update/output/sdk-audit"
$PY audit_sdk.py   # v2.8.1 = 146 项；FAIL 项逐条定性（陈旧断言 vs 真回归）
```
> 注意：audit 是**唯一**覆盖"版本串/CHANGELOG 顺序"的门禁（ci-smoke 不含）→ 它的红灯不能被当作"文档小事"，按 F-18 硬规则原样上报。

### S7 架构对齐（升级前或大版本后）
- 对照 `D:/WorkBuddy/data/SDK_Reference/`（v2.8.1 时 9 份）：
  - **已吸收基线**：`coding-agent-os`（ALIGNMENT 全表）· `agentos`（T-07~T-13）· `GPT-当前主流agent技术栈`（survey G1-G8）· `agent-doctor`（ref-17）· `GPT-软件工厂` / `GPT-Github_Action*`（ref-24 + C2 系列）
  - **v2.8.1 新入两份（缺口源）**：`verification-kernel-architecture.md`（12 阶段验证 / 测试选择 / flaky / 回归双向校验 / origin class / 8 项修复预算 / 三重置信度）· `agentic-cicd-design.md`（幂等原则 / TIA / flaky 四分类 / 策略版本化 / 七字段升级包 / Golden Benchmark）
  - 新缺口 → 高价值进票（协议 + 轻脚本优先），低价值进 ALIGNMENT 排除总表（附原因）。
- **已闭环的票要在报告里显式核销**（上轮 15 票中 v2.8.1 查出 AgentOS Top4「Action Validator 预执行门」悬空 → F-38）。悬空票比新缺口更危险：它已被认为"处理过了"。
- ALIGNMENT 排除表 = 决策记录，不轻易删除行。

## 2. 报告格式（写 D:\WorkBuddy\softwares-update\自查报告与改进计划-SDK-moe-vX.Y.Z-<date>.md）

1. **§0 结论先行**：健康度评级（对比上轮）+ 四维表（静态资产/执行门禁/学习闭环/架构对齐）+ P0 一句话。
2. **§1 方法与实测证据表**（12 项左右，每项带实测数字）。
3. **§2 分层体检**（静态/门禁/学习闭环/架构对齐，各一表）。
4. **§3 缺陷清单**：编号续上轮（F-xx），等级 P0 门禁失效 / P1 纪律数据 / P2 接线覆盖 / P3 卫生；证据列必须带实测输出。
5. **§4 风险矩阵**（触发条件/影响/等级/缓解，对接票项）。
6. **§5 改进计划**：票项 T-xx（动作/落点/验收闸），按 P0→P3 分批。
7. **§6 决策点**：D-x 二选一（选项 A/B + 建议），**push 永远是 D 末位等显式确认（tier-4）**。
8. **§7 回归证据块**（fenced code，全部实测数字）。

## 3. 落地轮纪律

- 改完即测：每个脚本改动 → 对应 `--only` 子集 → 全量 ci-smoke 收口。
- 提交颗粒：一个票一个 commit（Conventional Commits，`feat/fix/test/docs/chore(skill-moe): ...`）；bump 用 `bump-version.py vX.Y.Z --apply --commit --sync-size`（CHANGELOG 条目手写在前，bump 只补版本串）。
- 落地报告：`落地报告-SDK-vX.Y.Z-<主题>-<date>.md`，含"实施期发现与即时修复"表（修复过程留痕，如 v2.8.0 的映射边界反写/PROD 链路误伤两例）。
- 报告中"自查误报"要显式更正（v2.7.1 T-06 先例：toolstack.json 本有 schema 字段，首轮查错键名）。
