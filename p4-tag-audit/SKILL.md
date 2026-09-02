---
name: p4-tag-audit
description: P4 终检强制关卡 — 对 AI 绘画工作流输出的 TXT 文件执行 Danbooru 标签合规审计。每个单 token 批量调用 danbooru-tags CLI 校验，违规(not_found)即拒绝交付，并给出场景级违规定位。工作流 P4 输出的 TXT 必须通过本审计才能交付。
agent_created: true
---

# P4 Tag Audit — TXT 强制标签合规审计（v2 严格模式）

## 用途

AI 绘画工作流 (v6.4+) 的 P4 终检关卡。**TXT 必须是 tags-only**——每个 token 都必须是合法 Danbooru 标签，叙事内容只能存在于 MD 的 nltags_block。

## 用法

```bash
python tag_audit.py "<输入 TXT>.txt" [--output "<审计报告>.md"]

# 退出码: 0 = 全部合规 | 1 = 存在违规 | 2 = 环境错误
```

## v2 严格模式判定

| CLI 结果 | 判定 | 处置 |
|----------|------|------|
| exact_tag / exact_alias | ✅ 合规 | 保留（别名自动映射，如 cctv→security_camera） |
| fuzzy / prefix / contains | ❌ 违规 | fuzzy 只是候选，可能命中无关标签（如 `remembering childhood game` → `game_boy_color`）→ 改用标准标签/拆解/移入 nltags |
| not_found | ❌ 违规 | 拆解为多个合法标签，或移入 nltags_block |

**核心规则：多词叙事短语（如 `remembering childhood game find same color winner got candy`）转下划线后不是合法标签 → 判违规。输出必须是 tags 组成的提示词组合。**

## 已知坑（脚本已内置规避）

1. **批查请求不能带 `group` 字段** — 否则报 `unknown group: general`
2. **批查返回的 `results` 是 dict 按 id 索引**（`{"results": {"t0": {...}}}`），不是 list
3. **批查临时文件必须用 Windows 可访问路径**（`%TEMP%`），不能用 Git Bash 虚拟 `/tmp`
4. **token 规范化必须保留已有下划线** — `purple_hair` 不能变成 `purplehair`（否则白名单失配误报）
5. 批查单条 query 结构：`{"id": "t0", "keyword": "xxx", "limit": 3}`（无 group）

## 白名单策略（跳过校验，避免重复查询）

- 画风前缀：masterpiece / best quality / highres / absurdres / newest / year 2025
- 系列：equestria_girls / 1girl / solo
- 角色：fluttershy / twilight_sparkle / rainbow_dash / rarity 等 EQG 全角色 + 仙剑 cos 角色
- 外观：全部发色/瞳色/眼镜/发型标签
- 已验证标签缓存：brick_wall / graffiti / pantyhose / kneeling 等 80+ 个跨批次验证过的标签

## 与工作流集成

P4 输出 TXT 后强制执行：

```bash
python .workbuddy/tag_audit.py "{prefix}_{theme}_{timestamp}.txt" --output "{prefix}_tag-audit.md"
```

退出码 1 = 违规 → TXT 不允许交付，退回 P3 将违规 token 移入 nltags 或替换为 Danbooru 别名。

## 实战战绩（2026-08-01 v2 严格模式回测）

- **发现 Y0 原版 45 个违规**：全部是多词叙事短语混入 TXT（`remembering childhood game...`、`applying foundation with serious focus` 等）
- 重写为纯标签版 + 修复 10 个 fuzzy/未命中 token → **全绿通过 (EXIT=0)**
- 之前 v1 宽松模式只抓到 6 个单 token 违规——**v2 严格模式抓违规能力提升 7 倍**
- 历史修复：N0 `darkroom` → `dark_room`、Q0 移除 `Baigujing`
