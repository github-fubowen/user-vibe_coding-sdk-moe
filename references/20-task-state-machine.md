# ref-20 — 任务状态机与黑板协议（coding-agent-os §10-11/§15/§28.3-28.4 吸收）

> 吸收来源：`coding-agent-os-architecture.md` §10 Agent Orchestrator、§11 Blackboard/State Machine（11.1 任务状态机 / 11.2 任务状态 Schema / 11.3 黑板）、§15 Multi-Agent、§28.3 核心数据结构、§28.4 主执行状态机。
> 落地形态：**协议文档**（本节）+ `scripts/task-state.py`（确定性实现，见 §6）。判断纪律在此，执行脚本在彼。

## 1. 核心思想

任务状态**外置**为文件（`.workbuddy/tasks/<task_id>.json`），LLM 永远不需要"记住"软件已知的状态（架构 §10 第一支柱）。状态转移表是**数据**不是提示词；五态终局判定（SDK §5.6）是状态机的进入条件而非叙事。

## 2. 状态集

```
INIT → UNDERSTAND → CLASSIFY → EXPLORE → PLAN → IMPLEMENT → VERIFY → REVIEW → FINALIZE → DONE
VERIFY/REVERIFY 失败 → DIAGNOSE → REPAIR → REVERIFY（再验证）
预算耗尽 / 熔断 / 3+ 矛盾假设 → ESCALATED（L5 人类，一等终态，非崩溃）
不可恢复工具错误 → IMPLEMENT/REPAIR → FAILED
```

| 状态 | 含义 | 进入条件 | 出口 |
|---|---|---|---|
| INIT | 任务登记 | 新任务 | UNDERSTAND |
| UNDERSTAND | 理解需求/最小上下文 | INIT | CLASSIFY |
| CLASSIFY | 定模式/定 tier/定 min_level | UNDERSTAND | EXPLORE、PLAN |
| EXPLORE | 图谱/检索取证（最小必要） | CLASSIFY | PLAN |
| PLAN | 计划（SDD: spec→tickets） | EXPLORE、CLASSIFY | IMPLEMENT |
| IMPLEMENT | 变更（模式内方法） | PLAN | VERIFY |
| VERIFY | 确定性验证（verify-runner） | IMPLEMENT | REVIEW、DIAGNOSE、FAILED |
| DIAGNOSE | 假设-证据-实验环（ref-18） | VERIFY/REVERIFY 失败 | REPAIR |
| REPAIR | 修复/升级阶梯 L0-L5（ref-22） | DIAGNOSE | REVERIFY |
| REVERIFY | 修复后重验 | REPAIR | REVIEW、DIAGNOSE、ESCALATED |
| REVIEW | 审查收尾（标准+spec 双轴） | VERIFY/REVERIFY 通过 | FINALIZE、DIAGNOSE |
| FINALIZE | 交付定型 | REVIEW | DONE |
| DONE | 终态 | FINALIZE | — |
| FAILED | 终态（不可恢复） | VERIFY/IMPLEMENT | — |
| ESCALATED | 终态（L5 人类，一等公民） | REVERIFY 熔断/预算 | — |
| **WAITING**（v2.7.0） | **可恢复暂停**：tier-4 人工批准 / 子代理返回 / 外部门禁 | IMPLEMENT/VERIFY/REVIEW/FINALIZE/REPAIR/CI_QUEUED/MERGE_PENDING/STAGING_DEPLOY/PROD_DEPLOY | 回到来源态（RESUMABLE_STATES）、ESCALATED、FAILED |
| **CRASHED**（v2.7.0） | 会话中断/超时/被杀 | 任意非终态 | REPAIR、DIAGNOSE、WAITING、ESCALATED、FAILED；经 `resume` 从 checkpoint 恢复 |

> **为何要加这两个态**：v2.6.1 及之前 ESCALATED 是唯一"停下来"的方式，而它是**终态** ——
> §10.9 tier-4（push 需人工批准）无法建模为"暂停→批准→继续"，会话崩溃也无处恢复。
> WAITING/CRASHED 均为**非终态**，分别对应"主动等待"与"被动中断"。

### 2.1 checkpoint / resume（v2.7.0）

```json
"checkpoint": {"ts":"...","state":"VERIFY","context_pointer":"sess:turn-42","workspace_ref":"wt/t-001"}
```

- **打点时机**：每次进入 VERIFY / REVIEW / WAITING 自动写入；也可 `checkpoint` 子命令手动写。
- **不在 CRASHED 上打点**：那会用崩溃态覆盖上一个好状态，导致 `resume` 恢复到 CRASHED 自身。
- **恢复**：`task-state.py resume --task <id>`（默认回到 `checkpoint.state`，也可 `--to` 显式指定）；
  只能恢复到 `RESUMABLE_STATES`。无 checkpoint 且无 `--to` → exit 2（不给"假装恢复"的机会）。

### 2.2 三条确定性硬闸（v2.7.0，此前只有协议文本）

| 闸 | 判定 | 拒绝行为 |
|---|---|---|
| 修复预算 `max_repair_attempts=3` | 进入 REPAIR/REPAIRING 时检查 `repair_budget` | 第 4 次 → exit 2；唯一合法出口 `ESCALATED`（DIAGNOSE 已增该出口）。`init --max-repair N`（0=不限） |
| 振荡检测 | 同一 `(from,to)` 转移 > 3 次 | exit 2，并记 `blackboard.facts.loop_guard`；`--allow-loop` 显式放行 |
| DAG 依赖 | `depends_on` 中任一任务非 DONE（或文件缺失） | 禁止进入 IMPLEMENT → exit 2 |

## 3. 与 SDK §5.6 五态映射（判定在 agent，记录在状态机）

| 五态 | 状态机动作 |
|---|---|
| SUCCESS | VERIFY→REVIEW→FINALIZE→DONE |
| PARTIAL_SUCCESS | REVIEW 通过但记 residual（blackboard `residuals[]`），仍 FINALIZE |
| FAILED | → FAILED（或 DIAGNOSE 再试一轮后仍败） |
| REGRESSION | 从 REVIEW/REVERIFY 回 DIAGNOSE，附带 REGRESSION 标记 + 回归修复票 |
| UNKNOWN | 留在 DIAGNOSE 再跑一次实验；**禁止强判** SUCCESS/FAILED |

## 4. task-state.json Schema（任务状态 Schema，§11.2 技能级裁剪）

```json
{
  "schema": "task-state.v1",
  "task_id": "t-20260826-001",
  "title": "修复 verify-runner 分层短路",
  "mode": "Debug",
  "state": "VERIFY",
  "verdict": "SUCCESS",
  "priority": "P1",
  "acceptance_criteria": "分层配置落地且 robustness 全绿",
  "done_when": "robustness 全量 pass_rate=1.0 且 ci-smoke 5/5",
  "done_evidence": null,
  "branch": "fix/verify-runner",
  "workspace": ".workbuddy/workspaces/t-001",
  "depends_on": ["t-20260825-014"],
  "checkpoint": {"ts": "2026-08-26T10:30:00+08:00", "state": "VERIFY",
                 "context_pointer": "sess:turn-42", "workspace_ref": ".workbuddy/workspaces/t-001"},
  "repair_budget": {"max": 3, "used": 1},
  "runs": [],
  "created_at": "2026-08-26T10:00:00+08:00",
  "updated_at": "2026-08-26T10:35:00+08:00",
  "history": [
    {"ts": "...", "from": "IMPLEMENT", "to": "VERIFY", "note": "分层配置落地"}
  ],
  "blackboard": {
    "recent_actions": ["...", "..."],
    "known_failures": [],
    "residuals": [],
    "facts": {}
  }
}
```

## 5. 黑板更新规则（§11.3 吸收，写入脚本不实现）

1. **仅 Orchestrator 写入**：工具/模型结果先经 Orchestrator 转述入黑板，不直接写；
2. **last-validated-write-wins**：同键冲突时，后验证者胜（验证=确定性证据优先于模型陈述）；
3. **`contradicts_evidence` 拒收**：新事实与已验证事实冲突 → 写入被拒并记入 `known_failures`，触发 DIAGNOSE；
4. **recent_actions cap 8**：超阈压缩（Class-A 模型摘要入任务记忆，ref-21 §6 压缩时机）；
5. **known_failures 防重试**：同 error_class + affected_files 复现 → 不重试，直接升级（ref-22 §5）。

## 6. 与脚本接口

`scripts/task-state.py` 负责：init / transition / checkpoint / resume / history / trace-export（含黑板）/ validate。
职责边界：脚本做**合法性、持久化与确定性闸门**（转移表、修复预算、振荡检测、DAG 依赖）；
**状态语义判定（五态、模式选择）仍留在 agent**。

```bash
python scripts/task-state.py --tasks-dir .workbuddy/tasks init --task t-001 \
    --title "修复 X" --priority P1 --max-repair 3 --depends-on t-000 \
    --done-when "robustness 全绿（T-08 完成条件，AgentOS #3）"
python scripts/task-state.py --tasks-dir .workbuddy/tasks transition --task t-001 --to VERIFY \
    --verdict SUCCESS --context-pointer "sess:turn-42"
# FINALIZE→DONE（T-08 闸）：必须附完成证据，否则 exit 2
python scripts/task-state.py --tasks-dir .workbuddy/tasks transition --task t-001 --to DONE \
    --done-evidence "robustness 124/124 + ci-smoke 5/5"
# 事件台账（T-10）：每次 init/transition/resume 追加 <tasks-dir>/events.jsonl
python scripts/task-state.py --tasks-dir .workbuddy/tasks trace-export --task t-001   # 读事件流
python scripts/task-state.py --tasks-dir .workbuddy/tasks resume --task t-001   # 仅 CRASHED
```

事件台账行格式（append-only，survey G4）：`{"ts","event":"transition","task","from","to","verdict","actor"}`——
`--actor` 标注执行者（agent/子代理类名，配合 §7.1 权限矩阵）；ledger 写失败仅告警不阻断（任务 JSON 是主真相源）。

### 6.1 幂等键（v2.10.0，T-26 —— agentic-cicd 原则 9）

**问题**：重试与重放是两回事，但状态机此前分不清。PLAN→IMPLEMENT 已生效后再收到同一条
指令（网络重投 / 子代理重发 / 人类重贴命令），若直接判"非法转移"会报 `illegal` 并**计入
修复预算**——等于把一次网络抖动变成一次失败修复（F-35 实测）。

**闸**：`transition --idempotency-key <k>`

| 情形 | 判据 | 行为 |
|---|---|---|
| 首次应用 | key 未见 | 正常转移，记录 `{k: {to, ts}}` |
| **同键同目标**（真重放） | `seen.to == nxt` | **no-op 返回 0**，不耗修复预算，事件记 `duplicate_ignored` |
| **同键换目标**（调用方 bug） | `seen.to != nxt` | **exit 2** —— 同一把钥匙要求两个去处，是调用方错误，不是重放 |

**顺序**：本闸必须**先于**合法性 / 预算 / 振荡闸。真正的重放发生在 `cur == 已应用目标态` 时
（PLAN→IMPLEMENT 生效后重试，`cur` 已是 IMPLEMENT），此时合法性检查会先报 `illegal` ——
幂等键要在它之前接住。

幂等键与非幂等工具是一对：`action-gate.py` 读 toolstack.json 的 `idempotent` 字段，非幂等
工具的重试**必须**带幂等键（ref-19 §2.7，T-25 的配套约束）。

## 7. 多代理行（§15 吸收，指针式）

- **默认单代理**：一条主链完成任务，避免协调开销（token/延迟双耗）；
- **启用条件（任一）**：T0 架构设计 / Review 双轴（标准+spec）/ L4 共识升级（ref-22）——此时才派生子代理，且子代理只产出证据不写状态机（写权限仅在 Orchestrator）。

### 7.1 子代理权限矩阵模板（v2.8.0 T-11，survey G5 吸收）

派生任何子代理前，先按类填这张表并写进派生 prompt（省一行 = 子代理越界一次）。矩阵是**默认拒绝**制：没写"可写"的就是禁触。

| 子代理类 | 可读 | 可写 | 禁触 | 事件台账 actor |
|---|---|---|---|---|
| **Explore / 检索** | 仓库源码、docs、tasks JSON（只读） | 无（报告回 Orchestrator） | 任何写操作、git 变更、网络 | `explore` |
| **Research / 调研** | 网页、docs、参考文档 | 仅 `output/` 下自己的报告文件 | SDK 源码、scripts/、生产库（router-stats.db） | `research` |
| **Implement / 实现** | 任务指定文件 + 依赖链 | 仅任务 workspace/worktree 内文件（task-workspace.py 隔离） | 其它任务目录、.workbuddy/tasks（写权在 Orchestrator）、git push | `implement` |
| **Review / 审查** | diff、全仓、golden 基线 | 无（结论回主链） | 一切修改类动作 | `review` |
| **Test / 回归** | 全仓、套件脚本 | 仅临时目录 / 测试夹具 | 生产数据（router-stats.db 真库）、SKILL 主文件 | `test` |

硬规则（对所有类生效）：
1. 子代理**不得**调用 `task-state.py transition`（状态机写权仅在 Orchestrator —— §15 原则的脚本化落点）；
2. 子代理产出以**证据**形态回传（文件路径 / 命令输出 / JSON），由 Orchestrator 验证后写入黑板；
3. 子代理触达禁触清单 = 立即终止该子代理并记 `known_failures`（ref-22 §5）。

## 8. 排除项

不落地：多代理常驻框架、分布式状态存储、Redis/DB 持久化（JSON 文件 + git 即存储，对齐 §20 低复杂度部署）。
