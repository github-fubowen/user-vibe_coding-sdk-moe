# ref-23 — 流水线自动化与门禁（pre-commit gate / ci-smoke / 调度自动化）

> 评估依据：《评估报告-SDK自动化与鲁棒性-2026-08-26》（自动化 L3⁻ → 目标 L4；鲁棒 L4⁻ → 目标 L4.5）
> 落地：P0-1 pre-commit 门禁 · P0-2 §10 协议行 · P1-2 月检自动化 · P2-1 ci-smoke + 周度冒烟 · P2-2 bandit recommend 接线

## 1. 门禁分层（从纪律到结构）

| 层 | 机制 | 触发 | 成本 |
|---|---|---|---|
| **提交门禁（P0-1）** | `.git/hooks/pre-commit` → `git-pre-commit.py` | 每次 git commit | 秒级（robustness `--only` 子集 + 新文件 privacy） |
| 验证闸（既有） | verify-runner 分层 | agent 调用 | 秒-分级 |
| 回归门禁（既有） | golden-run + robustness-suite | 阶段收尾/发布 | 分-级 |
| 发布门禁（既有） | privacy-scan + §10 tier-4 显式确认 | push 前 | 秒级 |
| **定时冒烟（P2-1）** | ci-smoke.py（全量栈） | 周度自动化 | 分-级 |
| **月度巡检（P1-2）** | toolstack-pipeline + ci-smoke | 月度自动化 | 分级 |

## 2. pre-commit 门禁设计（git-pre-commit.py）

- **范围判定**：暂存变更仅含 SDK `scripts/*.py` 时跑 robustness `--only <脚本>`（子集，秒级）；docs-only / 非 SDK 提交**秒过**；
- **新增文件**：暂存区新增 SDK 文件 → privacy-scan 整目录（leak 门禁）；
- **fail-closed**：套件崩溃/超时/失败一律 exit 1 阻断提交；**绝不静默放行**；
- **环境硬化**：子进程前 `pop PYTHONPATH`（沙箱 shim 干扰，E1）；
- **测试入口**：`--dry-run --changed <path>` / `--new <path>` 免 git 直接验证核心逻辑。

## 3. 安装/卸载（install-hooks.py）

```bash
python scripts/install-hooks.py                # 幂等安装（存在同源钩子则跳过）
python scripts/install-hooks.py --remove       # 卸载
python scripts/install-hooks.py --force        # 覆盖外来钩子
python scripts/install-hooks.py --repo /path   # 指定仓库（测试）
```
- 钩子体：`#!/bin/sh` + `exec $PY user-vibe_coding-sdk-moe/scripts/git-pre-commit.py`（python → `py -3` 回退）；
- 钩子文件不入版本库（git 惯例），安装器即可复现路径；**换机器后需重跑安装**（已纳入月检清单）。

## 4. ci-smoke.py（定时冒烟）

单命令跑全量确定性回归栈：**version-check（v2.8.2 T-16，cheapest-first 置第 0 步）→ robustness-suite（全量）→ golden v2/v3 `--validate-set` → golden v3 离线 32/32 → privacy-scan**；`--json` / `--report <path>` 存档，exit 0/2。**零 LLM、离线**，适合无人工定时触发。

> **第 0 步为什么是 version-check（F-26 教训）**：v2.8.1 的 CHANGELOG 条目被手工写在旧条目之后，首个 `## vX` 因此不是最新版 → 五处版本串失配；而 ci-smoke 当时**不含版本串检查**，红灯只能靠 workspace 侧 `audit_sdk.py` 发现（145/146）。把最便宜的闸前置后，顺序倒置/版本失配在 1 秒内失败，不必等 4 分钟全量套件跑完。
> **伴随纪律**：手工改 CHANGELOG 后必须跑 `python scripts/version-check.py`（或等 ci-smoke 第 0 步）；`bump-version.py` 的 layout-repair 插入在 header 已存在时会 `[skip]`，**不会**纠正手工写入的错误顺序。

## 5. 调度自动化（评估报告 P1-2 / P2-1）

- **周度冒烟**（自动化）：`ci-smoke.py --report <存档>` → 持续回归基线；
- **月度巡检**（自动化）：`toolstack-pipeline.py`（probe→diff→report）+ ci-smoke → 工具漂移与金标回归双保险；
- 两者均只读/只报告 + 本地提交，**push 仍需显式确认**（§10 纪律不变）。

### 5.1 门禁 FAIL 处置硬规则（v2.7.1，F-18）

自动化运行中出现任一 step FAIL 时，**只允许两种动作**：

1. **原样上报**：把失败 step 名、exit code、findings 明细逐条写进报告与执行日志，停止后续写操作（不再提交、不再"顺手修"）；
2. **等待人裁**：误报与否由用户判定，自动化**不得自行定性**"良性/可忽略/已知误报"——红灯被自动化解释掉 = 门禁失效的前兆（2026-09-01 实例：privacy findings=2 被月检标注"良性误报"而未修复，根因 F-15 拖了两天）。

判定后如确属误报：修复扫描域/规则（治本），而不是在报告里写一句"误报"（治标）。

## 6. 与既有资产的关系

- robustness-suite：仍是标准门禁与月度基线；pre-commit 用其 `--only` 子集，不重复全量；
- golden-run / privacy-scan：被 ci-smoke 复用（validate/offline/clean 三段）；
- ref-15（toolstack-pipeline）：月检自动化即其"月度一次"的落地触发器；
- 预期收益：回归漏网 → 0（结构强制）；人工复验轮次下降 → 每阶段 token 消耗下降（对应 SDK 目标：少验证循环 = 少 LLM 调用）。

## 7. 已知边界

- 钩子仅在本机安装；他人 clone 后需自行 `install-hooks.py`（无 CI 环境下的等价物）；
- robustness `--only` 子集不覆盖全量（全量留 ci-smoke/月检）；
- 沙箱环境（WorkBuddy）下 python 子进程需 `env -u PYTHONPATH`；钩子内已自动处理。

## 8. bandit 在线学习与月度校准（C2-6，v2.6.0）

- **学习启动（已具备）**：`golden-run --set golden-set-v3.json --model <id> --record scripts/data/router-stats.db`（在线基线 C0-5 已入库 32 样本）；`router-stats.py recommend --cell <cell>` 出 Thompson 建议（SKILL §4 接线）。
- **月度校准协议**：每月巡检（与 toolstack-pipeline 同批）跑 `router-stats.py report --db scripts/data/router-stats.db --json`，核对：
  1. `calibration.mean_abs_error`（n≥5 单元）——误差 >0.1 时调 §4 路由先验；
  2. `escalation_rate`——>30% 说明路由矩阵整体偏弱，回退到静态矩阵默认档；
  3. 基础设施失败（HTTP 503 等）**不计入能力评估**——C0-5 基线中 4/12 失败为 OmniRoute 组合上限，需在 report 中标记 `infra_error: true` 单独统计（避免低估模型能力，P0 报告遗留项）。
- **记录位置**：`scripts/data/baseline-golden-v3-online.json`（在线基线）+ router-stats.db（增量带通带）；月度校准结论写入当月验证报告。
