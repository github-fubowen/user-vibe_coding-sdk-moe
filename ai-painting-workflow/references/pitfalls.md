# 坑表与预检纪律（pitfalls）— 按需加载

> 本文件由 ai-painting-workflow/SKILL.md §参考文件 按需加载：遇到报错/校验失败/设计纠结时读。

## 1. 完整常见坑表

| 坑 | 处理 |
|---|---|
| TXT 不以质量锚开头 → validate "未找到 prompt 行" | flow 已自动前置 quality；手工文件必须 masterpiece 开头 |
| 中文短语/叙事进 TXT → 违规 | 叙事只进 MD 的 nltags/notes，TXT 全 token |
| fuzzy 标签（如 on_hands_and_knees） | 改用 exact 命中（all_fours）或移入 MD |
| EQG 角色 `xxx_(eqg)` 写法被 normalize 破坏 | 用无括号形式 rarity + equestria_girls |
| 直觉标签不合法（实测: telephone_booth/wet_road 均 not_found） | 新场景标签先 `cn2tags`/`combine` 预检；wet_road→wet+puddle+reflection |
| 想复现随机分配 | 固定 scene_seed，同 seed 结果一致 |
| 注入卡跨块重复（attire 已有 see-through legwear，scene 又注入） | 注入卡每块只要求 1 个 token，且优先选该块"独有"元素；已在他块出现的不要再设注入 |
| 日文标签（D站日文别名） | 先翻译成英文标签再预检：泣きぼくろ→mole under eye、holding unworn shoes→holding_shoes、curtain→curtains |
| forbidden 词混入场景（blush/sitting/smile 等） | flow 已自动剥离（v2.6 修复，MD 记录"禁止词剥离"审计）——不再需要手工删 |

## 2. 权重语法暂停（v2.18，用户指定 2026-08-13）

- `(tag:1.2)` / `(a, b:1.2)` 权重功能**默认关闭**——输出一律纯 tags 平铺（可直接过 validate）。仅当用户明确要求"带权重/模型方言"时才使用。
- 默认身材同理：恢复 IP 库 simple_tags（apple/scootaloo=small breasts、sweetie=medium breasts），不加 curvy/huge breasts。
- 权重语法是**模型方言**——引擎 normalize 会搅成 `tag12` 判非法，不走 validate（与 essay 模式同类）。交付形态 = 手工构建 + 基础词剥离权重逐词过 153K。
- **组合括号校验必须括号感知**：`(a, b:1.2)` 不能按逗号 naive split（会拆坏括号内组合）。用 split_top（追踪括号深度）+ expand（展开组合权重）→ 见 scripts/bracket_check.py。
- 参考文件含大量非法词（wanaata/konoshige 艺术家 lora、huge areaolae 拼写错误、deep penetration 等）——借鉴语法结构，不用其具体露骨内容；SFW 批次替换为合法反套路表情矩阵。

## 3. 预检纪律（v2.12 提速）

根因: 全量在线验证 15 分钟空转（2026-08-08 实测）。详见主文档 v8.3「预检提速」节。

1. **预检只用 `_precheck_spec.py`**（复用 validate 白名单，0.1s/数百词）——替代内嵌脚本与在线验证
2. **flow 0.9s 是唯一权威终检**
3. **在线验证仅限 validate 报违规后的定向复核**（<10 词）
4. **跨批次复用 `runtime/verified_tags.json`**（已 554 词，持续累积）

写 spec 前，所有非已知标签先用 `$WB cn2tags "<词>" --top 3` 或 `combine` 验证存在性。

## 4. Danbooru 在线核验三条 + 缺失词解析器（v3.1，2026-08-17 token 消耗调查实测）

根因: coco-maid 批次仅 3 个 153K 缺失词（anime_style/slight_smile/soft_lighting），核验却花了 ~18 次工具调用（403 死路 ×3 + tag_index 结构探测 ×4 + CLI 复检 ×6 + WebFetch wiki ×4）。教训固化如下：

1. **`tags.json` API 直连必 403**（Cloudflare 拦截）——urllib 直连是死路，别试。可用通道只有两条：
   - CLI: `python3 .workbuddy/promptos/__main__.py danbooru search <tag> --limit 1`（有实帖 = 真实 tag）
   - WebFetch `https://danbooru.donmai.us/wiki_pages/<tag>`（HTML 可达，仅作辅助参考，如"已废弃"标注）
2. **wiki 页缺失 ≠ tag 缺失**——`blush`（330 万帖）无 wiki 页但存在；`soft_lighting` 无 wiki 也无实帖才是判死。**判死唯一依据 = CLI post search 无实帖**。
3. **`tag_index.json` 结构** = `{version,total,category_names,tags:[{n:名,p:帖数,c:类别,w:...}]}`——是 153K 子集，**高频 tag 也可能漏收**（bangs ~2.6M 帖 / slight_smile 均漏）。
4. **缺失词不再手工核验**：`python3 _precheck_spec.py <tags.txt> --resolve [--online]` → `_resolve_missing.py` 一次出替代表（头词精确/头词系/语义系按帖数排序）+ 每词 ≤1 次 CLI 确认；确认存在即打印可粘贴的 `KNOWN_VALID_EXTRA` 补漏行，判死即换替代。禁止连环重试（同一路径不重走两遍）。
