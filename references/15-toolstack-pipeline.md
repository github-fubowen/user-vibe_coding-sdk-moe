# ref-15 — 工具栈维护流水线（toolstack-pipeline）

> Load when: 维护/更新本 SDK 的外部工具栈（refs 08-14 + 本地工具链）；"更新工具栈"、"工具栈复核"、
> 定期巡检；需要脚本化 fetch/diff/update/commit/push 的自动化方案。
> Implemented 2026-08-18（v1.0，Python 3.9+ stdlib，零第三方依赖）。

## 1. 流水线阶段（probe → diff → report → update → commit → push-gate）

```
┌──────────┐ ┌───────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐
│ probe    │→│ diff      │→│ report  │→│ update   │→│ commit  │→│ push (gate)  │
│ 本地探针  │ │ 上游核对   │ │ 漂移报告 │ │ 数据/清单 │ │ 本地提交 │ │ 显式确认     │
└──────────┘ └───────────┘ └─────────┘ └──────────┘ └─────────┘ └──────────────┘
   只读         只读          只读        (可选写)     (可选写)     (非 TTY 拒绝)
```

| 阶段 | 命令/动作 | 写操作 | 说明 |
|------|-----------|--------|------|
| probe | 逐条跑 `local_tools` 的 cmd | 无 | 本机工具链版本探针（open-code-review / graphify / code-review-graph / specify / cli-hub / strix） |
| diff | `gh api` 取 head/release/pushed_at/stars | 无 | 与 `toolstack.json` 记录的 pin 对比；**stars 仅作信息展示，不判漂移**（每次查询都变，属噪声） |
| report | 三张表 + Verdict | 无 | 漂移 → exit 2；干净 → exit 0；`--json` 出机器可读报告 |
| update | 刷新 recorded pins + 拉取 vendored 数据 | manifest / PROVENANCE.md | 自动：manifest 同步 head/release/stars/head_date；public-apis 数据 SHA256 漂移时按 raw_url_template 重新下载并更新 PROVENANCE；**cybersecurity-skills（49MB 全量库）只输出手动更新配方，不自动替换** |
| commit | `git add` + `git commit`（Conventional） | git 本地 | 默认消息 `chore(skill-moe): toolstack update (...)`；`--commit-msg` 可覆盖 |
| push | 交互 y/N 门禁 → `git push` | git 远程 | **非 TTY（沙箱）直接拒绝并打印手推命令** —— 遵守 SDK §10 push 显式确认纪律 |

## 2. 用法

```bash
# 报告模式（只读，巡检用；exit 0=干净 / 2=有漂移）
python scripts/toolstack-pipeline.py
python scripts/toolstack-pipeline.py --json        # 机器可读（供自动化消费）

# 更新模式（刷新 manifest pin + vendored 数据）
python scripts/toolstack-pipeline.py --update

# 更新 + 本地提交（推荐日常组合）
python scripts/toolstack-pipeline.py --update --commit

# push 必须在交互终端单独执行（沙箱内会被安全拒绝）
python scripts/toolstack-pipeline.py --push        # 交互终端: y/N 确认
```

**前置**：`gh` CLI 在 PATH（Windows 兜底路径为 `<user-install-dir>/Software/githubCLI/bin/gh`）。gh 缺失时上游核对自动降级跳过，仅做本地探针（G3 静态路由降级原则）。

## 3. 单一事实源：`scripts/toolstack.json`

机器可读清单（脚本读写），与人类可读的 ref md 分工：

| 层 | 文件 | 角色 |
|----|------|------|
| 机器层 | `scripts/toolstack.json` | pin 的**唯一事实源**：repo/branch/check 类型/recorded(head·release·stars·pushed_at)/data(路径·SHA256·raw_url)/vendored 路径 |
| 人类层 | `references/08-14-*.md` | 调研记录、用法、安全审计结论（agent 按需人工同步） |

- 条目类型：`check: head`（只比 HEAD）｜`both`（HEAD + release）｜`data`（附加 SHA256 完整性 + raw 下载模板）｜`vendored`（本地全量目录，只报告不动手）
- 每次 `--update` 都会戳 `last_check` 时间戳 —— 巡检间隔可据此审计。
- **新增工具**：在 manifest 加条目 + 写对应 ref md 即可接入流水线（schema 见文件顶部注释）。

## 4. 已知边界（v1.0）

1. **stars 不判漂移**：只展示。真正的漂移信号 = head / release / pushed_at。
2. **cybersecurity-skills 不自动更新**：49MB 全量库，自动替换风险大；漂移时按 ref-14 §4 配方手动更新（gh api 取 HEAD → 临时 clone → diff -r → 替换 → 提交）。
3. **push 门禁**：脚本只在交互 TTY 接受 `y`；WorkBuddy 沙箱（非 TTY）永远打印手推命令 —— 与 §10 纪律一致，push 决策权始终在用户。
4. **Windows npm shim**：`ocr` 等无扩展名 shim 在 Python subprocess 下需 `.cmd` 回退（已内置）；`cli-hub`/`strix` 缺失属**预期**（指针引用，未本地安装）。
5. **本地提交路径**：`--commit` 只提交 `scripts/` 目录（manifest + 脚本），ref md / SKILL.md 等文档改动仍由 agent 按 §10 手工 commit。

## 5. 与 SDK 其他部分的关系

- **§10 Git 纪律**：commit 默认 / push 显式确认 —— 流水线把这条纪律编码进 `--commit` / `--push` 两个开关。
- **§6 工具路由**：流水线是"维护工具"，不属于任一开发模式工具集；建议每月巡检一次（`--update --commit`）。
- **ref-14 §4**：vendored 库的更新配方已被流水线引用（第 4 节边界 2）。
- **§8 版本漂移**：manifest 的 recorded pin 即 §8 要求的"dated pinning"落地；每月巡检即"version drift monthly re-run"。
