# CHANGELOG — user-vibe_coding-sdk-moe

> 版本历史集中于此文件（G2 渐进披露：按需加载，不进 SKILL.md 热路径）。
> SKILL.md 保持静态前缀以维持 prompt cache 命中（G5）。最新版本见本文件顶部。

> 更早条目（v1.x 时代）见 **CHANGELOG-archive.md**（F-62 归档策略：条目 >30 天移入归档）。

## v2.10.12（2026-09-04）

> **评审清偿批次** —— 可维护性/可扩展性增量复审（2026-09-04 报告）P0-P3 逐项落地。

### N-1 · `_common.py` 半成品收尾（F-58 首批落地）

- `sdk_tools_exempt: ["_common.py"]`（toolstack.json）—— selfcheck 活体红灯 exit 2 → 复绿；
  toolstack-pipeline Stage 3b 同步感知豁免（`on_disk - sdk_tools - exempt`）；ENGINEERING 增库行（非工具、无 CLI）
- 首批接入：action-gate / diff-risk / patch-gate（exit 码契约 / 规范 JSON 序列化 / schema id 单点 / argparse 母版）；判定逻辑留在各闸

### 文档批次（F-64 / F-65 / F-66 / N-4 / E-3）

- **用例计数单点化**：README/ENGINEERING 的"190"（实为 227，已失真）改为指向套件 `--json` 的 `total` 字段；ENGINEERING 单元格 mini-changelog 移交 CHANGELOG
- **SKILL §9 引用表按编号重排**（ref-17/18 归位，01→25 连续）
- **版本戳自指勘误**：ENGINEERING"第 7 点"/ALIGNMENT"第 8 点"统一为"版本戳一致性闸（七戳含本文件）"；顺带修正 version-check 行"五处"→"七处"（v2.8.2 时代残留）
- **ref-12 重新定性（E-3）**：SKILL §9 表的路径格是 selfcheck `REFRE` 解析 ref 的机器可读源，`../` 相对路径受存在性闸校验 —— 断链**可见**而非静默，保留路径 + 补外部注册说明（原"指针化"方案会打破解析契约，实测 selfcheck unresolvable 证实）

### F-62 · CHANGELOG 归档

- v1.x 时代 21 条目（v1.0~v1.16.0，08-15~08-22，v2.0 重写前历史）预归档至 **CHANGELOG-archive.md**；主文件 107.4KB → 81.9KB + 指针行
- 归档策略写入归档头部（条目 >30 天移入；今日最老条目仅 20 天，v1.x 预归档属机制建立）；version-check 顺序闸不受影响（实测 exit 0）

### F-63 · data/ 保留策略

- 删过期 `router-stats.db.bak-2026-08-30`（未跟踪冗余件；0901-backfill 为回填溯源记录保留）
- ci-smoke `--report` 落盘后同前缀带日期旧报告保留最近 **7** 份（`REPORT_KEEP=7`；仅匹配日期收尾文件名，无日期文件永不触碰）；+1 用例（8 旧 + 1 新 → 留 7、最旧 2 清、新报告在）

### F-59 Phase 1 · robustness 用例数据化

- **135 条常量参数用例（C() 总量 220 的 61%）AST 保真迁移至 `scripts/cases/` 五域 manifest**（eval 29 / gates 26 / router 30 / release 24 / pipeline 26；schema `robustness-cases.v1`）；args 支持 `{tmp}` 占位符
- loader **fail-closed**：manifest 不可读 / schema 不符 / 缺字段 → exit 2，绝不静默跳过；与 build_cases 产物同构合并（cmd 构造 / want/dont/timeout 语义一致）
- selfcheck-static 新增 **style-3**：manifest 纳入拦截用例收集（迁移后 24 个受闸脚本 **0 gaps**）
- run_case 增 `env_extra` 通道（用例级环境注入，测试钩子 `ROBUSTNESS_CASES_DIR` 可指向临时夹具）
- **临时目录清理改分离进程**：沙箱把 TMP 重定向至 D:\Temp，Windows 原生 rmdir 被过滤驱动间歇阻塞（faulthandler 实证卡在 `TemporaryDirectory.__exit__`）→ 全量 `--quick` 曾在 200+ 用例全绿后卡死于 cleanup；改为 mkdtemp + try/finally + 分离 `rd /s /q`，套件永不等待清理
- 新增 loader 契约用例（importlib 直载套件模块，不递归跑套件）；总用例 238（85 程序化 + 17 内嵌 fixture 用例 + 135 manifest + 1 契约）
- Phase 2（未做，挂账）：tmp 夹具引用类用例的 manifest 化（需夹具声明 DSL，待评估）

### 验证

- selfcheck-static ok（24 gated / 0 gaps）· version-check 七戳一致 · robustness `--quick` **225/225（220s，清理不再阻塞）** · router-stats 23/23 / action-gate 14/14 / ci-smoke 子集 3/3 分域实测
- 基线对账（2026-09-04 增量复审）：F-57 部分（graft）｜F-58 首批落地｜F-59 Phase 1｜F-60/F-61 上版已清偿｜F-62/F-63/F-64/F-65/F-66 本版清偿｜E-3 重新定性｜E-4 上版已清偿

## v2.10.11（2026-09-03）

> **Epic B（F-60）—— 版本戳闸扩容 5 点 → 7 点。**
> 取自清偿包 `sdd-sdk-improve-v2.11`（T-511 / T-512，批次 1 / P0），按 Epic E 同一裁决
> 提前执行并改 patch 号：本会话连续 bump 四次，ENGINEERING/ALIGNMENT 两枚戳一次都没跟上，
> 正是 F-60 描述的漂移，越早堵越好。

### T-511 · version-check 扩容到 7 点

- 新增两点：
  * `engineering_head` —— ENGINEERING.md 头部 `> vN.N.N · …`
  * `alignment_head` —— ALIGNMENT.md 头部「吸收对象本体：…（vN.N.N）」
    （ALIGNMENT 有多个「吸收对象：」行，「吸收对象本体」全文件唯一，用它定位）
- **容错口径（R-B1）：缺戳 → warning 不 fail，错戳 → fail**。
  这两份是工程视图/架构映射，不是发布物 —— 没戳只是漏标，戳错了是**明确记录了错误信息**，
  性质不同（"没写注释" vs "写错注释"）。文件缺失同样只 warning
  （fixture 文档根没有这两份，不得因此 fail-closed）
- 输出增 `warnings` 段，与 `problems` 分开 —— **可提示 ≠ 可拦截**
- **bump-version 同步扩容 TARGETS**（+`engineering-head` / `alignment-head`）：
  闸门从 5 点扩到 7 点后，发布工具必须成对改，否则下一次 bump 立刻把新闸打红。
  这条配套已用一条用例固化（bump 计划必须含这两枚戳）
- 实测（提交前）：正确报出 `engineering_head=v2.10.1 != v2.10.10`、
  `alignment_head=v2.10.2 != v2.10.10`

### T-512 · 修正现存漂移

- ENGINEERING.md 头：v2.10.1 → 当前（日期同步）；ALIGNMENT.md 头：v2.10.2 → 当前
- 两份文档各加一行说明：该戳受 `version-check.py` 第 7/8 点校验（错戳 exit 2、缺戳仅 warning）

### 端到端自证

```
python scripts/bump-version.py v2.10.11 --apply --sync-size
python scripts/version-check.py --json     # ok=true，七点全 v2.10.11，warnings=[]
```

**一条命令同步七点** —— 这才是 T-511 真正的收益：不是多两个检查项，而是**漂移从此不可能发生**
（bump 自动同步 + 闸守住手工改动）。

### 验证

- ci-smoke 7/7 绿；`version-check` 七点一致、`changelog_order_ok=true`、`warnings=[]`
- robustness +5 例（七点全一致放行 / ENG 戳错拒 / ALIGN 戳错拒 / 缺戳仅 warning /
  bump 计划含两枚新戳）
- SKILL.md 36,950B 未变（本轮零热路径增长）；S-4 余量 50B

## v2.10.10（2026-09-03）

> **Epic E（F-61）—— SKILL.md 热路径尺寸闸 + §5.6 流水账下沉。**
> 取自清偿包 `sdd-sdk-improve-v2.11`（T-541 / T-542），**提前执行**：它是唯一能解除
> "热路径只剩 84B 余量"封印的票，ResourceOS P1/P2 两轮都被它卡住。
> 版本沿用 v2.10.7 裁决：patch 递增，**不占用 v2.11.0–v2.13.1 清偿包号段**
> （`version-check` T-16 强制 CHANGELOG 严格递减，按原定 v2.12.0 发会堵死批次 1）。

### T-541 · SKILL.md 热路径尺寸闸

- 阈值常量化：`SKILL_WARN_BYTES = 40_000` / `SKILL_FAIL_BYTES = 45_000`；
  `--max-skill-bytes` 覆盖 warn（fail 保持 warn + 5,000 的带宽 —— 单点调参不该把闸门调没）
- fail → **problem（exit 2）**；warn 仅 note，不阻塞
- 增 **S-4 advisory**：>37,000 B 出 note。清偿包的 S-4 判据（≤37,000B）比 warn 阈（40,000B）
  **更严**，若不加这条 advisory，S-4 会在 40KB 的闸下**静默失效** —— 把"本轮验收目标"
  与"长期闸"显式分开
- 输出增 `skill_size` 段（bytes / warn_bytes / fail_bytes / s4_target_bytes / verdict）
- robustness +4 例（超 fail 拦截 / 超 warn 只提示 / 超 S-4 advisory / 阈值覆盖）

### T-542 · §5.6 闸门流水账下沉

- 原 T-16..T-26 逐条定义以 inline 长段落堆在 §5.6（每版必涨，是 F-61 失控主因）。
  现按"**热路径只留判据与指针**"下沉：五态表 + 三条硬闸表（含命令）保留，
  原 ~3.5KB 流水账 → 按 ref 分组的三行台账指针
- 分布：ref-19（T-07/T-16/T-17/T-18/T-22/T-25，明细本来就在）· ref-22（T-19 origin 分流 /
  T-20 / T-21 / T-23 / T-24）· ref-23（CI 归因与流水线）· **ref-20 §6.1（新增 T-26 幂等键）**
- **只增不删**：T-26 是此前**唯一没有任何 ref 覆盖**的闸，先补 ref-20 §6.1
  （问题背景：重试≠重放，PLAN→IMPLEMENT 重投会被判 illegal 并计入修复预算 F-35 实测；
  三态判据表；"必须**先于**合法性·预算·振荡闸"的顺序要求），再从热路径移除
- 体积：**39,916B → 36,948B**（-2,968B）· **S-4 判据（≤37,000B）PASS**，余量 52B

### 当前热路径余量

| 阈值 | 值 | 当前（36,950B） |
|---|---|---|
| S-4 判据（清偿包） | 37,000B | 余 **50B** |
| warn | 40,000B | 余 3,050B |
| fail | 45,000B | 余 8,050B |

> 注：S-4 余量偏紧是预期内 —— 37,000B 是清偿包自评口径，而长期闸是 40/45KB。
> 后续新增协议行应**默认下沉 refs**；真要占用热路径时，`--max-skill-bytes` 是有记录的显式动作。

## v2.10.9（2026-09-03）

> **ResourceOS 对齐线 P2（R-7 / R-8 / R-9 / R-10）—— 收官批次。**
> 关闭 G-5 度量面（R-7）、G-6 声誉时间维度（R-8）、G-7 注册查重（R-9）、G-8 追溯主键（R-10）。
> 至此计划 9 张新票（R-1, R-3..R-10）**全部落地**，仅 R-2（= F-61 尺寸闸）留在清偿包 Epic E。
> 版本沿用 v2.10.7 裁决：patch 递增，**不占用 v2.11.0–v2.13.1 清偿包号段**。

### R-8 · 声誉时间维度（G-6）

- `ema_freshness()`：EMA 成功率（半衰期 30 次调用，alpha = 0.5^(1/H)）× freshness decay
  （exp(-0.05 × 距最近一次 pass 天数)，半衰期 ≈13.9 天）→ `confidence`
- 与 Thompson 排名**并列输出，不改排名** —— **bandit 仍只是建议**（§4 裁决不变）
- 低样本（<5）→ `confidence_label=insufficient`；全部候选均低样本时
  `fallback_to_static=True` + `fallback_reason`（明确回退静态矩阵）
- 三阈值全部 CLI 可调：`--ema-half-life` / `--freshness-decay` / `--min-sample`
- `infra_fail` 不进 EMA —— 沿用 F-01 既有裁决：基础设施抖动不算模型能力
- 实测：m_old 累积成功率 0.667（成功全在 41 天前）→ conf **0.1022**；
  m_new 近期 8 连胜 → conf **0.9512**，rank1 = m_new ✅

### R-9 · 重复登记检测（G-7）

- 双通道：name 用**重叠系数** |A∩B|/min(|A|,|B|)（判"名字是已有名字的超集"，
  Jaccard 会被后缀稀释 —— `verify-runner-alt` vs `verify-runner` 只有 0.5）；
  desc 用 **Jaccard**（note + group + category + capabilities，§21.1 原始口径）
- 通用默认 note（"auto-registered by…"）**不计入候选侧** —— 它对所有自动登记条目
  都一样，计入会把任意两个自动登记条目误判为重复
- 分词：ASCII 按非字母数字切分 + CJK 字 bigram，剔除噪声词 "py"
- 处置：`--update` **扣住**疑似重复项不登记（日志 `[held]`），人工确认后
  `--allow-duplicate` 放行；阈值 `--dup-threshold` 可调（默认 0.7）
- 报告增 `suspect-duplicate` 状态行，**不改 drift 语义**（未登记才是 drift）
- 新增 `--scripts-dir`（否则只能在真 scripts/ 里造文件才能测查重）

### R-7 · 上下文分类观测（G-5 度量面）

- 五类与 SKILL §7 预算表**逐行对齐**：system / task / refs / memory / results
  （"活动资源 L3" 即 refs）；未知或缺失落 **`unclassified` 且不丢弃** ——
  分类漏标本身就是要被看见的信号
- 输出增 `by_category` + `category_budget`；`--category-budget` 传软上限，
  超限**只写 flag 不拦截**（只观测不分配 —— 分配仍是 agent 的判断）
- 超限 flag 复述 reasoning 硬底线："压缩输入类，但不得挤占输出推理空间"
- `--db` 显式指定才落 `router-stats.db` 的 `context_budget_log` 表；落库失败
  只报告，不改变退出码

### R-10 · trace_id 贯穿（G-8）

- `new_trace_id()`：**ULID 风格**（10 字符毫秒时间戳 + 16 字符随机，Crockford
  base32，26 字符）—— 时间有序可按前缀粗排序，stdlib only
- 贯穿三处：task JSON 头（schema 之后）/ 每条 transition 事件 / events.jsonl 每行；
  5 个事件构造点全部接上（created / transition / transition_rejected /
  duplicate_ignored / resume），取不到时留空**不伪造**（老任务无此字段）
- `transition` 输出回传 trace_id —— 调用方无需回读任务文件即可串联
- `trace-export --trace <id>`：跨任务重建（events.jsonl 全扫 + 反查带该 id 的
  任务 JSON），输出 `trace.v1`；未知 id / 都不传均 exit 2
- `init --trace-id`：外部系统可指定（否则自动生成）
- **最小 diff**：只加字段与一条检索路径，不改状态机与转移表

### 验证

- ci-smoke **7/7 绿**（version-check → selfcheck-static → robustness `pass_rate=1.0`
  （用例数 208 → **227**（全量）/ 205 → **214**（`--quick`），本轮 **+19**）→
  golden v2/v3 validate → golden v3 离线 1.0 → privacy-scan `findings=0`）
- `tool_health`: {"active": 37}
- **SKILL.md 体积未变（39,916B）** —— P2 全部四票**零热路径增长**，协议条款一律
  留在 refs；距 40KB warn 线仍剩 84B，Epic E（F-61 尺寸闸 + §5.6 下沉）依旧必须做

## v2.10.8（2026-09-03）

> **ResourceOS 对齐线 P1（R-3/R-4/R-5/R-6）**——从"概念对齐"进到"数据面 + 轻量脚本"。
> 关闭 G-2（无能力层）/ G-3（工具无健康态）/ G-4（步骤序硬编码）/ G-5（只有闸门没有预算表）。
> 版本沿用 §10 规则 8 豁免边界做 patch 递增（理由同 v2.10.7）：**不占用 v2.11.0–v2.13.1 清偿包号段**。

### R-3 · toolstack.json schema 3 → 4（G-2 / G-3 数据面）

- 两表（29 脚本 + 8 外部工具）条目增四个 **optional** 字段：`capabilities` / `fallback` /
  `health`（active|degraded|unavailable）/ `last_checked`；顶层新增 `capability_vocab`
  （**36 词扁平词表**，新词需人工确认 —— ResourceOS §6.3 反词表蔓延闸的 SDK 等价物）
- `selfcheck-static` 扩四项校验：**能力词必须在词表内 / health 必须合法枚举 / fallback 不得断链 /
  capabilities 必须是 list[str]** → problem（拦截）；**字段缺失仅 note**（向后兼容，
  toolstack-pipeline 自动登记的新脚本不会被卡）
- 覆盖度：37/37 条目 100% 有 capabilities；13 条脚本 + 3 条外部工具声明 fallback
- robustness 增 6 例（4 负向拦截 + 2 向后兼容）

### R-4 · 工具健康态维护（G-3 行为面）

- `probe-tools --write-back`：探测结果**原子回写** toolstack.json（tmp+replace，内容无变化不落盘）
- 三态阶梯：连败 1 次仍 active（防抖动误判）→ **2 次 degraded** → **4 次 unavailable**；
  任一次成功即回 active 且连败清零（§19 DEGRADED→ACTIVE 回边）；阈值 `--degraded-after` /
  `--unavailable-after` 可配；连败计数存 `_fail_streak`（运行时台账，非协议字段）
- **回写是显式动作**：默认探测仍为只读，避免每次会话污染工作区（副作用闸）
- `ci-smoke` 报告增 `tool_health` 概览；SKILL §6 增健康态降权协议行
- robustness 增 5 例（阶梯 3 档 + 回边 + 只读不改盘）

### R-5 · ci-smoke 步骤 manifest 化 + action-gate resolve（G-4 / E-4）

- 七步清单抽出为 `scripts/data/ci-steps.json`（name / script / args / timeout / **tier** /
  optional / **skip_flag**，`@data/…` 与 `@sdk` 占位符由 runner 展开）；`ci-smoke` 退化为
  **薄 runner** —— 加第 8 步 = 改 JSON 一行，零代码改动
- 清单不可用（缺失 / 空 / 指向不存在的脚本）→ **fail-closed exit 2**（不静默放行）
- `action-gate --resolve`（ResourceOS §10 七动词之 resolve，**纯规划零副作用**）：
  输出 **READY / DEGRADED / BLOCKED** 三态，附带 capabilities、fallback 健康、
  以及该脚本在 ci-smoke 中的位置与前置步骤；READY/DEGRADED exit 0，BLOCKED exit 2
- robustness 增 7 例（resolve 三态 + 未登记阻断 + ci 前置可见 + 清单 fail-closed 两例）

### R-6 · ContextOS 分类预算表（G-5）

- SKILL §7 增五类软上限表（system 固定不裁剪 / task ≤2K / 活动资源 L3 ≤8K / memory ≤2K /
  前序结果 ≤6K）+ **reasoning 硬底线**协议行（输入预算再紧也不得挤占输出推理空间，
  冲突时先砍输入）
- 压缩规则明细下沉 `ref-21 §3.1`（与既有 A/B/C 任务档相乘使用：先定档再按类分配）

### 顺带修复（本轮执行中暴露）

- **`collect_blocking_cases` 正则跨用例贪婪吞匹配**：夹具 JSON 里的 `"script": "…"` 会把
  后面真正的拦截用例吞掉 → probe-tools 被误报「无拦截用例」。已改为**有界匹配**
  （script→expect ≤400 字符），并把夹具 JSON 改为 `json.dumps` 生成
- **夹具函数漏 return 的静默失败**：`_sdk_tree4` 一度插进 `_sdk_tree` 函数体内，使其
  `return root` 成为死代码 → 两条既有 F-43 用例拿到 `--root None`，其中一条**碰巧 exit 2 通过**。
  已加**建表时刻自检**：任何用例参数出现 `None` 直接 SystemExit，不留给 CI 去猜
- `robustness-suite` 的 raw-dict 用例原先强制 `want`/`dont` 键，缺一即 KeyError → 改 `.get()` 兜底
- 新增 `ROBUST_DEBUG_OUT=<file>` 调试出口：把每个用例的组合输出落盘，红灯可直接归因

### 验证

- ci-smoke **7/7 绿**（version-check → selfcheck-static → robustness `pass_rate=1.0`
  （用例数 **187 → 205**（`--quick`）/ **208**（全量），本轮 +18）→ golden v2/v3 validate
  → golden v3 离线 1.0 → privacy-scan `findings=0`）
- `tool_health`: {"active": 37}
- ⚠️ **SKILL.md 38,800B → 39,916B**，距 40KB warn 线仅剩 **84B** ——
  **Epic E（F-61 尺寸闸 + §5.6 流水账下沉）已由"应该做"变成"必须做"**，否则下一批协议行无处安放

## v2.10.7（2026-09-03）

> **ResourceOS 对齐线 P0（R-1）**——第 5 份外部架构规范吸收（`ResourceOS-Architecture.md`，40 节）。
> 裁决：定位为**架构对齐参考**而非待实现蓝图（SDK ≈50 资源 ≪ 其 minimal tier 下限 10³，
> 依其 §34 规模驱动 + §39 反过度工程两条元原则否决设施层）。处置统计：已吸收 12 节 ·
> 部分吸收 16 节 · 新吸收 5 节 · 排除 7 节 · 参考 4 节。本轮为**纯文档轮**（无行为变更）。

### 新增

- `ALIGNMENT.md` 增「ResourceOS-Architecture.md 吸收映射」整节：40 节逐行处置矩阵 +
  G-1..G-8 差距→R-1..R-10 票号对账 + §35 三条权衡表对排除决策的支持附录 + 批次版本表
- `references/25-resourceos.md`（ref-25，指针式，不 vendored）：采纳条款索引 13 条 +
  8 项排除清单 + 与前四份架构吸收的互补关系（前四份=判断与验证纪律，ResourceOS=资源元数据面）
- SKILL.md §9 引用表尾追加 ref-25 行（不做全表重排 —— 重排归清偿包 Epic F，避免同表双改）

### 变更

- R-2（热路径尺寸闸）**不重复立项**：已并入 `sdd-sdk-improve-v2.11` 包 Epic E（= F-61，批次 2 → v2.12.0）。
  本线贡献 = ResourceOS §12.1 规范背书（SKILL.md 目标 500–2K token，实测 ≈12K，超 5–6 倍）+
  验收口径确认（warn >40KB / fail >45KB 维持）

### 裁决与偏离

- **版本号偏离原计划**：计划给 P0 分配 v2.14.0，但 v2.11.0–v2.13.1 已被清偿包预订，
  而 `version-check`（T-16）强制 CHANGELOG 条目严格递减 —— 若本轮跳至 v2.14.0，
  清偿包后续 v2.11.0 条目插到顶部即判失序 exit 2。故 P0 纯文档轮按 §10 规则 8 豁免边界
  只做 patch 递增；**v2.14.0 号段保留给 P1**，待清偿包 v2.13.1 收官后启用
- **P1/P2 顺延**：R-3..R-10 排在清偿包 v2.13.1 之后（避免与 Epic C/D 结构迁移同版本撞 diff）

### 前置清偿

- **F-57（P0，共享 git 仓库历史损坏）已处置**：`git fsck` 盘点出 2 缺失 commit + 1 缺失 blob，
  3 个 ref 遍历中断。以 **`git replace --graft`** 对两处断点做无父化修复（可逆：
  `git replace -d <sha>`），7/7 ref 恢复可遍历，live 线 129→130 commit；`main`（推送血统）
  本就完好且打包枚举通过 —— push 不受阻。残留 1 个 blob（2026-08-21 某历史 SKILL.md 版本）
  本地与 origin 裸库均无，不可恢复，仅影响**全仓** `git rev-list --objects` / `gc`，
  逐 ref 与 push 路径不受影响。详见 `验证报告-SDK-v2.10.7-ResourceOS-P0-2026-09-03.md`

### 验证

- ci-smoke 7/7 绿（version-check → selfcheck-static → robustness pass_rate=1.0 →
  golden v2/v3 validate → golden v3 离线 pass_rate=1.0 → privacy-scan findings=0）
- SKILL.md 38,375B → 38,800B（+425B），仍低于 40KB warn 线；`--sync-size` 已回写三处体积声明

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
