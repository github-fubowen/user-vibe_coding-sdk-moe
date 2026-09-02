# 弹药库（ammo）— 按需加载，勿常驻上下文

> 本文件由 ai-painting-workflow/SKILL.md §参考文件 按需加载。所有标签均经 153K 库实测合法。
> 核心教训: **Grok 用非法词(rim_light/metallic/sequin)靠想象，我们用合法替代(backlighting/leather/glitter)靠实测——数据驱动必赢。**

## 1. 人物设定卡（v2.9，对齐 Grok/Claude 级设计密度）

背景: 用户拿 Grok 生成的 6 个"韩国 popstar"提示词对比，发现我们"数据源更强但不如 Grok"。逐维拆解 Grok 输出结构 = 年龄+身份+妆容+材质+款式+灯光+氛围，但 **Grok 用词大半非法**（metallic/sequin/rim_light/high_slit 全 not_found）——用 153K 库合法替代即可超越。

每场景设计时，除 8-Block 外按此卡填充：

| 维度 | 弹药（已验证合法） | 对应块 |
|------|-------------------|--------|
| 年龄/身份 | mature_female / solo / young | block1_style |
| 妆容层 | eyeliner / mascara / lipstick / red_lips / blush / eyeshadow / makeup / beauty mark | block4_body |
| 发型细节 | silver hair / blonde hair / black hair / bob cut / braid / ponytail / twintails / bangs / wavy hair / straight hair | block4_body |
| 材质层 | silk / satin / lace / leather jacket / fur trim / glitter / studded choker / pearl necklace | block3_attire |
| 款式细节 | crop top / v-neck / off-shoulder / fishnet stockings / stiletto heels / platform boots / knee boots / combat boots / body chain / choker | block3_attire |
| 灯光层 | golden hour / sunset / silhouette / backlighting / spotlight / bokeh / depth of field / lens flare / neon lights / city lights | block2_composition |
| 场景氛围 | cyberpunk / stage / rooftop / balcony / pool / studio / cherry blossoms / graffiti | block7_scene |

## 2. 原子级拆解技术（v2.16，参考文件驱动）

背景: 用户提供"优秀提示词"参考文件（Pony/Illustrious 模型方言，3 示例 66-104 token/场景），精细的根因不是句子长，而是 7 项原子级拆解。套用后 token 密度 25→32-46/场景。

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

## 3. IP 锚点置首（v2.17，用户指定 2026-08-10）

`equestria girls` 等 IP 系列名必须放**角色 tags 最前面**（先于 1girl/角色名）——SD 注意力机制先识别 IP 再画角色，避免冷门角色 OOC。
正确: `equestria girls, 1girl, apple_b100m, ...`；错误: `1girl, apple_b100m, equestria girls, ...`。
适用所有输出形态（手工 tags 语言 / essay / flow spec）。

## 4. 冷门角色强调名（v2.19，用户指定 2026-08-13）

可爱军团三人输出角色 tags 用**双括号强调 leetspeak 名**——`((apple_blo0m))` / `((sweetie_bel1e))` / `((scoota1oo))`（IP 库 `emph_tag` 字段，flow `_ip_std_role` 优先返回）。双括号=SD 强调语法，冷门角色避免 OOC。validate 白名单已补裸形（apple_blo0m/sweetie_bel1e/scoota1oo），normalize 剥括号后仍可过校验。热门角色（fluttershy 等）不受影响。

## 5. 双人 CP 动作弹药（已验证合法）

hug from behind / holding hands / interlocked fingers / lap pillow / cuddling / spooning / headpat / kiss / standing on one leg / one side up / piggyback / sitting on lap / tickling / whispering / playing with hair / swinging legs
