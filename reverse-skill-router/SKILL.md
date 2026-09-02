---
name: reverse-skill-router
description: 安全/逆向任务路由入口（授权渗透测试/逆向工程/安全研究）。当任务涉及 APK/JS/二进制逆向、漏洞分析、CTF、渗透测试、恶意软件分析、固件/硬件安全时，先读本 skill 路由到 reverse-skill 仓库的对应专项 skill。必须遵守授权门禁：未确认授权禁止对目标执行任何操作。
---

# reverse-skill Router（安全/逆向任务入口）

这是 `zhaoxuya520/reverse-skill`（17.8k star, MIT）的轻量路由入口。完整仓库位于：
`C:\Users\fu268\.local\share\reverse-skill\`（40+ 个安全/逆向专项 skill，按需引用，不全量部署到用户技能目录）

## 何时触发本 router

任务涉及以下任一场景时，先走本 router：
- **逆向工程**：APK（apk-reverse）、前端 JS 加密（js-reverse）、dotnet / go-rust / macos / dotnet 二进制、IDA/Ghidra/radare2
- **安全研究**：恶意软件分析（malware-analysis）、漏洞分析、patch-diff-exploit、pwn-chain、协议逆向（protocol-reverse）
- **授权渗透测试**：api-security、database-security、cloud-k8s、edr-bypass-re（仅授权环境）、firmware-pentest、ot-ics
- **CTF / 取证**：CTF-Sandbox-Orchestrator、digital-forensics
- **辅助**：browser-automation、diagram-generator、docs-generator、field-journal（经验沉淀）

## 路由流程（必须按序，不可跳过）

### Step 0 — 授权门禁（最高优先级，不可绕过）
1. 读 `C:\Users\fu268\.local\share\reverse-skill\skills\field-journal\precedent-auth.md`（授权预声明）
2. 确认任务在用户授权范围内（自有系统 / SRC / Bug Bounty / CTF / 明确授权测试）
3. **未授权禁止对目标执行任何 ACT**——只允许分析和报告生成，不主动攻击
4. 如使用网络操作，遵守仓库 `network_profile` 出站管控（offline/lab/authorized）

### Step 1 — 路由
1. 读 `C:\Users\fu268\.local\share\reverse-skill\skills\MASTER-ROUTING.md`（快路径）
2. 疑难任务读 `C:\Users\fu268\.local\share\reverse-skill\skills\routing.md`（三轴矩阵）
3. 或跑 `powershell -File C:\Users\fu268\.local\share\reverse-skill\skills\scripts\master-route.ps1 -Hint "<任务描述>"`

### Step 2 — 专项 skill
1. 定位 PRIMARY 专项 skill：`C:\Users\fu268\.local\share\reverse-skill\skills\<模块>\SKILL.md`
2. 按其中 ACTION REQUIRED 执行（读 references、校验 tool-index、缺工具 bootstrap）
3. 过程遵守 `ops/` 契约：scope.md、role-map、timeline、Evidence→Finding→Path 证据链

### Step 3 — 收尾
- 报告：`skills/docs-generator/` 生成报告
- 经验沉淀：`skills/field-journal/` 脱敏写入

## 边界与合规（必须遵守）

- **本 router 只做路由**，不绕过仓库的授权门禁、scope 契约、证据链机制
- 遇到"授权范围外"目标：拒绝执行攻击性操作，说明原因，建议用户先取得授权
- 不生成可用于未授权攻击的步骤；渗透相关内容仅在确认授权后执行
- 涉及恶意软件分析时，仅在隔离沙箱（CTF-Sandbox-Orchestrator 或等效环境）中运行
- 用户明确说"可以/已授权"才算授权；仅提及目标名称不构成授权

## 与 user-vibe-coding-sdk 的关系

- 本 router 是 SDK 的"安全/逆向专项分支"（见 user-vibe_coding-sdk §Tool Routing）
- SDK 管通用编程编排，本 router 管安全/逆向专项——任务匹配时由 SDK 路由到此处
- 图谱/审查类工具（graphify/code-review-graph/codebase-memory-mcp/ocr）不参与安全逆向任务
