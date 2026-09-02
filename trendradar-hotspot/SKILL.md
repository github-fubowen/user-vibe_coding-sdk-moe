---
name: trendradar-hotspot
description: TrendRadar 多平台热点聚合 — 监控 11 个中文平台（微博/知乎/B站/抖音/贴吧/头条等）的热搜/热门内容，支持 AI 绘画关键词过滤、AI 趋势分析、跨平台对比。用于 AI 绘画工作流 P0a 趋势搜索层，替代传统 WebSearch 泛化词搜索，直接获取正在传播的真实 prompt 和风格词。
agent_created: true
---

# TrendRadar 热点聚合 Skill

## 概述

TrendRadar 是 24K star 的多平台热点聚合工具（[GitHub](https://github.com/sansan0/TrendRadar)），覆盖微博、知乎、B站、抖音、贴吧、头条、百度、澎湃、华尔街见闻、财联社、凤凰网等 11 个平台。

本 Skill 将其配置为 **AI 绘画趋势监测器**，通过关键词过滤抓取各平台正在传播的 AI 绘画相关热点内容，提炼为可用 prompt 元素。

## 快速使用

```bash
# 引擎路径
ENGINE="D:/WorkBuddy/2026-07-23-18-07-50/.workbuddy/trendradar"

# 安装依赖（首次）
cd "$ENGINE" && uv pip install -e ".[all]"

# 运行一次采集
cd "$ENGINE" && python -m trendradar

# 查看调度状态
cd "$ENGINE" && python -m trendradar --show-schedule

# 环境体检
cd "$ENGINE" && python -m trendradar --doctor
```

## 核心配置

### AI 绘画关键词过滤 `config/frequency_words.txt`

文件：`C:\Users\fu268\.workbuddy\skills\trendradar-hotspot\config\frequency_words.txt`

将此文件复制替换引擎的 `config/frequency_words.txt`。

**语法说明：**

| 语法 | 含义 | 示例 |
|------|------|------|
| `关键词` | 包含即匹配 | `AI绘画` |
| `+词A +词B` | 多词同时出现 | `+丝足 +纯欲` |
| `!词` | 排除 | `!广告` |
| `[组名]` | 给一组词命名 | `[丝足专题]` |
| `/正则/` | 正则匹配 | `/厚涂|impasto|厚塗り/` |
| `=> 别名` | 推送显示名 | `/厚涂|impasto/ => 厚涂风格` |
| `@5` | 限制该组最多 5 条 | `@5` |

### AI 分析配置

```yaml
# config/config.yaml 中的 ai: 部分
ai:
  model: "deepseek/deepseek-v4-flash"
  api_key: "${AI_API_KEY}"
  api_base: ""

ai_analysis:
  enabled: true
  language: "Chinese"
  mode: "current"
  max_news_for_analysis: 150
  include_standalone: true
```

### 报告模式

| 模式 | 说明 |
|------|------|
| `daily` | 当日汇总（含重复） |
| `current` | 当前在榜快照 |
| `incremental` | 仅推送新增，零重复 |

## 工作流集成

在工作流 P0a 层调用：

```
P0a-L1 TrendRadar:
  1. 确保引擎已运行过（已有 SQLite 数据）
  2. 读取 output/news/YYYY-MM-DD.db 的热点数据
  3. 提取匹配关键词的新闻标题/摘要
  4. 提炼其中的 prompt 相关词汇
  5. 注入 P1 灵感词库
```

## 通知渠道（可选）

支持推送：企业微信、飞书、钉钉、Telegram、邮件、ntfy、Bark、Slack、Webhook。

配置 `config/config.yaml` 中的 `notification:` 部分。

## 调度

GitHub Actions / Docker / cron 三种方式。本地开发建议：

```bash
# 每天早晚各跑一次
0 9,21 * * * cd /path/to/trendradar && python -m trendradar
```

## 输出产物

| 产物 | 位置 | 用途 |
|------|------|------|
| SQLite 数据库 | `output/news/YYYY-MM-DD.db` | 结构化原始数据 |
| HTML 报告 | `index.html` | 可视化浏览 |
| MCP API | `python -m trendradar-mcp` | AI 客户端接入 |

## 许可证

GPL-3.0
