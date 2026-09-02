---
name: ai-painting-workflow
description: Use when user requests an AI painting prompt batch (AI绘画提示词/批量出图), mentions 工作流/走流程/按流程生成, provides Danbooru hot tags (D站热门) or wants anti-AI-fatigue prompts. Also use when user asks to generate EQG/小马国女孩 or IP character prompt batches with quality control. Routes to design layer methodology + flow --spec engine. v3.1 (2026-08-22 重建).
---

# ai-painting-workflow — 全链路提示词生产流水线（v3.1 MoE 优化版）

> **⚠ 版本来源（2026-08-22）**：v3.0 主文件（2026-08-16）因 skills git 仓库对象损坏丢失（blob 230e4625 缺失，不可恢复）。本 v3.1 为**重建版**：8-Block/管线纪律/方法论等主体 100% 取自 2026-08-13 备份（v8.0 时代基线），MoE 层（MoE-2/3/4/5/7/8）按完好保留的 `references/moe-{thinking,routing,cache,eval}.md`（v3.0 原创文件）复原，章节编号与 user-vibe_coding-sdk-moe 对齐。若日后找回 v3.0 原件，以原件为准并回退本版标注。

## Overview

**"搜索为骨，匿名生肉，注入成血"**：设计层（LLM 语义判断，会话内执行）想清楚画什么 → 序列化为 `design_spec.json` 契约 → 引擎层（workbuddy-promptos）自动生成+校验+评分+双文件输出。两层仅通过 JSON 契约耦合。

完整方法论: `D:\WorkBuddy\2026-07-23-18-07-50\ai-painting-workflow.md` (v8.0)。
引擎命令: **REQUIRED SUB-SKILL:** 加载 `workbuddy-promptos`（命令用法/环境坑）。

## When to Use

- 用户要"一批提示词" / "批量出图" / "按工作流走" / "生成提示词"
- 用户给了今日 D 站热门标签清单（如 `feet on table 996 / spread toes 7.1k`），要求组合成提示词
- 用户强调"不要太普通的 AI / 观众疲劳 / 反差感" → 走匿名场景+低热度标签
- 需要 EQG / 小马国女孩 / IP 角色多主角批次 + 严格合规交付
- 不需要时：单条中文需求快速出 → 直接用 `generate` 快路径

---

# MoE 层（v3.0 起接入，对齐 user-vibe_coding-sdk-moe；细节见 references/moe-*.md 渐进披露）

## MoE-2. 语言规则与分阶段思考预算（非协商）

- **⛔ THINK IN ENGLISH**：thinking 一律英文骨架 `[GOAL] → [CONSTRAINTS] → [PLAN] → [EXECUTE] → [VERIFY]`；首 token 必须是 `[`；thinking 内零 CJK（中文标签在思考中用英文形式，如 `twilight_sparkle`）。输出跟随用户语言（默认中文）。
- **分阶段预算表**（绘画域特化，详见 references/moe-thinking.md）：

| 阶段 | Thinking | 预算 | 说明 |
|------|----------|------|------|
| P0 热度筛选 | **OFF** | 0 | `<50k 保留，1M+ 丢弃` 是确定性规则，开思考掉速 |
| P-pre 成瘾卡 | ON | low | CONSTRAINTS→EXECUTE，别在措辞打转 |
| P1a 匿名场景 | **ON** | **high** | 本流水线唯一高预算阶段，给足余量 |
| P1b 角色分配 | OFF | 0 | 随机洗牌是脚本行为；分配后不改场景 |
| 8-Block 填充 | ON | low–medium | **防过度润色**：达标即走 |
| essay 作文 | ON | medium | 四要素（记忆点/灯光/双情绪/镜头）齐了就收笔 |
| 预检/validate/digest | OFF | 0 | 交给脚本，别用模型 |

- Overthinking 检查：think-token >70% 且评分没升 → 砍预算（moe-eval §2）。

## MoE-3. 绘画域 MoE 路由矩阵（详见 references/moe-routing.md）

| Tier | 流水线任务 | 主模型 | 备选 | Thinking | temp |
|------|-----------|--------|------|----------|------|
| **T0** | P1a 匿名场景 · P-pre 成瘾卡 · essay 作文 · 重点 IP 批次设计 | DeepSeek V4 | Qwen3.5-Max, Kimi K2 | ON | 0.5–0.7（创作）/ 0.2（决策） |
| **T1** | 8-Block 补全 · 风格扩展 · 中文需求解析 · 别名映射 · 摘要 | GLM-4.6 | Doubao-1.5-pro, MiniMax M2 | OFF–medium | 0.3 |
| **T2** | 热度筛选 · 去重 · 预筛 · 简单 QA · 分类 | DeepSeek V4-Flash | Qwen3, Doubao light | OFF | 0（筛选）/ 0.7（闲聊） |
| **T3** | 私有数据 / 批量 embedding / 离线 / 免费 | 本地 Qwen3-30B-A3B | 本地 MiniLM | — | — |
| **引擎层** | flow / validate / digest / _precheck_spec.py | 确定性脚本，无模型 | — | — | 权威终检 0.9s |

- **协议差异**：GLM-4.6 用 XML 工具模板（勿强套 JSON schema）；DeepSeek/Qwen/Kimi/Doubao 用 JSON schema —— 差异包在一层适配器。
- **降级**：T0 挂 → T1（thinking 降 medium）；T1 挂 → T2；**引擎层永不降级**（flow 是唯一权威终检）；降级不改 spec 契约。
- **创作禁用 temp 0**（只会复制套路）；T2 严格抽取用 temp 0 + 固定 seed + 固定输入顺序。

## MoE-4. Token 闸门（每批执行）

| 闸门 | 规则（绘画域） |
|------|----------------|
| G1 上下文最小化 | 只加载本批所需：弹药池（<50k 清单）+ 8-Block 纪律 + 核心纪律；不整库加载 |
| G2 渐进披露 | 本 SKILL.md 为入口；`references/moe-*.md` / `workbuddy-promptos` / 方法论文档按需加载 |
| G3 静态工具路由 | flow/validate/precheck 路径固定；探针每会话一次 |
| G4 max_tokens 余量 | T0 创作 max_tokens = thinking + 期望场景输出 × 1.5 |
| G5 稳定前缀 | 系统提示 + 8-Block 纪律 + IP 锚点在前（缓存命中区）；用户输入/搜索词在最后 |
| G6 廉价模型卸载 | 热度筛选/去重 → V4-Flash/本地；高价值创作 → T0 旗舰 |

## MoE-5. 质量闸门

- **输出规范**（任何 LLM 调用 prompt 必带）：直接给结果，禁止开场白/寒暄；思考内容不得出现在输出；TXT 严格 tags-only（validate 权威终检，退出码 1 = 拒交付）。
- **注入卡审计 = grounding**（v3.0 核心）：P0 搜索/用户清单里的关键 token 每维度 ≥1 必须出现在最终 prompt（flow 审计 + 自动补入）；MD 存档含注入审计表。
- **7 维评分**（商业化黄金集，moe-eval §1）：可讨论性/细节密度/反差感/组合性/合规性/多样性/落地效率，全 ≥3 才交付；合规性一票否决。
- **提交前自检**：validate 全绿？注入每维度 ≥1？8-Block 全维度非空？thinking 语言扫描（零 CJK）？

## MoE-7. 上下文装配（稳定前缀）

```text
[系统提示（角色/纪律/思考协议/输出规范）]   ← FIXED，永不变（缓存命中区）
[任务不变指令（8-Block 纪律/注入卡结构/核心纪律五条）] ← FIXED
[弹药池（ammo/低热度清单，按批更新，版本化）] ← 稳定
-----------------------------------------------------------------
[本批用户输入（主题/角色/今日热度清单）]     ← volatile，最后
[本批搜索结果]                              ← volatile，最后
```

- **IP 锚点置首既是质量纪律也是缓存纪律**（v2.17）：`equestria girls` 放角色 tags 最前，固定前置 = 可缓存 + 避免冷门角色 OOC。
- 别在 FIXED 段写日期/批次号；换批只替换 volatile 段。
- **runtime 复用即缓存**：`runtime/verified_tags.json`（554+ 词）跨批次复用，别重复在线校验；预检（快）→ flow（0.9s 权威）→ 在线验证仅限报违规后的定向复核。

## MoE-8. 评估与版本漂移（详见 references/moe-eval.md）

- **黄金集**：20-50 个 CN 优先批次（常规/反差系/足袜控/EQG-IP/essay/多人 CP），7 维评分 + 验收点（validate 全绿 + 注入审计可查）。
- **指标**：通过率（<95% 回查纪律）· 评分均值（<3 设计层纪律没执行）· token 效率 · think 占比（>70% 无收益 = overthinking）· 缓存命中率（<60% = 前缀坏了）· 版本漂移（月度重跑）。
- **25 项回归**：`test_flow_workflow.py`（可复现/随机/多人分配/注入/轮换补入/多样性审计/分块输出/质量锚/端到端）——改 flow/schema/纪律后必跑，不过不落地。
- **版本锁定**：生产用日期版批次号 `design-spec-<theme>-20260816.json`，禁 `latest/new`；交付 `{前缀}_{主题}_{ts}.txt` + `.md`。
- **A/B**：换模型/纪律前冻结黄金集 → 旧配置基准 → 新配置对比；降幅 <2% 可换，>5% 回退。

---

## 核心纪律（不可跳过）

1. **P1a 匿名在前，P1b 角色在后**：先设计 N 个无角色身份的匿名场景，再随机洗牌分配角色。分配后不改场景内容——不协调本身就是反差。
2. **反 AI 疲劳弹药 = 低热度高辨识标签**：优先今日热门清单里 <50k 的（feet on table 996 / spread toes 7.1k / see-through legwear 3.6k / inverted cross 4.5k / extra ears 89k），避开人人都会用的 1M+ 大路货组合。
3. **注入卡强制落位**：P0 搜索/用户清单里的关键 token 每维度 ≥1 必须出现在最终 prompt（flow 会审计并自动补入）。
4. **TXT 必须 tags-only**：每行以质量锚（masterpiece, best quality）开头，全 token 合法（validate normalize 空格→下划线后查 153K 库）。fuzzy 判违规，退出码 1 = 拒交付。
5. **双文件交付**：`.txt`（复制即用）+ `.md`（完整存档：设计层摘要/注入审计/校验表）。

## 快速路径（5 步）

```bash
# 前置: 引擎路径
cd "D:/WorkBuddy/2026-07-23-18-07-50"
WB="python3 .workbuddy/promptos/__main__.py"

# 1. 设计层（会话内执行，产出 spec）
#    P0 搜索/用户热门清单 → P-pre 成瘾卡 → P1a 匿名场景 → P1b 角色池 → 写入 design-spec-*.json
#    参考现有示例: design-spec-pure-desire-dhot.json

# 2. 引擎层一键全流程（组装+校验+评分+双文件）
$WB flow design-spec-<theme>.json --analyze

# 3. 检查 validate 全绿（✅ 全部通过 / rc=0）
# 4. 交付 {前缀}_{主题}_{ts}.txt + .md（命名: A/B/C... 前缀表见工作流文档 P4）
# 5. 可选: digest 拆解入库 → 词频累积反哺下批
```

## spec 契约骨架

```json
{
  "meta": {"prefix": "H", "theme": "xxx", "style": "xxx", "series": "equestria_girls"},
  "quality_anchor": ["masterpiece", "best quality", "highres", "year_2026"],
  "inject_card": {"block1_style": ["innocent"], "block3_attire": ["see-through legwear"]},
  "char_pool": ["fluttershy", "rarity"],
  "scene_seed": 20260803,
  "forbidden": ["blush", "smile"],
  "negative": ["photorealistic, perfect skin"],
  "notes": ["成瘾设计说明"],
  "scenes": [{"id": 1, "desc": "匿名描述", "assign": "", "blocks": {"block1_style": []}}]
}
```

8-Block 顺序: identity→style→composition→attire→body→action→expression→scene→quality。
角色用无括号白名单（`fluttershy` + `equestria_girls`）；`assign` 可指定或留空走随机。

## 多人/双人 CP 场景（v2.5 原生支持）

多人提示词不再需要 workaround——flow spec 的 `assign` 支持多角色，引擎自动注入 count 标签：

```json
"assign": ["twilight sparkle", "starlight glimmer"],   // 双人 CP（或逗号字符串 "a, b"）
"char_pool": ["twilight sparkle", "starlight glimmer"]
```

- 引擎自动: identity 注入全部角色 + 自动补 `2girls`（3 人→`3girls`，4+→`multiple_girls`）；单角色场景不误补
- 旧 workaround（identity 硬编码双角色）仍兼容但可弃用
- IP 模式多角色: `generate ... --ip mlp --char "暮暮,星光熠熠"` —— 俗称别名已收录（暮暮/暮光→twilight_sparkle、星光熠熠/星光→starlight_glimmer、云宝→rainbow_dash、余晖→sunset_shimmer 等）
- cn2tags 多人词: 两个/双人/两人→2girls、三人→3girls、多人/群像→multiple_girls（修复"两个女孩"→2boys 性别噪声）
- 参考 v13: `block1_identity` 是 multi_char_blocks（多角色共存不去重）；`count` 独立字段（2girls/solo）

## 8-Block 全维度设计纪律（v2.5，防止单薄）

**设计层每个场景的 blocks 必须全维度填满，对标引擎输出结构**。评分教训: 上次批次 composition/expression 空缺 → QSv3 组合性仅 7.3。

| 块 | 必填 | 最低丰富度 | 示例 |
|---|---|---|---|
| block1_identity | 留空 | — | flow 自动注入角色+系列 |
| block1_style | ✅ | ≥3 词 | style 锚(innocent/vaporwave) + solo + 画风(glitch/art deco/synthwave/grid) |
| block2_composition | ✅ | ≥1 词 | 镜头/视角: close-up / wide shot / from behind / from side / POV / knee up / cowboy shot / profile / perspective（low angle 不合法） |
| block3_attire | ✅ | ≥4 词 | 主服装 + 1-2 件配饰(choker/hair ribbon/mary janes) + 袜子/鞋（足袜控必含袜） |
| block4_body | ✅ | ≥3 词 | 发型 + 瞳色 + 身材(long legs/midriff/navel/collarbone) + 肤质(pale skin/colored skin/slender) |
| block5_action | ✅ | ≥3 词 | 具名姿势(contrapposto/kneeling/crossed legs) + 手部 + 足部动作(spread toes/soles/foot focus) |
| block6_expression | ✅ | ≥2 词 | 反套路表情: shy/neutral/teasing/seductive smile/closed eyes/looking away/eye contact（避免裸 blush/smile） |
| block7_scene | ✅ | ≥3 词 | 环境 + 氛围灯 + 成瘾细节(reflection/puddle/arcade/jukebox/static) |
| block8_quality | 留空 | — | flow 自动补质量锚 |

**规则:**
1. 每个场景 7 个内容块全部非空（identity/quality 留空给引擎）
2. 每块标签数达标（见上表），禁止整块缺失
3. 动作块必须含至少 1 个足部动作（足袜控主题）或 1 个具名姿势
4. desc 用一句话画面描述（含 1 个叙事缺口），作为 MD 存档标题
5. **写 spec 前全标签预检**（见下方预检脚本），避免 flow 跑完才报违规
6. **跨块去重**: style 块的画风词(synthwave/grid/glitch)勿在 scene 块重复

> **增强：v2.12 预检提速纪律（2026-08-08，根因: 全量在线验证 15 分钟空转）——见 `ai-painting-workflow.md` v8.3「预检提速」节。核心: ①预检只用 `_precheck_spec.py`（复用 validate 白名单，0.1s/数百词）②flow 0.9s 是唯一权威终检 ③在线验证仅限 validate 报违规后的定向复核（<10 词）④跨批次复用 `runtime/verified_tags.json`（已 554 词）。**

**人物设定卡（v2.9，对齐 Grok/Claude 级设计密度）:**
> 背景: 用户拿 Grok 生成的 6 个"韩国 popstar"提示词对比，发现我们的输出"数据源更强但不如 Grok"。逐维拆解 Grok 输出发现其结构 = 年龄+身份+妆容+材质+款式+灯光+氛围，但 **Grok 用词大半非法**（metallic/sequin/rim_light/high_slit 全 not_found）——我们用 153K 库合法替代即可超越。

每场景设计时，除 8-Block 外按"人物设定卡"填充（全部用 153K 库实测合法词）：

| 维度 | 弹药（已验证合法） | 对应块 |
|------|-------------------|--------|
| 年龄/身份 | mature_female / solo / young | block1_style |
| 妆容层 | eyeliner / mascara / lipstick / red_lips / blush / eyeshadow / makeup / beauty mark | block4_body |
| 发型细节 | silver hair / blonde hair / black hair / bob cut / braid / ponytail / twintails / bangs / wavy hair / straight hair | block4_body |
| 材质层 | silk / satin / lace / leather jacket / fur trim / glitter / studded choker / pearl necklace | block3_attire |
| 款式细节 | crop top / v-neck / off-shoulder / fishnet stockings / stiletto heels / platform boots / knee boots / combat boots / body chain / choker | block3_attire |
| 灯光层 | golden hour / sunset / silhouette / backlighting / spotlight / bokeh / depth of field / lens flare / neon lights / city lights | block2_composition |
| 场景氛围 | cyberpunk / stage / rooftop / balcony / pool / studio / cherry blossoms / graffiti | block7_scene |

**关键教训: Grok 用非法词(rim_light/metallic/sequin)靠想象，我们用合法替代(backlighting/leather/glitter)靠实测——数据驱动必赢。**

**原子级拆解技术（v2.16，参考文件驱动，2026-08-10）:**
> 背景: 用户提供"优秀提示词"参考文件（Pony/Illustrious 模型方言，3 示例 66-104 token/场景），研究后发现精细的根因不是句子长，而是 7 项原子级拆解。套用到目标批次后 token 密度 25→32-46/场景。

写"精细"提示词（tags 语言 / 模型方言）时，把每个概念拆成微标签，而非一个大词：

| # | 技术 | 参考示例 | 套用示例（处男杀手） |
|---|------|----------|----------------------|
| 1 | **主题原子化**：一个概念→5-8 微标签 | 奶牛= collar, bell, hairband, animal ears, cow ears, cow horns, ear tag, cow print | 下衣失踪= oversized shirt, long sleeves, loose socks, scrunchie, barefoot, toes |
| 2 | **部位逐个点名**：身材逐部位列 | curvy, huge breasts, huge areolae, puffy nipples, wide hips, thick thighs | toes, barefoot, foot focus, one leg up, knee up, collarbone, bare shoulders |
| 3 | **服饰配件链**：每配件独立成词 | elbow gloves, garter belt, thighhighs, skindentation | off-shoulder dress, satin, lace trim, elbow gloves, choker, pendant |
| 4 | **动作链**：行为拆成支撑细节 | bent over, standing, hand on horizontal pole | yawning, stretching, arms up, lying, on back, hand on chin |
| 5 | **表情链**：情绪→微表情序列 | blush, heart-shaped pupils, raised eyebrows, rolling eyes, ahegao, open mouth | deadpan, blank stare, half-closed eyes, looking at viewer, parted lips |
| 6 | **场景道具枚举**：环境逐件点名 | barn, booth, hut, wooden wall, wooden fence, milk churn | living room, couch, coffee table, mug, strawberry milk, note, lamp, dust |
| 7 | **组合权重 + 触发词** | (from behind, ass focus) / (milking machine, lactation)；masterpiece, best quality, explicit, lazypos, lazynsfw, F4st | (feet on table, spread toes:1.3)；masterpiece, best quality, lazypos, F4st（SFW 去 explicit/lazynsfw） |

**分层顺序模板（参考文件通用）**: **IP 锚点（绝对最前，用户指定 2026-08-10）** → 角色计数 → 角色名 → 其他角色 → 艺术家lora → 画风 → 构图/视角 → 妆容 → 服装配件链 → 身材部位 → 鞋袜 → 动作链 → 表情链 → 场景道具枚举 → 质量锚+模型触发词。

> **IP 锚点置首（v2.17，用户指定 2026-08-10）**: `equestria girls` 等 IP 系列名必须放**角色 tags 最前面**（先于 1girl/角色名）——SD 注意力机制先识别 IP 再画角色，避免冷门角色 OOC。正确: `equestria girls, 1girl, apple_b100m, ...`；错误: `1girl, apple_b100m, equestria girls, ...`。适用所有输出形态（手工 tags 语言 / essay / flow spec）。

> **冷门角色强调名（v2.19，用户指定 2026-08-13）**: 可爱军团三人输出角色 tags 用**双括号强调 leetspeak 名**——`((apple_blo0m))` / `((sweetie_bel1e))` / `((scoota1oo))`（IP 库 `emph_tag` 字段，flow `_ip_std_role` 优先返回）。双括号=SD 强调语法，冷门角色避免 OOC。validate 白名单已补裸形（apple_blo0m/sweetie_bel1e/scoota1oo），normalize 剥括号后仍可过校验。热门角色（fluttershy 等）不受影响。

**关键坑（v2.16）**: 
- **权重语法已暂停（v2.18，用户指定 2026-08-13）**: `(tag:1.2)` / `(a, b:1.2)` 权重功能**默认关闭**——输出一律纯 tags 平铺（可直接过 validate）。仅当用户明确要求"带权重/模型方言"时才使用。默认身材同理：恢复 IP 库 simple_tags（apple/scootaloo=small breasts、sweetie=medium breasts），不加 curvy/huge breasts。
- 权重语法 `(tag:1.2)` 和组合括号 `(a, b:1.2)` 是**模型方言**——引擎 normalize 会搅成 `tag12` 判非法，不走 validate（与 essay 模式同类）。交付形态=手工构建 + 基础词剥离权重逐词过 153K。
- **组合括号校验必须括号感知**：`(a, b:1.2)` 不能按逗号 naive split（会拆坏括号内组合）。用 split_top（追踪括号深度）+ expand（展开组合权重）。
- 参考文件含大量非法词（wanaata/konoshige 艺术家 lora、huge areaolae 拼写错误、deep penetration 等）——借鉴语法结构，不用其具体露骨内容；SFW 批次替换为合法反套路表情矩阵。

**动作多样性纪律（v2.6，防僵硬雷同）:**
1. **注入卡动作维度 = 主题集合（≥4 候选）**，如 `["hug from behind", "holding hands", "interlocked fingers", "lap pillow"]` —— 单元素注入卡会让 flow 在 N 个场景全补同一 token 制造雷同
2. **每场景主动作不重复**：6 场景用 6 个不同主动作（hug from behind / holding hands / lap pillow / cuddling / kiss / piggyback...），flow 补入已自动轮换"最少使用"的
3. **组合叙事**（对齐 v13 动作池 104 项风格）: 每场景动作块 = 主动作 + 手部动作 + 足部细节，如 `["lap pillow", "interlocked fingers", "toes"]`
4. **足部细节轮换**: toes/spread toes/soles/foot focus/one side up/knee up/leg up/swinging legs 交替使用，避免每场景同词
5. flow 输出 MD 自动含「动作多样性审计」表——跨场景重复 ≥ 半数会报警，据此回改 spec

**双人 CP 动作弹药（已验证合法）**: hug from behind / holding hands / interlocked fingers / lap pillow / cuddling / spooning / headpat / kiss / standing on one leg / one side up / piggyback / sitting on lap / tickling / whispering / playing with hair / swinging legs

**v2.10 双层架构（小作文模式，用户定义）**:
- **设计层**（只做极致设计，不越俎代庖）: 写**匿名英文小作文**（自然语言段落，不管标签合法性）+ 指定 IP 角色（assign）——不写标签/不校验/不组装
- **引擎层**（flow --essay）: 接收小作文+IP → 注入角色名+IP 外观(发色/瞳色/肤质，作文自带外貌则跳过)+系列+质量锚 → 输出**专业提示词**（可直接交 SD/MJ/Flux）
- spec 契约: `scenes[].essay`（匿名小作文）+ `scenes[].assign`（IP 角色）→ `flow design-spec.json --essay`
- 超越 Grok 要点: 每段小作文含 ①记忆点(L4 低热度弹药语义化) ②灯光层次 ③双情绪 ④镜头语言——数据源优势直接转化为作文质量
- 示例: `design-spec-popstar-essay-ip.json`（6 段 popstar 小作文+IP）

## 常见坑

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

**预检纪律**：写 spec 前，所有非已知标签先用 `$WB cn2tags "<词>" --top 3` 或 `combine` 验证存在性，避免 flow 跑完才报违规。

**预检脚本**（推荐，一次查 spec 全部标签 + 白名单跳过）:
```python
import os, sys, re, json
os.environ.pop("PYTHONUSERBASE", None); os.environ.pop("PYTHONPATH", None)
sys.path.insert(0, ".workbuddy/promptos")
from core.json_engine import get_json_engine
from commands.validate import STYLE_PREFIX, SERIES_TAGS, CHARACTER_TAGS, APPEARANCE_TAGS, KNOWN_VALID, KNOWN_VALID_EXTRA
eng = get_json_engine()
def norm(t): return re.sub(r"[^a-z0-9\s_\-]", "", t.lower()).replace(" ", "_")
spec = json.load(open("design-spec-X.json", encoding="utf-8"))
all_tags = {t for sc in spec["scenes"] for blk, ts in sc["blocks"].items() for t in ts}
def skip(t):
    n = norm(t)
    return n in STYLE_PREFIX or n in SERIES_TAGS or n in CHARACTER_TAGS or n in APPEARANCE_TAGS or n in KNOWN_VALID or n in KNOWN_VALID_EXTRA or n.endswith("_nl")
miss = [t for t in sorted(all_tags) if not skip(t) and not eng.lookup(norm(t))]
print("缺失:", miss if miss else "无 — 全部合法")
```

**括号感知校验**（tags 语言 / 权重版文件专用，v2.16）:
```python
# 用法: 校验含 (a:1.2) / (a, b:1.2) 权重的模型方言文件
import os, sys, re
os.environ.pop("PYTHONUSERBASE", None); os.environ.pop("PYTHONPATH", None)
sys.path.insert(0, ".workbuddy/promptos")
from core.json_engine import get_json_engine
from commands.validate import (normalize, STYLE_PREFIX, SERIES_TAGS, CHARACTER_TAGS,
                               APPEARANCE_TAGS, KNOWN_VALID, KNOWN_VALID_EXTRA, ALIAS_MAP)
eng = get_json_engine()
def is_ok(tok):
    n = normalize(tok)
    if not n: return False
    if n in STYLE_PREFIX or n in SERIES_TAGS or n in CHARACTER_TAGS or n in APPEARANCE_TAGS or n in KNOWN_VALID or n in KNOWN_VALID_EXTRA: return True
    r = ALIAS_MAP.get(n, n)
    return bool(eng.lookup(n)) or (r != n and eng.lookup(r))
def split_top(ln):  # 括号感知: 顶层逗号切分
    out=[]; buf=''; depth=0
    for ch in ln:
        if ch=='(': depth+=1
        elif ch==')': depth-=1
        if ch==',' and depth==0: out.append(buf.strip()); buf=''
        else: buf+=ch
    if buf.strip(): out.append(buf.strip())
    return out
def expand(tok):  # (a, b:1.2)->[a,b]; (a:1.2)->[a]; 普通->[tok]
    m = re.fullmatch(r'\(([^()]*?):([0-9.]+)\)', tok)
    if m:
        inner = m.group(1)
        return [s.strip() for s in inner.split(',')] if ',' in inner else [inner.strip()]
    return [tok]
seen=set(); miss=[]
for i, ln in enumerate(open("你的文件.txt", encoding="utf-8"), 1):
    if not ln.strip(): continue
    for t in split_top(ln.strip()):
        for base in expand(t):
            n = normalize(base)
            if not n or n in seen: continue
            seen.add(n)
            if not is_ok(base): miss.append((i, n))
print("缺失:", miss if miss else "无 — 全部合法")
```

## 验证

- 回归脚本: `test_flow_workflow.py`（25 项：可复现/随机/多人分配/注入/轮换补入/多样性审计/分块输出/质量锚/端到端）— 改 flow 或 schema 后必跑
- 评分参考: 商业化 7 维 ≥3 才算合格；足袜控/反差系常见 3.4-3.7（可讨论性/细节密度高分）

## References（渐进披露，按需加载）

| 文件 | 内容 | 何时加载 |
|------|------|----------|
| `references/moe-thinking.md` | 绘画域强制英文思维链协议（分阶段预算表 + few-shot 示例） | 设计层动笔前（P1a/P-pre/essay 必读） |
| `references/moe-routing.md` | 绘画域 MoE 路由矩阵全表（T0-T4 + 引擎层 + 协议差异 + 降级规则） | 选模型/调采样/批量分流时 |
| `references/moe-cache.md` | 稳定前缀与缓存策略（会话侧 + flow 侧 + runtime 复用） | 批量会话/排查 token 成本时 |
| `references/moe-eval.md` | 评估闭环（7 维黄金集 + 指标 + 25 项回归 + 版本锁定 + A/B） | 改引擎/换模型/月度复评时 |
