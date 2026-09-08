# GPT-Github_Action集成方案 · 摘要卡
- id: d-gpt-github-action · type: guide · bytes: 40,028 · sections: 26 · tokens: ~4,681
- source: guide/GPT-Github_Action集成方案.md · sha256: 9e8760fd2f7f2910 · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
GitHub 自己目前也明确建议：对于确定性的、重复性的任务，可以把逻辑封装进 reusable workflows，而 Agentic workflow 更适合做需要上下文判断的任务。

## 高频术语（自动统计 Top-8 · 未校对）
`github`×195 · `text`×84 · `agent`×81 · `actions`×71 · `workflow`×42 · `app`×38 · `docs`×37 · `rightarrow`×26

## 一句话
GitHub Actions 上的 Agent CI 控制面指南（25 节，本对姊妹篇的主篇）：GitHub App 最小权限、workflow_dispatch 控制面、webhook 反向神经、Failure Analyzer 与 Run State Machine。

## 章节地图（TOC 压缩，标 ★核心节）
- §一、推荐的总体架构
- §二、不要让 Agent 直接拥有生产级 GitHub Token
- §三、GitHub App 权限建议
- §四、Agent 应该拥有哪些 GitHub Tool
- §五、GitHub Actions 启动机制
- §六、推荐使用 `workflow\_dispatch` 做 Agent 控制面
- §七、非常重要：让 Agent 使用 Reusable Workflow
- §八、这样 Agent 就能形成真正的软件生产闭环
- §九、Webhook 是整个系统的反向神经系统
- §十、Webhook Receiver 推荐独立出来
- §十一、Agent 最应该做的是“Failure Analyzer”
- §十二、必须建立 Run State Machine
- §十三、不要允许 Agent 无限修 bug
- §十四、Production CD 不应该由 Agent 直接“点击按钮”
- §十五、进一步可以做 Agent 自己的 Deployment Gate
- §十六、生产部署应该使用 OIDC，而不是长期云密钥
- §十七、Runner 应该分级
- §十八、并发控制也必须交给 GitHub Actions
- §十九、Agent CI/CD 控制平面的推荐技术栈
- §二十、为什么我特别推荐 Temporal
- §二十一、安全边界一定要这样划分
- §二十二、尤其要防 GitHub Actions Injection
- §二十三、推荐的 Repository 模板
- §二十四、最终应该形成“软件生产操作系统”

## 关键条款（≤8 条，每条 ≤2 行）
- §2-4 不要让 Agent 直接持有生产级 GitHub Token：GitHub App installation + 最小权限 + 抽象 Tool Layer。
- §6-7 workflow_dispatch 做 Agent 控制面 + reusable workflows：每次执行可串联日志/PR/run。
- §9-10 Webhook=反向神经系统：Receiver 独立部署、验签、只订阅必要事件。
- §11-12 Agent 最该做 Failure Analyzer；Run State Machine 不靠自然语言记状态。
- §13-15 修复预算 + Environments 部署保护规则：不允许无限修 bug、CD 不由 Agent 直点按钮。
- §16-18 OIDC 短时凭据 + ephemeral runners + concurrency groups。
- §22 防 GitHub Actions Injection：Agent 生成内容注入 workflow 的风险面。
- §25 分面定义：Actions=Execution Plane、Agent=Decision Plane、Temporal/DB=State & Orchestration。

## 与 SDK 的关系
- 已吸收：未吸收——外部实操指南；核心控制面思想已由 ref-24（v2.9.0）吸收，本文留作云侧 CI 落地时的施工参考
- 已排除：—
- 未决：与 d-gpt-github-action-cicd 章节同构（姊妹篇，D-05 按 tags 互斥共存）；引用优先本篇

## 引用约定
注入时打 `<source doc="d-gpt-github-action" section="§x.y">`；引用必须可回查到本节。
