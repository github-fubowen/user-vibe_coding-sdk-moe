---
name: workbuddy-sandbox-fs
description: WorkBuddy Windows 沙箱文件系统陷阱与对策。触发场景：在编码会话中安装软件/克隆仓库/写文件到 D: 或 C: 真实磁盘、遇到"文件写进去了却看不到""目录明明空却说非空""git 报路径不存在但 status 正常"等诡异现象。覆盖 Bash overlay 与 PowerShell 真实磁盘双通道、MSYS 路径转换 bug（/d/Software → D:\d\Software）、后台任务差异、以及用 Read 工具做最终验证的方法。
---

# WorkBuddy 沙箱文件系统（Windows）

## 核心结论

WorkBuddy 在 Windows 上存在**双文件系统视图**，写错通道 = 数据丢失/位置错乱：

| 通道 | 写行为 | 读行为 | 适用 |
|------|--------|--------|------|
| Bash（默认沙箱） | 写进沙箱 overlay，**不落真实磁盘**（会话结束即丢） | 先看 overlay，再看真实磁盘（fall-through） | 只读操作 |
| Bash + `dangerouslyDisableSandbox=true` | 写真实磁盘（前台已验证可靠） | 真实磁盘 | 一次性写操作（需用户放行） |
| PowerShell 工具 | **写真实磁盘**（可靠通道） | 真实磁盘 | 安装/写文件首选 |
| Read / Write / Edit / Glob / Grep 工具 | — | 真实磁盘（可靠） | 最终验证用 Read |

**关键诊断法（marker 测试）**：用 PowerShell `Set-Content D:\xxx\__m.tmp` 写标记 → 用 Bash 查。Bash 看不到 = 该 Bash 视图是 overlay；能看到 = 一致。

## MSYS 路径转换 bug（2026-08-18 实测）

该环境 git（Bundled PortableGit）在**非沙箱 Bash** 里把 `/d/Software/pi_agent` 误转为 `D:\d\Software\pi_agent`（把 `/d` 当成 D: 盘根，又保留了 "d" 子目录）：
- 症状：`git clone URL /d/Software/X` 报"成功"，但 `ls /d/Software/X` 是空、仓库实际落在 `D:\d\Software\X`；后续 clone 报"目录非空"；`git -C /d/Software/X status` 却正常（git 用同一错误转换）。
- 对策：**克隆/安装一律走 PowerShell**（`git.exe clone URL D:\Software\X` 用 Windows 风格路径），或先 `mkdir` 目标目录用绝对 Windows 路径。
- 清理误放位置：PowerShell `Move-Item -LiteralPath` 逐个移动（注意通配符 `*` 不匹配隐藏项，`.git` 需单独移）。

## 其他要点

- **PowerShell stdout 可能不被捕获**（只见 exit code）→ 结果写文件再 Read：`Set-Content D:\Temp\out.txt $x`。
- **npm 安装**：用 PowerShell `Start-Process node.exe npm-cli.js ... -RedirectStandardOutput/-RedirectStandardError` 原生运行，避免 PowerShell 流解析把 npm 卡死（`*>` 重定向 + npm.cmd 会退化到极慢）。
- **后台任务行为可能与前台不一致**：验证以 Read 工具（真实磁盘）为准。
- 沙箱注入 `NODE_TLS_REJECT_UNAUTHORIZED=0`，npm 有 TLS 警告属正常。
- **npm/pnpm 安装卡死或 EPERM（2026-08-19 实测）**：先查缓存 `npm config get cache`——若落在 `.workbuddy` symlink 树内（如 `D:\softlink\.workbuddy\binaries\node\...\npm_cache`）会写缓存 EPERM / 无限卡死 → 重定向 `--cache D:\Software\npm-cache` 即解（309 包 2min 装完）。
- 沙箱注入 `NODE_OPTIONS=--use-system-ca`（旧 node <22.15 不认，exit 9）与 `NODE_PATH`（污染模块解析）→ 跑旧版 node 的 npm/pnpm 前先 `$env:NODE_OPTIONS=''; $env:NODE_PATH=''`。

## 标准工作流（安装/写文件）

1. PowerShell 写/装（真实磁盘）→ 2. Read 工具验证 → 3. Bash 只读调用产物。
