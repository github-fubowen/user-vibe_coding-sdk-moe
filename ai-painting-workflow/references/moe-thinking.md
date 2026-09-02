# moe-thinking — 绘画域强制英文思维链协议（深化）

> **何时加载**: 设计层动笔前（P1a 匿名场景 / P-pre 成瘾卡 / essay 作文阶段**必读**）；thinking 出现中文漏出或 overthinking 时回查本节。
> **一句话**: 思考是英文骨架填充（GOAL→CONSTRAINTS→PLAN→EXECUTE→VERIFY），不是中文日记；输出才跟随用户语言。

---

## 1. 总纲 — 思考是骨架填充，不是自由联想

- 任何非平凡设计决策前，按骨架填，不写散文。
- **ZERO CJK in thinking**: 中文标签名在思考中一律用英文形式（如「暮暮」思考里是 `twilight_sparkle`，不是拼音/中文）。
- **首 token 必须是 `[`**（`[GOAL]`）。中文开场 = 立即重开。
- **死胡同规则**: 同一条路不重试两遍；换策略并说明为什么。

## 2. 分阶段骨架模板表

| 阶段 | Thinking | 骨架侧重 | 说明 |
|---|---|---|---|
| P0 热度筛选 | **OFF** | 不思考，直接按阈值 | `<50k 保留，1M+ 丢弃` 是确定性规则，开思考反而掉速 |
| P-pre 成瘾卡 | ON (low) | CONSTRAINTS→EXECUTE | 定反差轴 + 挑弹药，别在措辞上打转 |
| P1a 匿名场景 | **ON (high)** | GOAL→CONSTRAINTS→PLAN→EXECUTE→VERIFY 全链 | 本流水线**唯一高预算阶段**，给足余量 |
| P1b 角色分配 | OFF | 随机洗牌是脚本行为 | 分配后不改场景——不协调即反差 |
| 8-Block 填充 | ON (low–medium) | CONSTRAINTS→EXECUTE | **防过度润色**: 达标即走，不追求"最优措辞" |
| essay 作文 | ON (medium) | PLAN→EXECUTE | 四要素（记忆点/灯光/双情绪/镜头）齐了就收笔 |
| 预检/validate/digest | OFF | 脚本 | 0.1s/数百词 交给脚本，别用模型 |

## 3. Few-shot 绘画域示例（结构示范）

### 3.1 P-pre 成瘾卡（ON, low）— 反差决策

```
User: 主题"反差系"，要反 AI 疲劳
Think:
[GOAL] Pick contrast axes + low-heat ammo for this batch.
[CONSTRAINTS] Ammo must be <50k heat from today's list; axes must clash
             (innocent x gritty, cute x macabre); no 1M+ generic tags.
[EXECUTE] Axes: innocent x arcade-grime; soft pastel x concrete bunker;
         school idol x back-alley jukebox. Ammo: see-through legwear (3.6k),
         inverted cross (4.5k), feet on table (996).
[VERIFY] All <50k ✓, axes clash ✓, no cliché blush/smile ✓. Ship.
```

### 3.2 P1a 匿名场景（ON, high）— 全链

```
User: 6 个匿名场景，反差系，足袜控
Think:
[GOAL] 6 anonymous scenes, contrast-driven, foot-focused, each with 1 gap.
[CONSTRAINTS] No identity in desc; ≥1 sub-50k ammo per scene; foot token in
             every action block; 6 DISTINCT main actions; desc ≤1 sentence.
[PLAN] 1) map 6 contrast axes 2) rotate foot details (toes/spread toes/soles/
       foot focus/one side up/feet on table) 3) give each scene a gap.
[EXECUTE] S1 innocent x arcade: feet on table, see-through legwear, looking
          away — gap: who does she wait for?  S2 pastel x bunker: kneeling,
          soles up, static TV light — gap: why is the bunker furnished like a
          bedroom?  ... (S3-S6 same discipline)
[VERIFY] 6 scenes ✓ anonymous ✓ 6 distinct actions ✓ foot in every action ✓
         ammo ≥1 each ✓ exactly 1 gap each ✓ → S4 had two gaps, merged. Ship.
```

### 3.3 8-Block 填充（ON, low）— 防过润

```
[GOAL] Fill block7_scene for S3, ≥3 tokens.
[CONSTRAINTS] No style-word duplication (synthwave/grid already in block1);
             must support the scene's mood (quiet dread).
[EXECUTE] flooded parking lot + flickering neon + reflection on water.
[VERIFY] ≥3 ✓ no dup with block1 ✓ mood matches ✓. Move on — do NOT polish.
```

### 3.4 essay 作文（ON, medium）— 四要素齐就收笔

```
User: 6 篇匿名小作文，popstar 主题，IP 角色后注入
Think:
[GOAL] 6 anonymous essays; each: ①memory point (low-heat ammo semanticized)
       ②lighting layers ③dual emotions ④camera language. No tags, no legality.
[EXECUTE] E1: stage fog + single follow-spot (lighting), backstage dressing-
         room mirror shot (camera), shy on the outside / greedy inside (dual
         emotion), memory: worn mary janes under the sequin dress (ammo
         semantic). ... (E2-E6 same)
[VERIFY] 4 elements each ✓ anonymous ✓. Stop — essays are raw material, the
         engine turns them into prompts.
```

### 3.5 预检决策（OFF）— 这是规则，不是思考

```
缺失词出现 → 直接在线定向复核（<10 词），不展开推理。
规则: 预检 0.1s/数百词 → flow 0.9s 终检 → 在线仅限 validate 报违规后的定向复核。
```

## 4. 语言镜像陷阱与反制（绘画域实例）

**根因**: CN MoE 模型镜像输入语言。中文用户输入 + 中文文档 = 中文思维链。

| 场景 | 镜像陷阱 | 反制 |
|---|---|---|
| 用户说"暮暮" | 思考里写「暮暮」或拼音 | 思考用 `twilight_sparkle`（英文白名单名） |
| 文档是中文纪律 | 思考用中文复述纪律 | 纪律在思考里压缩成英文关键词（`P1a anonymous first`） |
| 输出要求中文 notes | 误以为思考也要中文 | 输出中文 notes，思考英文——两通道独立 |
| 用户全中文提问 | 全中文思维链 | 首 token `[GOAL]` 强制切英文，之后全程英文 |

**收尾自检**: 关闭任何 thinking 块前扫一遍——出现任一 CJK 字符 → 整块英文重写，再继续。这是硬违规，不妥协。

## 5. Overthinking 检查与预算回收

- **症状**: 同一场景反复措辞 3 遍以上；thinking token > 70% 总输出且评分没升；设计层耗时远超脚本层。
- **处理**: 砍预算——8-Block 填充降到"达标即走"；P1a 场景每个只做一次 VERIFY；essay 四要素齐就收笔。
- **原则**: 创作给足余量，但**过润 = 掉反差**。反 AI 疲劳的精髓是"糙的真实"，不是"精致到完美"。
