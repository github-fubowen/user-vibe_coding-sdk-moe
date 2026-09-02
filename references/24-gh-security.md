# ref-24 — 远程执行引擎（GitHub Actions）安全设计

> v2.5.0 · C1-6 · 来源：GH 方案 §2/§3/§16（GitHub-Actions 集成计划 2026-08-28）
> 加载时机：任何涉及远程 CI/部署执行的会话。指针式——本文件是设计契约，不复制 GH 方案正文。

## 1. 认证与令牌层次（优先级从高到低）

| 优先级 | 令牌 | 用途 | 说明 |
|---|---|---|---|
| 1 | **GITHUB_TOKEN**（内置） | 当前仓库内 CI 操作（checkout/artifact/codeql/PR 注释） | 自动注入、仓库级最小权限、过期即失效；**默认首选** |
| 2 | **GitHub App installation token** | 跨仓库/跨组织的受控操作（release 打标签、模板仓下发） | 见 §2 最小权限表；`actions/create-github-app-token` 生成，job 级短时 |
| 3 | PAT | 仅本地 gh CLI 管理（不落入 CI 配置） | **禁止**写入 `.github/workflows` 或 secrets 明文 |
| 4 | OIDC（`permissions: id-token: write`） | 云部署（Azure/AWS/GCP/Cloudflare）免密联邦 | 指针：`cloudflare/wrangler-action`、`azure/login`、`aws-actions/configure-aws-credentials` 官方 OIDC 文档 |

## 2. GitHub App installation token 最小权限表

> 原则：**权限 = 任务所需的最小集合**，一律 `contents: read` 起步；只读操作绝不给写权限。

| 操作类型 | 权限 | contents | pull_requests | issues | actions | 备注 |
|---|---|---|---|---|---|---|
| 纯测试（ci.yml 冒烟） | read-only | read | read | — | read | 默认形态 |
| 发布 artifacts / release | write 仅此步 | write | read | — | read | 用 `permissions:` 块收窄到该 job |
| 跨仓模板下发 | read | read | — | — | read | 目标仓用同 App 另一 installation |
| 部署触发 | 视目标 | — | — | — | — | 优先 OIDC，不用写令牌 |

- 安装级别：**仓库级**（organization 内单仓）优先；organization 级 App 需书面确认范围。
- 轮换：installation token 短时（≤1h）自动过期；App private key 存 secrets，**永不入库**。

## 3. Tool Layer 抽象（Agent 不拼 API）

- Agent 会话中**禁止手写 `curl`/`gh api` 组装远程操作**——一律走既存工具层：
  - 本地：`gh` CLI（§6 Review/SDD 工具链）；
  - CI 内：官方 Actions（`actions/checkout@v4`、`actions/setup-python@v5`、`actions/upload-artifact@v4`）+ reusable workflows（C2-2）；
  - 部署：官方 OIDC action + Environments protection rules（C3-1 可选）。
- 理由：拼 API 是凭据泄漏与越权操作的第一来源；工具层天然带权限边界与审计。

## 4. 拒绝清单（hard rules）

- ❌ 不在 workflow 中硬编码任何令牌/secret 默认值；
- ❌ 不将 PAT 放入 secrets 供 CI 使用（App token / GITHUB_TOKEN 优先）；
- ❌ 不在日志中回显 `${{ secrets.* }}`（GH 已脱敏，但自定义 echo 会绕过）；
- ❌ 不建自托管 runner 接收不可信工作流（run 越权边界不清）；
- ❌ push 门禁不变：CI 配置的推送仍需 §10 显式确认。

## 5. 与本 SDK 的接线

- §6 SDD 工具链：`specify` CLI + reusable workflows 选择行（C2-2）；
- §1 Debug/Review：`ci-fail-analyze.py`（C1-4）诊断 → ref-18 环 → ref-22 阶梯；
- §10 风险分层：CI 配置变更 = tier-2/3（有回滚），push = tier-4（人批）。
