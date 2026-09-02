---
name: promptos-drift-gate
description: No-LLM Danbooru 提示词生成器(PromptOS)的"漂移标签硬闸门"方法论——定位 matcher_v2/cooc/block_completer 注入的、与用户输入矛盾的属性/性别/风格/节日标签,并在组装末态 + formatter 两层终态裁剪。适用于修复 toned_male/steampunk/happy_valentine 等补全层越界注入。
agent_created: true
---

# PromptOS 漂移标签硬闸门(P0-B)方法论

## 何时用
补全层(matcher_v2 + cooccurrence + block_completer)向最终 prompt 注入了**与用户原始输入矛盾**的属性/性别/风格/节日标签(漂移),而既有终端闸只剔角色/版权、未覆盖属性维度。典型症状:`toned_male` 落在少女查询、`steampunk`/`cyberpunk` 落在治愈/校园基调、`happy_valentine` 无共现。

## 漂移来源溯源
- 漂移标签是 `components/components_db.json` 的 `d-*` 组件(`d-toned_male`/`d-happy_valentine`/`d-steampunk`/`d-cyberpunk`),经 `matcher_v2.DualLineMatcher`(L1/L2) + `cooccurrence.CooccurrenceExpander`(cooc) + `block_completer.BlockCompleter.complete` 注入。
- 既有 `semantic.complete()` 路径**不是**泄漏源——它已用 `_cand_reject` 拦截角色/主题噪声/维度冲突;`_THEME_NOISE` 等词表在那里生效。漂移绕过它,走 matcher/cooc/completer。
- 终态唯一可信闸口 = `pipeline_v13.py` 中 `block_completer` 之后的 `assembly_input`(约 L1266 `sanitize_blocks` 之后),以及 `formatter.py` 的三条发射路径(`finalize` 8-Block / `finalize_flat`→`_flatten` / `flatten_multi` 多角色)。

## 两层闸门落地(均"仅做减法,仅明确矛盾才剥离")
1. **pipeline 层(基于 raw_input + 标签计数 token)** — `semantic.attr_hard_gate(raw_input, tags)`:
   - 性别:女上下文(输入含少女/女孩/妹… **或** 标签含 `1girl`/`*girls` 且无 `*boys`)→ 剥含 `male` 整词标签(`toned_male`/`male`)。男上下文 → 剥 `*female`。
   - 年龄:幼年意图(少女/女孩/loli…)或(女上下文且无成年意图词 成熟/熟女/mature…)→ 剥 `mature_*`。
   - 风格:`_STYLE_CONFLICT`(steampunk/cyberpunk/industrial/glitch_art/mecha/grunge)仅当输入含其触发词才保留。
   - 节日/场景:`_THEME_COOC`(happy_valentine/graveyard…)仅当输入含共现词才保留。
   - 调用点:`pipeline_v13.py` L1266 后 `assembly_input = attr_hard_gate_blocks(raw_input, assembly_input)`。
2. **formatter 层(自包含,无需 raw_input)** — `formatter.formatter_gender_gate(tags, chars=None)`:检测 prompt 内命名角色(从 `ip/*.json` 的 `gender` 字段,经 `semantic._char_gender_map()`),剥相反性别标签。覆盖多角色合并路径与直接 `finalize` 调用。接入 `finalize`/`_flatten`/`flatten_multi`。

## 两个必踩的坑(已修复,记录防复发)
- **消歧后缀归一 bug**:`attr_hard_gate` 用 `t.lower().replace("_"," ")` 推 `base` 做字典键匹配,致 `happy_valentine`→`happy valentine` 不匹配下划线键(仅 `steampunk`/`graveyard` 因无下划线侥幸命中)。**必须用下划线形式(`tl_u = t.lower()`)做 `_STYLE_CONFLICT`/`_THEME_COOC` 键匹配**;空格形式仅用于性别整词 `split()`。
- **ip 路径 bug**:`_char_gender_map` 用 `Path(__file__).parents[1]/ip` → `components/ip`(不存在)。正确是 `parents[2]/ip`(仓库根)。角色性别表为空会让 formatter 闸门完全失效。
- 触发词用子串匹配时务必防误触发:如 `蒸汽` 会误中 `蒸汽波`(vaporwave)→ steampunk 触发词用 `蒸汽朋克`/`发条`/`齿轮` 而非裸 `蒸汽`。

## 验证(双轨,不依赖翻译 daemon)
- 单元:针对四条规则各写 保留/剥离/中性/用户显式 四态用例。
- 真实回归:取既有批量输出 JSON(`one-click_run/output/*.json`,含 `results[].input` 与 `results[].prompt_flat`),对每条 `attr_hard_gate(input, prompt_flat_tokens)` 做 before/after 漂移计数(`validate_gate.DRIFT_TAGS` + `drift_scan`)。全量 109 重跑需翻译 daemon(缺失时 ~50s+/query,用定向验证代替)。
- 全量重跑脚本 `verify_rerun.py` 已就绪(读 meta.ip_inject 核对注入率),待 daemon 可用时跑。

## 保守边界
- 仅明确矛盾才剥离;中性输入(无性别/年龄信号)的 `*_male`/`mature_*` **保留**,避免误删潜在意图。
- 用户显式触发的风格/节日词**保留**(如输入"赛博"→`cyberpunk` 正确保留)。
- 女向非矛盾属性(`muscular_female` 等)不强制剥离,留待"用户优先级"细化规则。
