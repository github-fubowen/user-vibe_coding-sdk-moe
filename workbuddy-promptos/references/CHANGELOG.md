# workbuddy-promptos 版本演进 CHANGELOG（v2.1 ~ v2.18 完整归档）

> 由 SKILL.md 重构时从正文迁移（2026-08-13）。当前行为要点见 SKILL.md「当前版本要点」；本文件仅当需要回溯历史设计决策/排障时读取。

## v2.18（2026-08-04 稳定输出收敛）

**去 NL 锚 + 严格查库 + 多人数结构** — ①nl2prompt 输出移除自然语言叙事锚（TXT 纯标签，解决 v13 输出不稳定）②遵循 v13 组装结构: 单人(1girl+solo)/双人(2girls)/三人(3girls)/多人(multiple_girls)，N 人 N 角色层 ③严格 tags 检查: lookup_resource()=153K 库 OR 组件词库 OR IP 资源 OR Pony 质量锚；strict_filter() 映射优先+查库过滤 ④组件词库 assets/data/component_vocab.json: v13 不常见组件入库（coffee shop/window seat/warm indoor/reading room/music room/concert hall/relaxed/studious/passionate 等），资源有依据即可，方便持续入库。

## v2.17（2026-08-04 5 层分层输出）

**nl2prompt 默认输出对齐 Hermes v13 结构（session-20260804）** — `质量锚,, 双人场景层,, 角色1层,, 角色2层,, (NL 叙事锚)`。质量锚 Pony 版(masterpiece/best quality/newest/svslul1zsv3/highres/absurdres)；场景层=2girls,yuri+场景氛围+镜头光效(v13 DSL 组件+作文词)；角色层=变体+系列+1girl+IP外观+服装+动作(奇偶轮换)；NL 锚=作文互动句自动提取。--flat 回单行。素材=v13 dsl_json + nl2tags 8 块 + IP 库；_snake_if_valid 下划线化；外观查库过滤(teal_hair 非法跳过)。

## v2.16（2026-08-04 结构稳定性收敛）

**v13 是"约定式"引擎——结构（7 节点 DSL）定死，但输入必须匹配内置字典，否则 fallback/随机**。①角色 profile key 仅 7 简写（twilight 非 twilight sparkle），传全名 → fallback fluttershy 外观 ②builder._get_theme_bias 内部 themes 只 12 key（缺 library/music/pajama/hanfu），传自由 theme → 空 bias → rng.choice 随机抽场景组件（场景漂移根源）。**修复**: nl2prompt 契约适配层（CHAR_TO_V13 全名→简写、THEME_TO_V13 场景词→16 key、per-scene theme+seed、standardize 兼容 v13 简写名）+ v13 builder 补 4 个 theme bias + nl2tags 词边界匹配（修 "film grain" 内嵌 "rain" 误命中）。效果: 6 场景 theme 全贴合、零漂移、确定性输出。

## v2.15 IP 标准形式（角色变体 + 冒号系列）

**角色变体是角色特异的（153K 库实测）**:
| 角色 | 标准标签 |
|------|---------|
| twilight_sparkle / sunset_shimmer | `_(human)`（`_(equestria_girls)` 不存在） |
| applejack / pinkie_pie / rainbow_dash / rarity / fluttershy / starlight_glimmer | `_(equestria_girls)`（`_(human)` 不存在） |

**系列标准**: `my_little_pony:_equestria_girls`（冒号版权形式，库中存在；裸 `equestria_girls` 不存在，此前靠 validate 白名单放行）。

**自动处理**: flow 角色/系列注入、generate --std-char、nl2prompt standardize_ip_tags 全部自动用 `char_standard_tag()` 选变体——无需手工指定。
**验证**: `flow` identity = `[twilight_sparkle_(human), starlight_glimmer_(equestria_girls), my_little_pony:_equestria_girls, 2girls]`（对照 session 成功案例一致）。

## v2.14（2026-08-04 双人 CP nl2prompt）

--char "a, b" 双角色合并（主角色 v13 生成 + 副角色 IP 外观 + 2girls）+ EN_PHRASE_MAP +70 场景词 + per-scene theme 防场景漂移。

## v2.13 nl2prompt — 作文 → v13 完整提示词（用户方法还原）

```bash
python .workbuddy/promptos/__main__.py nl2prompt essay.txt --char "rarity" --theme "cyberpunk popstar"
python .workbuddy/promptos/__main__.py nl2prompt essays.txt --char "sunset shimmer" --theme "kpop stage"
```
**流程**: 作文 → nl2tags 提取 extra(视觉标签) → v13 PromptEngine.generate(character, theme, extra) → 完整提示词（含 IP 外观 + 引擎自主补全 + 质量锚）。
**为什么这个"完整"**: v13 引擎从 components_db(20K 组件) + IP 库 + TagGraph 生成新组合（作文只给线索，引擎扩展服装/场景/叙事）——对比 nl2tags 的"映射直译"，nl2prompt 是"生成"。
**依赖**: v13 源仓库 D:\Hermes\projects\promptos（PromptEngine）。**实测**: S2 6 段 popstar 作文 + rarity → 51-58 标签/段。

## v2.12 nl2tags 丰富度增强

**nl2tags 输出对齐 v13 精编量级** — ①EN_PHRASE_MAP 扩充 200+ 映射 ②IP 外观注入(--ip --char) ③DetailExpand 细节展开 ④normalize 去重。6 段每段 43-54 标签。

## v2.11 nl2tags — 小作文 → 标签提示词

**流程**: 英文小作文 → EN_PHRASE_MAP 短语匹配(500+ 映射) + 颜色识别 → DetailExpand 细节展开 + IP 外观注入(--char) → normalize 去重 → 8-Block 分类 → 质量锚 → validate --strict 全绿。
**踩坑**: 裸颜色词(black/pink)不是标签 → COLOR_MAP 输出 black_hair/pink_dress；cinematic/medium_shot/hand on hip 非法 → depth of field/close-up/hand on own hip 替代；normalize 去重需"先空格→下划线再过滤"。
**与 --essay 区别**: --essay 输出自然语言（作文原样+IP）；nl2tags 输出**标签提示词**（作文→标签转换，引擎 NL→Tags 功能）。

## v2.10 essay 小作文模式（flow --essay）

```bash
python .workbuddy/promptos/__main__.py flow design-spec.json --essay
```
**流程**（用户定义）: 设计层只写匿名小作文 → 指定 IP 角色 → 引擎注入角色名+IP 外观+系列+质量锚 → 专业提示词。
- essay 模式跳过 validate（自然语言非标签，_validate.md 落说明）
- IP 注入: 角色名 + **外观描述**（IP 库 char_detail_tags 发色/瞳色/肤质 → 自然语言）；**作文已自带 hair/eyes/skin 描述则跳过外观注入**
- 冠词逻辑: 作文以 A/An/Two 开头 → 直接嵌角色名；否则 `A stunning {role}, ...`
- 双人: `Two stunning young women — {a} and {b}, `（assign 传 list）

## v2.7 8 层分块输出（flow 默认）

flow 默认输出 v13 风格分块（--flat 回旧单行）。分块映射: 质量锚头 / 身份(角色+外观+风格) / 身材(body) / 服装(attire) / 动作(action) / 表情(expression) / 场景(scene) / 镜头(composition) / 质量锚尾。
- 多角色场景: 身份层自动含全部角色 + 2girls/3girls count（v2.5）；双质量锚: 头尾各一份
- validate 已兼容多行分块解析（质量锚开头行 + 后续层行合并为场景 tokens）
- 实测: Q 批次 6 场景 38-41 tokens/场景，QSv3 39.5，validate 71 token 全绿

## v2.6 动作多样性

- 雷同根因: 注入卡单元素 + audit_inject 固定补第一个 → 6 场景全补 hug
- 修复1: 轮换补入（usage 跨场景累积，补最少使用的）；修复2: diversity_audit 审计（block5_action 跨场景重复 ≥ max(2, N/2) 报警，注入卡核心 token 豁免）
- 实测: P3 批次动作雷同 4 标签×6次 → 0 主动作重复，QSv3 多样性 6.0→6.4

## v2.5 多人提示词用法

- flow spec: assign 支持多角色（list 或逗号分隔），引擎自动注入 2girls/3girls count 标签
- generate: --char 逗号分隔多角色；IP 模式 --ip mlp --char "暮暮,星光熠熠" 别名自动解析（CHAR_ALIASES_CN: 暮暮→twilight_sparkle / 星光熠熠→starlight_glimmer / 云宝→rainbow_dash 等）
- cn2tags 多人词: 两个/双人/两人 → 2girls；三人 → 3girls；多人/群像 → multiple_girls
- v13 对齐: block1_identity 是 multi_char_blocks（多角色共存不去重）；count 独立字段（2girls/solo）

## v2.4（2026-08-03 低耦合整合）

flow --spec 契约桥（design_spec.json）。

## v2.3 变更（2026-08-03 性能差距调查）

1. **DetailExpand 细节展开层**（core/detail_expand.py）: generate `--detail` 按 DETAIL_MAP（60+ 映射）把稀疏标签展开为细节组（crop_top→midriff/underboob/navel、twin_tails→hair_ribbon/blunt_bangs、thighhighs→frilled_thighhighs/garter_belt、smile→parted_lips/open_mouth 等），值全部经 153K 库验证。
2. **NL 双通道**: validate 白名单跳过 `_nl` 后缀（叙事伪标签合规）；generate `--nl "短语1;短语2"` → 空格转下划线 + `_nl` 后缀入场景块。
3. **角色标准形式**: generate `--std-char` 输出 `fluttershy_(equestria_girls)` + `my_little_pony:_equestria_girls`；validate 已识别 `_(equestria_girls)`/`_(my_little_pony)` 后缀变体。
4. **IP 分类注入**: char_detail_tags 返回 hair_tags/eye_tags/skin_tags 分类 → block4_body 分层注入（发型/面容/肤色）；中文名前缀匹配（"余晖"→"余晖烁烁"）。
5. **质量锚补全**: generate quality 默认 newest/absurdres；HEURISTIC body 扩 30+ 发型/面容词（twintails/blunt_bangs 不再误入 scene）。

## v2.2 变更（2026-08-03 promptos v13 资源审计 P0）

1. **validate --cross-check 真正实现（L4 CLI 交叉校验）**: 调用 danbooru-tags.exe 批查，输出本地 O(1) vs CLI 对照表（exact_tag/exact_alias 才合规）。
2. **IP 宇宙接入（core/ip_loader.py）**: `generate --ip mlp --char "小蝶"` 自动解析角色别名/中文名 → 注入白名单角色名 + 系列标签 + 外观标签（body_tags 过滤仅留库内合法）。4 个 IP 已落地 assets/ip/（my-little-pony 14角色36模板 / genshin-impact / wuthering-waves / senran-kagura），别名: mlp/小马宝莉/genshin/原神/wuwa/鸣潮/senran/闪乱。
3. **generate --pipeline 接入 PipelineV13**: 主流水线从死代码变可用，修复三处：①matcher_v2.match 加 l1_topk=5（L1 每词 Top5，版权噪声 759→15）②HEURISTIC/heuristic_block 迁至 core/block_router.py（digest/pipeline 共享；unassigned 兜底路由率 3.5%→~100%）③Denoiser/Safety 插件默认关闭（拆平重拼破坏 8-Block + 关键词误杀；合规由 validate --strict 兜底）。
4. **validate parse_txt 兼容 score_9_up 开头**（Pony 质量锚行）。

## v2.1 变更（2026-08-03 工作流审查修复）

1. **全量库默认接入**: json_engine 默认加载 153K 全量（内存建 name_index ~0.12s），不再用 42K mini 子集。此前 biting_lip/crossed_legs/wink/seductive/milf 等真实合法标签被误判违规 → 现在直接命中或经 KNOWN_VALID_EXTRA 白名单合规。
2. **中文分词词级贪心**: split_zh_en 改为单字退化（原 4 字片段会吞子词）。"黑丝吊带高跟鞋" → 黑丝/吊带/高跟鞋全切出。
3. **CN_PATCH 词库补漏**（cn2tags.py 内 10 词）: 黑丝→black_pantyhose、撩拨→teasing、纯欲→innocent+seductive_smile、少妇→mature_female、清纯→innocent、竖纹→striped、肉丝→nude_stockings、小马国→my_little_pony、小马国女孩→equestria_girls 等。
4. **8-Block 路由扩充**（digest.py HEURISTIC +100 标签）: fishnets/high_heels/teasing 等不再全落 block7_scene，正确归位 attire/action/expression/quality。
5. **generate 打印错位修复**: 控制台块名与实际 8-Block 一致。
6. **creative --validate 修复**: 输出加 masterpiece 前缀（可被 parse）+ 降级非 strict（叙事短语仅提示不阻断）。种子池叙事短语需人工标签化后 strict 复验。
7. **validate 白名单对齐**: STYLE_PREFIX 补 very_awa/score_9_up/sensitive（与 assembler 质量锚一致）+ KNOWN_VALID_EXTRA 补漏 10+ 标签。
8. **EQG 角色写法**: 用无括号白名单形式 `rarity`/`sunset_shimmer`/`twilight_sparkle` + `equestria_girls`；库里真实形式为 `rarity_(my_little_pony)`，`xxx_(eqg)` 写法会被 normalize 破坏判违规。
