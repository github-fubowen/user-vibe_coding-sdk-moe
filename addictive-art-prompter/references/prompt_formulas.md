# Prompt 公式模板库

本文档提供可复制的 prompt 公式模板，按情绪类型和场景分类。
所有模板均可直接填入具体内容后用于 Stable Diffusion / Flux / Midjourney / DALL-E 等主流模型。

**标记说明**：
- `[变量]` = 需要替换的具体内容
- `{{固定词}}` = 建议直接使用的关键词
- 每个公式给出 **Pony/IL** 和 **SDXL/Flux** 两个版本

---

## 一、情绪成瘾型 Prompt 公式

### 1.1 极致孤独型

**适用场景**：个人壁纸、情绪树洞、深夜共鸣

**Pony/IL 版**（tag 模式）：
```
masterpiece, best quality,,
1girl, solo, {{{角色特征}}}, [面部方向], [表情],,
[体型], [肤色],,
[服装],,
{{sitting}} alone on a bench, {{empty}} [空间类型],
{{dusk}} lighting, dim warm light, {{soft fog}},
retro aesthetic, nostalgic atmosphere,
{{liminal space}}, {{dreamcore}}, {{cinematic lighting}},
highly detailed background, subtle melancholy
```

**SDXL/Flux 版**（自然语言）：
```
A solitary figure sitting alone in an empty {空间类型} at dusk.
Soft fog diffuses the dim orange lights. The space feels vast and quiet.
Retro aesthetic, cinematic composition. The viewer can feel the weight of stillness.
Loneliness meets warmth in the golden hour light. Highly detailed environment.
--no crowd, --no people in the background
```

**关键变量**：
- 空间类型：train station, shopping mall, school hallway, convenience store, rooftop
- 面部方向：looking away, back turned, profile, face hidden by hair

### 1.2 治愈的忧伤型

**Pony/IL 版**：
```
masterpiece, best quality,,
1girl, solo, [角色], {{gentle smile}}, {{dried tears}}, slightly reddened eyes,,
[体型], [肤色],,
casual clothes, loose sweater,,
{{sitting by the window}}, {{rain outside}}, {{steaming cup}} on the table,
{{soft daylight}}, {{warm interior}} with cold exterior,
{{nostalgic}}, {{bittersweet}}, quiet moment of healing,
cozy cluttered room, scattered personal belongings
```

**SDXL/Flux 版**：
```
A gentle portrait of quiet healing. {角色} sits by a rain-streaked window,
a steaming cup nearby. Her gentle smile carries the trace of dried tears.
The room is warm and cozy, cluttered with personal things.
Outside the window, cold rain falls on an empty street.
Bittersweet nostalgia — the stillness after crying, the warmth after the cold.
Soft diffused daylight, cinematic shallow depth of field.
```

### 1.3 微度诡异型（Uncanny Valley Lite）

**Pony/IL 版**：
```
masterpiece, best quality,,
1girl, [角色], {{looking at viewer}}, {{subtle uncanny expression}},,
[体型], {{porcelain-like skin}},, 
[服装],,
[日常场景], {{but something is off}}, {{anomalous shadow}},
{{flickering fluorescent light}}, {{too still to be real}},
{{eerie atmosphere}}, {{subtle unease}}, mundane horror,
liminal aesthetic, muted desaturated colors, unsettling but beautiful
```

**SDXL/Flux 版**：
```
A scene that feels wrong but you can't say why.
{角色} stands in an ordinary {日常场景}, looking directly at the viewer.
Her skin has a porcelain perfection — too smooth, too still.
The fluorescent light flickers. The shadows fall in the wrong direction.
Everything is normal. Everything is wrong. Eerie but not overtly horrific.
Muted color palette, subtle uncanny valley, unsettling beauty.
```

**可选"违和元素"注入**：
- `reflection in the mirror showing something different`
- `the shadow on the wall is not matching the pose`
- `eyes reflecting something that isn't in the room`

### 1.4 破碎的华丽型

**Pony/IL 版**：
```
masterpiece, best quality,,
1girl, [角色], {{complex expression}}, {{looking down}},,
[体型], [肤色],,
{{elaborate dress}}, ruined gown, torn silk, tarnished jewelry,,
{{standing in ruins}}, {{crumbling architecture}},
{{dramatic lighting}}, {{rays of light through debris}},
{{golden and decay}}, beauty in destruction,
wilted flowers scattered, shattered mirror fragments
```

**SDXL/Flux 版**：
```
A figure in an elaborate, once-beautiful gown stands amidst ruins.
The silk is torn, the jewelry tarnished, yet there is a regal dignity.
Golden light pierces through the debris above, illuminating floating dust.
Beauty and decay intertwined — a fallen queen in a crumbling cathedral.
Wilted flowers and shattered mirror fragments scatter the floor.
Dramatic chiaroscuro lighting, cinematic wide shot.
```

---

## 二、概念矛盾型 Prompt 公式

### 2.1 "不可能并存"组合

**公式**：`[元素 A] + [不该出现的环境 B] + [统一的光照/色调使 A 在 B 中可信]`

**Pony/IL 版**：
```
masterpiece, best quality,,
no humans, {{[元素A]}} {{in}} {{[环境B]}},,
{{[光照条件]}}, {{[色调]}},,
{{surreal but convincing}}, {{conceptual art}},,
{{hyperdetailed}}, photorealistic lighting,,
{{contradiction made natural}}, uncanny harmony
```

**SDXL/Flux 版**：
```
{元素A} floating peacefully inside {环境B}.
The {光照条件} makes it look completely natural, as if it has always been there.
The contradiction is jarring at first, then oddly convincing.
{色调} color palette. Photorealistic render with cinematic composition.
Silent, still, uncanny harmony between two worlds that should never meet.
```

**推荐组合**：
| 元素 A | 环境 B |
|:-------|:-------|
| tropical fish | abandoned subway car |
| cherry tree in full bloom | center of an empty library |
| glowing jellyfish | hospital corridor at night |
| vending machine | snowy mountain peak |
| grand piano | bottom of the ocean |

### 2.2 "材质置换"组合

**公式**：`[物体]` with `[异常材质]` + 正常的光照反应使材质可信

**Pony/IL 版**：
```
masterpiece, best quality,,
[描述], {{[物体]}} {{made of}} {{[异常材质]}},,
{{translucent}}, {{glowing internally}}, {{liquid-like surface}},,
{{photorealistic lighting on [材质] surface}},,
{{macro close-up}}, intricate texture,,
surreal still life, conceptual surrealism
```

**SDXL/Flux 版**：
```
A {物体} made entirely of {异常材质}.
Light passes through its translucent surface, glowing from within.
The texture is impossibly detailed — liquid yet solid, fragile yet eternal.
Photorealistic rendering of the impossible.
Macro photography style, shallow depth of field, dramatic studio lighting.
```

---

## 三、叙事成瘾型 Prompt 公式

### 3.1 "故事切片"公式

**公式**：`[角色] + [一个正在进行的动作，但停在中间] + [1-2 个暗示前因/后果的道具] + [情绪表情]`

**Pony/IL 版**：
```
masterpiece, best quality,,
1girl, [角色], {{mid-action}}, {{[表情]}},,
[体型], [服装],,
{{reaching for}} [目标], but {{freezing}},,
{{[道具 A]}} on the ground, {{[道具 B]}} left behind,,
{{[场景]}}, {{dramatic shadows}},,
{{candid moment}}, {{interrupted scene}}, narrative tension,
cinematic composition, story-driven
```

**SDXL/Flux 版**：
```
A frozen moment in a story you don't fully know yet.
{角色} is mid-action — {动词} — but has stopped, frozen by something unseen.
On the ground: {道具 A}, recently dropped.
In the background: {道具 B}, a clue to what happened before.
{氛围描述}. Everything before this moment and everything after it — 
left entirely to your imagination. Narrative photography style.
```

**"故事切片"变量库**：

| 动作前缀 | 道具 A | 道具 B |
|:---------|:------|:------|
| just opened the door | wet umbrella | unopened letter on floor |
| about to pick up the phone | shattered teacup | half-written note |
| stopped mid-stride | single high-heel shoe | train ticket on the ground |
| hand hovering over the light switch | fallen photograph frame | keys still in the door |

### 3.2 "未完成对话"公式

**公式**：两个角色 + 一个未完成的互动 + 一个看到/一个看不到

**Pony/IL 版**：
```
masterpiece, best quality,,
2girls, [角色A] and [角色B],,
[角色A], {{looking at}} [角色B], {{[表情A]}}, {{mouth slightly open}},,
[角色B], {{looking away}}, {{back turned}}, {{[表情B]}},,
{{almost touching}}, {{fingers just barely apart}},,
[场景], {{cinematic lighting}}, {{dramatic tension}},,
{{unspoken words}}, {{emotional distance}}, narrative composition
```

**SDXL/Flux 版**：
```
Two people in a room. {角色A} is looking at {角色B}, about to speak,
mouth slightly open as if the words are right there.
{角色B} faces away, looking down, unknowing — or choosing not to know.
Their fingers are almost touching, separated by a breath of air.
The conversation that is about to happen (or never will) hangs in the space between them.
{氛围描述}. Cinematic composition. The image holds its breath.
```

---

## 四、视觉成瘾型 Prompt 公式

### 4.1 "三层信息密度"模板

**公式**：`[表层冲击]` + `[中层叙事道具]` + `[深层隐藏彩蛋]`

**SDXL/Flux 版（全面版）**：
```
[CINEMATIC WIDE SHOT] — {表层主体描述} in {场景}.
The composition draws you in — a solitary {角色} illuminated by {光源}.
—— [LAYER 2: MID-GROUND NARRATIVE] ——
The environment tells its own story: {道具A} suggesting {暗示A},
{道具B} — a clue about {暗示B}. Every surface has texture, every object has purpose.
—— [LAYER 3: HIDDEN DEPTHS] ——
Look closer in the {角落/阴影/反射}: {隐藏彩蛋描述}.
A tiny figure in the distance, a reflection that doesn't match,
a symbol hidden in the wallpaper pattern — rewards for those who look deeper.
{色调体系}. {光影设定}. Painted as if by a cinematographer, not a painter.
```

### 4.2 "视觉视线循环"公式

**Pony/IL 版**：
```
masterpiece, best quality,,
[主体角色], {{[核心表情]}}, {{eyes directed at}} [视线目标],,
[场景], {{leading lines}} pointing to [主体],,
{{foreground blur}}, subject in {{mid-ground}}, mysterious {{background light}},,
{{dynamic composition}}, {{multiple focal points}},,
{{S-curve visual flow}}, {{circular composition elements}},,
{{where the eye cannot escape}}, intricate details throughout
```

### 4.3 "色彩节奏"公式

**Pony/IL 版**：
```
masterpiece, best quality,,
[主体],,
{{predominantly [主色调A] and [主色调B]}}, {{desaturated}},,
{{except for a single [高饱和色] [物体]}},,
{{muted world with one vivid anchor}},,
{{[光影条件]}}, {{atmospheric}}, {{color-graded}},
cinematic color theory, intentional palette
```

**SDXL/Flux 版**：
```
The world is rendered in desaturated {色调A} and {色调B} — 
muted, quiet, almost monochrome. Except for one thing.
The {物体} is vividly {高饱和色}, a single anchor of color 
that draws the eye and refuses to let go.
90% desaturated + 10% saturated = visual breathing.
{光影条件} lighting. Cinematic color grading.
```

---

## 五、阈限空间型 Prompt 公式

### 5.1 Liminal Space 模板

**Pony/IL 版**：
```
masterpiece, best quality,,
no humans, {{[空间类型]}},,
{{empty}}, {{abandoned}}, {{still}},,
{{fluorescent lighting}}, {{[不健康色调]}} color cast,,
{{infinite corridor}}, {{vanishing point composition}},,
{{liminal space}}, {{backrooms aesthetic}}, {{dreamcore}},
{{uncanny emptiness}}, {{familiar yet strange}},
trapped in transition, somewhere but nowhere
```

**SDXL/Flux 版**：
```
A {空间类型} that shouldn't feel familiar but does.
It's empty — not just of people, but of purpose. The fluorescent lights
cast a sickly {色调} glow. The corridor stretches impossibly far, 
vanishing into a point you can never quite reach.
You've been here before. In a dream. In a memory that isn't yours.
Liminal space — the architecture of transition, the geometry of waiting.
Analog horror aesthetic, dreamcore, infinite regression.
```

**空间类型变量库**：
- empty hotel hallway at 3am
- abandoned indoor swimming pool
- 90s shopping mall closed for the night
- hospital waiting room with no patients
- school hallway during summer break

---

## 六、身份投射型 Prompt 公式

### 6.1 第一人称沉浸模板

**Pony/IL 版**：
```
masterpiece, best quality,,
{{first-person perspective}},, 
{{looking down at own hands}}, [手部描述],,
{{legs visible at bottom of frame}}, [服装细节],,
{{soft light from [光源位置]}},,
{{[场景] from the viewer's point of view}},,
{{the viewer is the protagonist}}, {{immersive POV}},
personal moment, intimate composition
```

**SDXL/Flux 版**：
```
First-person perspective. You are standing here.
You can see your own hands — {手部描述} — and your legs at the bottom of the frame.
The {场景} stretches before you. {光源描述}.
You are not watching a character. You ARE the character.
This is your moment. Your memory. Your feeling.
Immersive POV, intimate composition, the viewer is the protagonist.
```

---

## 七、Prompt 质量快速自检

每条 prompt 生成后，逐项确认：

- [ ] 有至少一个"没说破"的认知缺口？
- [ ] 情绪是矛盾的混合体（不是单一情绪）？
- [ ] 有中层和深层细节描述（不只有表层）？
- [ ] 有熟悉 + 陌生的冲突元素？
- [ ] 画面有引导视线的构图词？
- [ ] 色彩是"大面积低饱和 + 小面积高饱和"的节奏？
- [ ] 主角的面部/眼睛被特别描述？
- [ ] 有让人产生身份投射的入口（视角/情绪/场景）？

**引用来源**：综合 Gemini、GPT、豆包、元宝 提供的 prompt 示例和视觉策略，统一整理为标准模板。
