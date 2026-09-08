# ref-27 — Acceptance OS（AOS）验收体系

> **来源**：`SDK_Reference/architecture/coding-agent-os-acceptance-system.md`（AOS v1.0，41 节）
> **定位**：**验收方法论参考**，不是待实现平台（28 子系统中 SDK 只吸收 6 类）
> **何时加载**：需要回答"这一轮全绿能不能算接受""失败该归哪一类""SDK 现在在哪个成熟度等级"时；日常编码不加载
> **对齐计划**：`升级计划-SDK-AOS验收体系对齐-2026-09-07.md`（14 票 A-0..A-14）
> **处置统计**：吸收 19 节 · 已符合 9 节 · 部分吸收 6 节 · 排除 7 节 · 参考 4 节

---

## §1 语义翻译层（先翻译，再对标）

AOS 评测"Agent OS"，SDK 评测"驱动 Agent 的协议 + 脚本"。不翻译直接对标会全盘误判。

| AOS 概念 | SDK 对应物 | 落差 |
|---|---|---|
| `AgentVersion` | `(SDK 版本, model_id, preset, toolstack.hash)` | 未联合登记 → A-5 |
| Task × type × complexity × LOC | golden sample × `cell`(8) × `difficulty`(3) | LOC 分层排除（工作区 <10K） |
| `EnvironmentSnapshot` / 复现契约 | `env-snapshot.py` | 有快照无契约 → A-11 |
| `hidden_tests` | **无**（golden 全公开） | **A-4** |
| Static / Dynamic Oracle | `verify-runner` / `selfcheck-static` / `robustness-suite` | 已达 AOS §40.8 MVI 的一半 |
| Semantic Oracle（judge 集成） | **无，且不引入**（ref-05 §3 结构化判定） | 天然免疫 §40.1-3 judge 漂移 |
| Security Oracle | `privacy-scan` + `action-gate` tier-4 + ref-14/13 | MVI 的另一半 |
| Chaos Engine / RecoveryRate | `robustness-suite` 测**脚本容错** ≠ Agent 恢复 | **概念错位 → A-9** |
| Trace（hash 链） | `events.jsonl` + `trace-export` + `task-state history` | 无 hash 链，D4 裁决不引入 |
| Acceptance Gate / Scoring | `ci-smoke`（布尔合取，无评分） | → A-1 |
| Regression（配对 + 显著性） | `regression-guard` + `golden --baseline`（点估计） | → A-3 |
| Failure Taxonomy / 二分 | `error-sig` + `case-search` + 五态 | → A-6 / A-7 |
| Acceptance Contract | **无** | → A-5 |
| Maturity Model | **无** | → A-12 |
| Self-Evolving Benchmark | **无** | → A-13 |
| Anti-Gaming / golden invariant | `mutation-audit`（仅闸脚本） | → A-8 |

---

## §2 采纳条款索引（票号）

| 票 | AOS 源 | 内容 | 批次 / 版本 |
|---|---|---|---|
| A-0 | — | ALIGNMENT 附录 + ref-27 + SKILL §9 指针 | P0 / v2.11.0 |
| A-1 | §20.3 / §21.3 | **gated 多维评分**（`accept-score.py`）：硬闸布尔优先 → 质量维几何均值 × 4 组权重 → 缺失维照实缺席 + coverage | **P1 / v2.11.1 ✅** |
| A-2 | §35.2 / §20.3 Step4 | **重复试验 + bootstrap CI**（`golden-run --trials N --ci [--profile]`；cluster bootstrap B=2000；欠功效在 binding profile 下 exit 2） | **P1 / v2.11.1 ✅** |
| A-3 | §22.2 / §35.3 | **配对 A/B**（`--compare` 输出 `paired`：配对 Δ 的 bootstrap CI + `significant_regression`） | **P1 / v2.11.1 ✅** |
| A-4 | §10 / §34 | **held-out 金标**（库外 `${SDK_HELD_OUT_ROOT}` + 契约 sha256，缺失/失配 → UNKNOWN + exit 2）+ **`--audit-rules` 诱饵审计**（恒真 accept 规则即 exit 2） | **P2 / v2.11.2 ✅** |
| A-5 | §24 / §4.2 | `data/acceptance-contract.v1.json` + `ci-smoke` 输出 `contract_hash`，失配 exit 2 | **P0（已落地）** |
| A-6 | §25.1 | 13 类失败分类 → SDK 信号映射（下 §3） | P0 |
| A-7 | §25.4 | **`task-state.py bisect`**（谓词外置 `{state}`；非单调时退回线性扫描并标注） | **P2 / v2.11.2 ✅** |
| A-8 | §33 / §34 | **验收栈 canary**（契约失配 → exit 2；植入盘符路径 → privacy 闸拦截）+ mutation-audit 锚点（KILLED） | **P1 / v2.11.1 ✅** |
| A-9 | §11 / §40.6 | **`chaos.py`**（tool_unavailable/timeout/corrupt_state/git_conflict/read_only_fs → RecoveryRate/MTTR/blind_retry） | **P2 / v2.11.2 ✅** |
| A-10 | §12 | **`task-state.py autonomy`**（necessary/avoidable 分解），**report-only**（D3） | **P2 / v2.11.2 ✅** |
| A-11 | §6.2 | **env 复现性契约**（`--hash` / `--repro N` / `--expect-hash`，漂移即 exit 2） | **P1 / v2.11.1 ✅** |
| A-12 | §36 | 成熟度自评（下 §4） | P0 |
| A-13 | §27 | **`case-evolve.py`**（近重复 Jaccard≥0.92 拒收 + 强制 provenance + dwell 7d + 3 次稳定才可晋升） | **P2 / v2.11.2 ✅** |
| A-14 | §15 | **pre-commit 第 5 闸**（SDK 内验收依据文件改动 → 需 `--allow-integrity`，否则拒绝并留痕） | **P2 / v2.11.2 ✅** |

---

## §3 失败分类映射（A-6，AOS §25.1 的 13 类）

分类优先级：**上游优先**——先判 planning/context/retrieval，再判 implementation；否则会把"需求理解错"误记为"代码写错"。

| AOS 类别 | SDK 判定信号 | 证据来源 |
|---|---|---|
| `planning_failure` | 计划未覆盖实际要求；golden accept 全挂且无上游检索问题 | 人工标注（无 hidden_requirements 概念，标"需人工"） |
| `retrieval_failure` | 关键文件从未检索 | ref-21 检索协议未命中 / 图谱查询 0 结果 |
| `context_failure` | 已检索但关键内容被截断 | ref-21 分类预算超限标记 / 长文档未走三级检索 |
| `tool_selection_failure` | 有正确工具却选错 | `probe-tools` 报 degraded 仍硬用 / `action-gate` 未预检 |
| `implementation_failure` | 计划与上下文正确，逻辑错 | `verify-runner` 的 `error_class`（syntax/type/lint/test_failed） |
| `test_failure` | 实现像对，但自检不充分就宣布完成 | `regression-guard` 判 `WEAK_TEST`（base 也 PASS） |
| `debugging_failure` | 发现失败但诊断错/缺失 | 五态 = FAILED 且无假设记录 |
| `recovery_failure` | 诊断对，恢复动作无效或更糟 | `task-state` REPAIR 超预算（>3）或振荡检测命中 |
| `security_failure` | 安全硬闸命中 | `privacy-scan` 命中 / `action-gate` tier-4 触发 |
| `environment_failure` | 环境差异导致，非 agent 过错 | `env-snapshot` 前后差异（版本/依赖/env） |
| `model_failure` | 模型侧错误（拒答/畸形/溢出） | `golden-run` 空响应（`infra_token_threshold`）或 JSON 解析失败 |
| `infrastructure_failure` | 宿主机/网络/工具缺失 | exit 124（超时）/ 126 / 127 |
| `orchestration_failure` | 多代理协调病态（循环/重复） | 振荡检测命中 / 子代理重复产出 |

**落地方式**：`case-search` 的 `taxonomy` 字段扩展为上述 13 值；`error-sig` 归并为 `implementation_failure` 的子类。

---

## §4 成熟度自评（A-12，AOS §36 裁剪到 L1–L2）

L3–L5 依赖多服务 / CI-CD 部署 / 多代理 / 10M-LOC 分层，**SDK 场景不存在，明确排除**。

| 等级 | SDK 替换判据 | 2026-09-07 实测 | 结论 |
|---|---|---|---|
| **L1 Task Agent** | golden 通过率 ≥70% · 工具 active 占比 ≥85% · 工作区无越界写 | golden v3 offline **32/32** · `tool_health.active=39`（0 degraded） · `robustness pass_rate=1.0` · privacy findings=0 | ✅ 达成 |
| **L2 Autonomous** | L1 + **RecoveryRate ≥55% 可测** + **held-out 通过率 ≥70%** + ContextRecall 可观测 | **RecoveryRate 无度量**（A-9 未落地） · **held-out 不存在**（A-4 未落地） | ⚠️ 门不过 |
| L3–L5 | — | 无对应场景 | ⏸️ 排除 |

**目标**：v2.11.2（P2 收官）达成 L2 可证状态。每批次收尾用本表复评。

---

## §5 排除清单

| 排除项 | 理由 |
|---|---|
| gVisor/Firecracker 沙箱池、IAM 分离 | 宿主沙箱已隔离；单机无 IAM 面 |
| ClickHouse/Kafka 事件仓 | stdlib-only；事件量 ~10³/天 |
| LLM-judge 集成与校准流水线 | 结构化判定优先，规避 judge 漂移 |
| 多代理评测（环路/交接保真） | 单代理默认（ref-20） |
| CI/CD 真实部署评测 | 无 staging；`gh-workflow-check` + `ci-fail-analyze` 已覆盖 |
| LOC 分层（100K–10M） | 工作区 <10K，只有单一层 |
| hash-chained trace | D4 裁决：威胁模型不成立 |
| Production profile（n=10 × 1000+ 任务）、FDR 校正 | 规模不匹配；指标数 <20 |

---

## §6 决策锁定（2026-09-07）

- **D1 版本**：本线从 **v2.11.0** 起算（P0 v2.11.0 / P1 v2.11.1 / P2 v2.11.2）。⚠️ 与清偿包 T-501..T-590 原订号段冲突，须确认其顺延至 v2.12.0+。
- **D2 held-out**：库外 `${SDK_HELD_OUT_ROOT}` + 契约内 `manifest_sha256`；**缺失/失配 → `UNKNOWN`，fail-closed**（与 doc 语料线的 fail-soft 降级刻意相反）。
- **D3 AutonomyScore**：**report-only**，不入闸（tier-4 push 门是 §10 规则 2 的结构性人审）。
- **D4 hash 链 trace**：不引入。
- **D5 权重表粒度**：先 4 组（code / bug_fix / review / documentation），A-2 有分布后再细化。

---

## §7 P1 落地纪要（v2.11.1，2026-09-07）

| 票 | 落点 | 关键设计 |
|---|---|---|
| A-1 | `scripts/accept-score.py` + `data/acceptance-weights.v1.json` | 硬闸未过 → `REJECT` 且 `quality_score=None`（绝不用高分买回安全/正确性）；缺失维**照实缺席**并在覆盖维上重新归一化，不用 1.0 假装；`--gate` 才 exit 2（默认 report-only） |
| A-2 | `golden-run --trials/--seed/--ci/--profile` | cluster bootstrap（按样本聚类，避免把多次试验当独立观测）；`variance_flag`（CI 宽 > 0.15）；`--profile staging` 欠功效即 exit 2 |
| A-3 | `golden-run --compare` 的 `paired` | Δ_i = new_ok − old_ok，CI 上界 < −0.02 才算显著回归；**不放松**原"逐样本 REGRESSION"判据（两者回答不同问题：逐样本硬信号 vs 套件级显著性） |
| A-8 | robustness canary ×2 + mutation 锚点 | 坏产物必须被拦：契约失配 / 植入盘符路径；mutation-audit 把契约闸改成恒放行后 canary 变红（KILLED） |
| A-11 | `env-snapshot --hash/--repro/--expect-hash` | 剔除 `time` 后 canonical sha256；`--expect-hash` 让"环境复现性"成为 CI 可断言的硬条件 |

**仍缺的两张 L2 门票**：`RecoveryRate`（A-9）与 `held-out` 隐藏集（A-4）——均在 P2/v2.11.2。

---

## §8 P2 落地纪要（v2.11.2，2026-09-07）

| 票 | 落点 | 关键设计 |
|---|---|---|
| A-4 | `golden-run --held-out auto\|<path>` + `--audit-rules`；`${SDK_HELD_OUT_ROOT}` 库外 | 缺失/hash 失配 → **UNKNOWN + exit 2**（fail-closed，D2）；审计用诱饵响应（空串/反转/通用文本）找**恒真 accept 规则**（F-50 同型）。离线模式只验管道，真实价值在 online 回归 |
| A-7 | `task-state.py bisect --task <id> --check "<cmd {state}>"` | 谓词外置（SDK 无法替调用方判定"从这里还能不能过"）；**非单调时退回线性扫描**并标注 `monotonic=false` |
| A-9 | `scripts/chaos.py`（5 类故障 + `--recover-cmd`） | 恢复由调用方定义；`blind_retry_pattern` 检测默认关闭（只读命令会假阳性） |
| A-10 | `task-state.py autonomy` | necessary（tier-4 push/凭据/不可逆）**不计入扣分**；只观察 avoidable 是否变多；**永不入闸**（D3） |
| A-13 | `scripts/case-evolve.py` | 三道闸：近重复拒收、provenance 强制、dwell 7d + 3 次稳定。**不做 LLM 合成新题**（§40.1-9 质量陷阱） |
| A-14 | `git-pre-commit --allow-integrity` | 只管 **SDK 自己的**验收依据文件（golden 集/契约/权重/步骤清单/闸脚本）；临时目录同名 fixture 不算 |

**L2 成熟度**：A-4 + A-9 落地后两张门票齐备 —— `chaos.py` 实测 RecoveryRate 经 `accept-score --dim reliability=<rate>` 注入，
`held-out` 提供隐藏集证据；coverage 由 2/5 升至 4/5（autonomy 仍 report-only，按 D3 不入分）。
