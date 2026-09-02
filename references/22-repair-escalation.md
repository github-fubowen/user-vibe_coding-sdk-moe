# ref-22 — 修复与升级阶梯协议（coding-agent-os §6.6/§13/§28.8 吸收）

> 吸收来源：`coding-agent-os-architecture.md` §6.4/§6.6 Hierarchical Model Escalation、§13 Repair Engine、§28.8 Failure Recovery Strategy。
> 落地形态：**协议文档**（本节）；与 ref-18（假设-证据-实验环）、SDK §5.6（五态）、§1 Debug/SDD 路径合并为完整修复纪律。

## 1. L0-L5 升级阶梯

| 级 | 执行者 | 重试预算 | 触发条件 | 失败后 |
|---|---|---|---|---|
| L0 | 确定性修复（lint/type/已知签名 error-sig 命中） | 2 | 语法/类型/已知模式类失败 | L1 |
| L1 | Class A 模型（T2 档，带错误上下文） | 2 | L0 不足 | L2 |
| L2 | Class B 模型（T1 档，失败上下文+假设） | 2 | L1 验证失败 | L3 |
| L3 | Class C 模型（T0 档，全上下文+假设） | 1 | L2 验证失败 | L4 |
| L4 | 多模型共识 / 子代理（成本 ×2，非默认） | 1 | L3 验证失败 | L5 |
| L5 | **人类介入（一等终态）** | — | 熔断/预算耗尽/3+ 矛盾假设 | 状态机 ESCALATED |

## 2. 铁律

1. **不可跳级**：唯一例外是 CLASSIFY 阶段显式给定的 `min_level`（如 T0 架构问题直接 L3）；
2. **每级验证闸**：升级前必须过 verify-runner（五态，§5.6）——"修复未验证 = 未修复"；
3. **有界重试**：每级预算耗尽即升下一级，绝不原地无限重试（死路规则：同路径不重试第二次）；
4. **熔断**：同 error_class + affected_files 复现 ≥3 次 → 直接 L5，不再烧 token（§13 防重试循环）；
5. **known_failures 入黑板**（ref-20 §5.4）：失败签名记入 blackboard，本任务内不再尝试。

## 3. 失败类感知（决定停在低阶还是快速升级）

| error_class（verify-runner 诊断） | 处置 |
|---|---|
| `syntax` / `type` / `lint` | 留在 L0-L1（确定性可覆盖） |
| `test_failed` / `logic` | 可升 L2-L3（需假设环） |
| `integration` / `security` | 直接 L3+（跨组件，需全上下文） |
| `infra` / `env` / `timeout` | 不升级模型，先修环境（error-sig 命中优先） |

### 3.1 origin → 动作映射（v2.9.0，T-19 —— verification-kernel §H 落地）

`ci-fail-analyze.py` 的 diagnostic 带 `origin` 字段；**进修复环之前**先按 origin 分流（"一切皆代码缺陷"是反模式）：

| origin | recommended_action | 阶梯含义 |
|---|---|---|
| `code` | REPAIR | 正常进修复环（L0-L3） |
| `test` | REPAIR_TEST | 只修测试/夹具，不碰产品代码 |
| `dependency` | RETRY_THEN_REPAIR | 预算内先重试（registry 抖动），仍挂才 pin 版本修复 |
| `infra` | RETRY | 纯基础设施抖动，只重试不修复（消耗 retry 预算，不消耗 repair 预算） |
| `environment` | FIX_ENV | 补环境（env var / 工具安装），不计入修复预算 |
| `flaky` | QUARANTINE | T-20 判出 → 隔离测试并记追踪项，**永不删除、不触发产品代码修复** |
| `unknown` | DIAGNOSE | 禁止直接进修复环，先补证据（ref-18 §3 假设环） |

**回归测试双向闸（v2.9.0，T-21）**：修复产出的回归测试必须过 `regression-guard.py --base <修复前>`（base FAIL + head PASS）；`WEAK_TEST`/`FIX_INCOMPLETE`/`NOT_A_REGRESSION` 一律 exit 2，修复不算完成（verification-kernel §B.11：两边都过 = 什么都没证明）。

## 4. 补丁隔离与回滚

- 每次 REPAIR 产出独立补丁（git worktree/stash 隔离，§10），**绝不混修**；
- 回滚到最近 known-good 是默认动作之一，不是最后手段（§10.7 rollback recipes）；
- REPAIR 前后各一次 verify-runner，diff 进 trace（task-state.py trace-export）。

## 5. 与 ref-18 的合并关系

- ref-18 = L1-L3 **内部方法论**（假设-证据-实验环、确定性先行清单、问题案例库）；
- 本节 = L0-L5 **外部骨架**（何时升级、何时熔断、何时交人）；
- error-sig/case-search = L0 的确定性先行步骤（命中即跳修复）；
- 三者在 Debug 路径合流：`error-sig 命中 → L0 → 未命中 → ref-18 环（L1-L3 内）→ 验证五态 → 升级/熔断按本节`。

## 6. 排除项

不落地：自动化补丁服务、回滚编排服务（git 即回滚基础设施）、L5 自动代答（人类终态是特性不是缺陷）。

## 7. 修复总预算（C1-5，v2.5.0 — GH 方案 §12 接线）

- **`max_repair_attempts = 3`**：CI 失败（CI_FAILED）后经 REPAIRING 重新入队（CI_QUEUED）的完整修复-重跑次数上限；
- 超过 3 次 → 状态机转 `ESCALATED`（FAILED_AFTER_REPAIR_LIMIT）→ **L5 人类终态**（一等公民，见 §1 表）；
- 记账位置：task-state.py `repair_budget: {max, used}`（v2.7.0 起）+ `runs[]`（attempt 字段）+ `history`。

> **v2.7.0 变更（自查 F-07 收口）**：此前本条明写"超限判定留 agent"——协议写了、脚本不管，
> 等于靠 agent 自觉。现已**脚本化为硬闸**：进入 `REPAIR`/`REPAIRING` 前检查
> `repair_budget`，`used >= max` 直接 exit 2 拒绝转移。为保证不死锁，`DIAGNOSE`
> 已增 `ESCALATED` 出口（它因此成为预算耗尽时唯一合法动作）。
> `init --max-repair N` 可调（0 = 不限）。

## 7.0 补丁规模预算与升级包（v2.10.0，T-23/T-24 —— kernel §I / agentic-cicd §16）

- **patch-gate.py**：修复产出的补丁过规模预算（files≤5 / lines≤300 / 依赖清单≤1，均可调）；超限 exit 2 → 唯一合法出口 `ESCALATED`——拆补丁或升级，不得自动推进。与 diff-risk 分工：评分（建议）vs 预算（硬闸）。
- **repair_confidence**：`diff-risk --verify-confidence <vc>` 合成 `0.5*(1-risk)+0.5*vc`；`<0.7` → `human_review_required=true`（kernel B.21 require_human_review_below_confidence）。
- **escalation-pack**：`task-state.py escalation-pack --task <id>` 生成七字段升级包（problem/evidence/attempted_fixes/failed_tests/relevant_diff<100 行/risk/recommended_action）——**L5 人类终态必附此包**，让人类从完整谱系开始而不是重新推导（G1：不是日志倾倒）。

## 7.1 振荡检测（v2.7.0 新增）

修复预算只防"修太多次"，防不住"在两三个状态间来回横跳"——概率型执行者会以略有差异的
失败变体无限循环（确定性程序要么停机、要么完全重复，LLM 是"近似重复"）。
`task-state.py` 因此增加**确定性循环闸**：同一 `(from,to)` 转移超过 3 次即拒绝（exit 2），
并将 `loop_guard` 写入黑板 `facts`。确需放行时由人显式 `--allow-loop`。
阈值常量：`LOOP_GUARD_THRESHOLD = 3`（脚本内数据，改它即改协议）。

## 8. Diff Risk Scoring（C1-5，v2.5.0 — GH 方案 §13）

合并/回滚前对补丁做风险分层（阈值是协议行，不是 prompt 建议）：

| 分数区间 | 处置 | 执行者 |
|---|---|---|
| `< 0.3` | 自动合并（确定性闸已过） | 流水线 / L0-L1 |
| `0.3 – 0.7` | agent review（ref-19 review-prefilter 关注包） | L2-L3 |
| `> 0.7` | **人工审核**（不自动推进） | L5 人类 |

- 计分输入：diff 规模（行数/文件数）、涉及模块风险权重（scripts/ 高于 docs/）、失败历史命中（known_failures）、error_class；
- 计分是**确定性函数**（脚本化，零 LLM）；`> 0.7` 是硬闸——任何 agent 都不得自行放行；
- 与 §10.9 风险分层并行：两者都过才可自动合并。

> **v2.7.0 变更（自查 F-04 收口）**：本节此前声称"脚本化，零 LLM"，但**仓库里没有任何脚本
> 实现它**——一个被声明为硬闸的规则退化成了 agent 自评自己的补丁，正是它要防的事。
> 现由 `scripts/diff-risk.py` 落地。

```bash
git diff | python scripts/diff-risk.py --stdin --json
python scripts/diff-risk.py --files scripts/a.py,scripts/b.py --lines 600 \
    --known-failures '["scripts/a.py"]' --error-class quality   # → band=human, exit 2
```

评分公式（确定性，权重为脚本内数据）：

```text
score = 0.30*size + 0.30*module + 0.25*history + 0.15*error_class
  size        = 0.7*min(1, lines/300) + 0.3*min(1, files/10)
  module      = 触及路径中的最高风险权重（scripts/ 1.0 > .github/workflows/ 0.9
                > SKILL.md 0.85 > docs/ 0.2；未知路径 0.4）
  history     = 命中 known_failures ? 1.0 : 0.0
  error_class = quality 0.6 / empty 0.3 / infra 0.2 / timeout 0.2 / 未提供 0.4
```

fail-closed：无 diff 输入源（或未给价格/无法解析）时 exit 2，**绝不返回"看起来安全"的 0 分**。
