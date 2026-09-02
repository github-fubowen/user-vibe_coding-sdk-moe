---
name: gh-project-investigation
description: Use when investigating an external GitHub repository (evaluate a project, decide code vs release binary, assess features, understand a new open-source tool) or when asked "调研/调查/评估某个 GitHub 项目" with a github.com URL. Also use when deciding whether to clone a repo vs use its releases.
---

# GitHub 外部项目调研

## Overview

以最少工具调用（3-4 次）完成对任意 GitHub 仓库的评估，核心是**先并行抓取、再按需深入**——不轻易 clone 全仓库（大仓库 100-300MB，且占往返时间）。

## 标准流程

### 第 1 步：并行抓取三个数据源（一次消息发 3 个调用）

| 数据源 | URL | 拿到什么 |
|---|---|---|
| README 纯文本 | `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md` | 项目定位、功能、集成方式 |
| 元数据 | `https://api.github.com/repos/<owner>/<repo>` | star/语言/许可/更新时间/默认分支 |
| Release 资产 | `https://api.github.com/repos/<owner>/<repo>/releases?per_page=3` | 是否有 exe/dmg/AppImage 二进制、版本号 |

> 用 raw.githubusercontent.com 的 README 而不是 WebFetch github.com 页面——更快、更省 token、无页面噪音。
> 元数据与 releases 是两条独立 API，与 README 无依赖，必须并行。

### 第 2 步：按需深入（仅当第 1 步不足以判断）

- **要看代码结构**：先 `https://api.github.com/repos/<owner>/<repo>/contents/` 拿目录树（一次调用），**不要直接 clone**
- **要确认核心机制**：才 `git clone --depth 1 --branch <默认分支>`（浅克隆，指定分支）；大仓库放临时目录
- 看具体代码用 GitHub 网页搜索或 grep 克隆目录，别通读文件

### 第 3 步：验证 + 结论

- 若评估"能否用于 X"，至少做一次实测（如启动、跑 --version、查配置），不空谈
- 给出明确结论：是否可用 / 用什么形态（exe vs 源码）/ 风险

## 踩坑备忘（实测验证）

| 坑 | 处理 |
|---|---|
| GitHub API 429 限流（裸 API 调用频繁时） | 降级为 git clone，或等待 Retry-After；不要反复重试 |
| Git Bash 的 `/tmp` 实际映射 | 用 `cygpath -w` 查真实路径（如 `D:\Temp`），Windows 工具要用绝对路径 |
| Git Bash 的 `unzip` 对 `/d/` 路径不可用 | 改用 Windows 原生 `tar -xf` |
| 仓库默认分支不一定是 master | 用元数据的 `default_branch` 字段，clone 时显式 `--branch` |
| Electron/GUI 应用在纯命令行环境拉不起 | 进程列表为空时，不要反复尝试启动；改为评估其配置/数据目录 |

## 决策规则

- **目标只是"用起来"** → 优先 release 二进制（开箱即用、自动更新）
- **目标含二次开发/自托管/审计** → 才用源码；先看 build 复杂度（monorepo？需要 bun/go 编译？）
- **评估"能否复用某资源"** → 直接检查其配置文件/数据目录，比读源码快得多

## Common Mistakes

- ❌ 一上来就 clone 大仓库（282MB 全量浅克隆浪费 30 秒+）
- ❌ WebFetch github.com HTML 页面（应抓 raw README）
- ❌ 元数据、release、README 串行抓（三个独立调用应并行）
- ❌ GUI 应用在无头环境反复尝试启动（进程起不来就转静态评估）
