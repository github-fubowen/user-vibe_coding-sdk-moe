# 成瘾机制理论框架

本文档综合神经科学（多巴胺预测误差）、认知心理学（信息缺口/认知闭合）、
进化心理学（超常刺激/注意力偏好）和视觉艺术原理，
系统阐述 AI 绘画成瘾性的底层机制与 prompt 实现方法。

---

## 一、神经机制层：多巴胺回路

### 1.1 预测误差理论（Prediction Error）

**核心原理**：多巴胺的核心功能不是"带来快乐"，而是"驱动人去寻找奖励"。
当大脑遇到预测误差——现实与预期不符时——多巴胺释放量最大。

```
画面输入 → 建立预测 → 发现误差 → 修正预测 → 多巴胺释放（奖励）
```

**最佳预测误差区间**：80% 可理解 + 20% 无法预测

- 太简单（100% 可预测）：大脑 0.1s 识别完毕，无奖励
- 太混乱（100% 无法理解）：大脑放弃解析，无奖励
- 最佳区间：大脑能理解大部分，但有一小部分"说不通"——驱动反复解析

**Prompt 实现**：
- 在高度写实/可信的画面中插入一个超现实元素
- 在熟悉的场景中引入一个"违反常理"的细节
- 主体清晰但背景/光源来源不明

### 1.2 变额强化（Variable Reward）

**核心原理**：类似老虎机上瘾——"稳定的期待 + 不可预测的惊喜"最让人沉迷。
如果观众每次点开你的作品都能猜到内容，很快就会审美疲劳。

**三种奖励类型**（Nir Eyal 的 Hook Model）：

| 类型 | 说明 | AI 绘画应用 |
|:-----|:-----|:-----------|
| 部落奖励（Reward of the Tribe） | 社会认同、归属感 | 评论区互动、身份标签（"喜欢这张的都是 XX 人"） |
| 狩猎奖励（Reward of the Hunt） | 寻找资源/信息 | 画面中隐藏的彩蛋、未揭示的世界观碎片 |
| 自我奖励（Reward of the Self） | 掌控感、完成感 | "我发现了别人没发现的细节"、"我猜对了下一张的内容" |

**Prompt 实现**：
- 系列作品中每次隐藏不同的符号/彩蛋（狩猎奖励）
- 每张留一个评论区可讨论的悬念（部落奖励）
- 设计"懂的才懂"的隐藏细节（自我奖励）

### 1.3 超常刺激（Supernormal Stimuli）

**核心原理**：生物学概念——动物对过度放大的特征（如更艳丽的羽毛、更大的眼睛）
会有比对现实更强烈的神经反应。

**AI 绘画中的应用**：
- **色彩超常**：极高饱和度与冷暖对比（荧光紫+明黄、赛博霓虹）
- **质感超常**：极度夸张的材质细节（流动液体金属、半透明冰晶皮肤、超光泽漆皮）
- **比例超常**：极致视觉张力（巨型建筑 vs 渺小人物、超长走廊、无限纵深）
- **细节超常**：比现实更密集的纹理、更完美的对称、更纯净的光影

**Prompt 实现**：在 prompt 中明确要求"比现实更 X"——比现实更饱和、比现实更光泽、比现实更宏大。

---

## 二、心理机制层：认知本能

### 2.1 信息缺口理论（Information Gap）

**核心原理**：人会天然地想填补自己意识到的知识空缺。
画面中留有"解释空间"，观众更容易停留、脑补、反复回看。

**四种信息缺口的 Prompt 实现**：

1. **时间缺口**：呈现动作/事件的中途瞬间
   - `mid-action`, `unfinished gesture`, `just before reaching`, `the moment after`

2. **空间缺口**：画面边界暗示画外有未展示的空间
   - `looking off-frame`, `hand reaching from outside frame`, `doorway with light spilling in`

3. **关系缺口**：两个角色之间的互动未完成
   - `almost touching`, `one looking while the other looks away`, `letter left unopened on the table`

4. **因果缺口**：结果可见但原因不可见
   - `tears on a smiling face`, `broken glass but no sign of struggle`, `wet footprints leading nowhere`

### 2.2 认知闭合需求（Need for Cognitive Closure）

**核心原理**：人看到不完整/暧昧的信息，会本能地想补全它。
半遮半露的人物、开放式的场景、模糊的表情——大脑自动脑补前因后果。
这个脑补过程本身就是精神投入，投入越多，依恋越强。

**Prompt 实现**：
- 人物面部部分遮挡（头发、阴影、角度）
- 场景只展示局部（门框内、窗户视角、镜子反射）
- 光线只揭示一部分，其余留在暗处
- `partially visible`, `half in shadow`, `glimpsed through`, `reflected in`

### 2.3 情绪残留效应（Emotional Residue）

**核心原理**：单一情绪的消退速度极快（纯美、纯恐怖都是秒忘）；
"混合情绪、未完成的情绪"在大脑中持续残留。

**四种高效混合情绪配方**：

| 混合情绪 | 配方 | Prompt 示例方向 |
|:---------|:-----|:---------------|
| 温暖包裹的孤独 | 暖色调 + 独处场景 + 柔光 | `warm sunset light, solitary figure, soft glow` |
| 华丽中的破碎 | 精美服化道 + 破损/废墟 | `elaborate costume, crumbling surroundings, tarnished gold` |
| 喜悦中的遗憾 | 笑脸 + 泪痕/红眼/未干泪水 | `gentle smile, dried tears, slightly reddened eyes` |
| 日常中的诡异 | 普通场景 + 一个违和细节 | `ordinary classroom, anomalous reflection, uncanny stillness` |

### 2.4 身份投射（Identity Projection / 镜子效应）

**核心原理**：当观众在画面中"看到自己"，就完成了从"看画"到"自我确认"的跃迁。
不是"好美"，是"这就是我"。

**Prompt 实现**：
- 第一人称视角（看到自己的手/腿/影子）
- 情绪状态而非具体事件（"站在雨夜车站等不会来的车"）
- 年龄共鸣（精准锚定特定年龄段的记忆场景）
- `first-person perspective`, `the viewer is standing here`, `looking down at one's own hands`

---

## 三、视觉策略层：注意力控制

### 3.1 分层信息密度（Multi-Layer Information Density）

视觉奖励的递进式释放：

```
远看（0.5s）→ L1 宏观冲击：色彩、光影、主体轮廓
细看（3s）→ L2 中观叙事：道具、纹理、表情、服装细节
放大（10s+）→ L3 微观彩蛋：隐喻符号、隐藏的第二张脸、微小反常
```

**每层的 Prompt 策略**：

| 层级 | Prompt 重点 | 关键词 |
|:-----|:-----------|:------|
| L1 | 极致的光影设定 + 风格化色彩 | `cinematic lighting, high contrast, striking color palette, wide shot` |
| L2 | 叙事性道具 + 质感 + 表情 | `storytelling details, personal belongings, textured fabric, nuanced facial expression` |
| L3 | 隐藏的微小元素 + 象征符号 | `easter eggs hidden in reflections, tiny figure in the distance, cryptic symbols in the shadow areas` |

### 3.2 视觉韵律与视线引导（Visual Rhythm）

**原理**：构图设计让视线在画面中不断游走形成闭合循环，无法"一眼看完"。

**四种视线引导技法**：

1. **S 型/螺旋型构图**：角落 → 沿曲线 → 主体 → 沿另一条线 → 回到起点
2. **引导线法**：利用透视线条、道路、栏杆、延伸的手臂引导视线
3. **多焦点法**：画面有 2-3 个吸引眼球的位置，视线不断跳转
4. **画内画外**：角色视线指向画外，观众的视线跟着出去又回来

**Prompt 关键词**：`leading lines, S-curve composition, multiple points of interest, figure looking off-frame, spiral movement`

### 3.3 色彩节奏（Color Rhythm）

**原理**：颜色不是越鲜艳越好。真正耐看的是"颜色节奏"——
大面积低饱和 + 小面积高饱和 = 视觉呼吸。

**公式**：90% 低饱和晕染 + 10% 高饱和点缀

**经典色彩配方**：

| 配方 | 大面色调 | 点缀色 | 情绪 |
|:-----|:---------|:------|:-----|
| 青橙 | 灰蓝/青灰 | 暖橙/琥珀 | 电影感、怀旧、孤独中的温暖 |
| 蓝紫 | 深蓝/靛蓝 | 品红/荧光紫 | 赛博、梦幻、超现实 |
| 绿橙 | 灰绿/暗绿 | 明黄/暖橙 | 废土、破败中的生机 |
| 全灰+一红 | 灰色世界 | 唯一红色 | 聚焦、残酷、突出 |
| 暖黄+冷蓝 | 暖黄/金黄 | 冷蓝/群青 | 治愈中的疏离 |

**Prompt 实现**：
- `muted [主色调], with a single pop of [点缀色]`
- `predominantly [色调1], punctuated by a solitary [色调2] element`
- `desaturated world, only the [物体] retains its vivid color`

### 3.4 不自然感（Uncanny Valley Lite）

**原理**：停在"有点不对劲，但又说不上来"的区段，而不是直接跳到恐怖。
这种微妙的违和感让观众反复盯着找"哪里怪"。

**四种微违和技法**：

1. **比例微调**：头稍大、手指略长（不明显但潜意识察觉）
2. **光影矛盾**：影子方向与光源不一致、反射内容与实际不符
3. **质感异常**：皮肤过于完美像蜡像/陶瓷、眼睛反光盘度不对
4. **细节违和**：镜子里的动作慢半拍、远处的人影比例不对

**Prompt 关键词**：`subtle uncanny valley, slightly off proportions, unsettling perfection, too still to be real`

---

## 四、综合成瘾公式

将以上所有机制压缩为一条通用公式：

```
成瘾性 =
    认知缺口（信息不对等 × 叙事留白）
  × 情绪极化（混合矛盾情绪 × 以身载情）
  × 分层信息（三层递进奖励）
  × 熟悉中的陌生（日常场景 + 反常元素）
  × 视觉韵律（引导线 × 多焦点 × 色彩节奏）
  × 身份投射（第一人称 × 年龄共鸣）
  × 系列连续性（变额强化 × 蔡格尼克钩子）
```

**引用来源**：综合 Gemini、GPT、豆包、元宝 四大 AI 对成瘾机制的独立分析，交叉验证后提炼。
