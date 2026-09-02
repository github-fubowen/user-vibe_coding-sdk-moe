---
{}
---

# random-ai-prompt Skill

基于 `github.com/junebug12851/random-ai-prompt` v2.60.1 (Apache 2.0) 封装的随机 AI 绘画提示词生成引擎。

## 引擎位置

```
.workbuddy/random-engine/          ← 克隆的完整项目
  prompt / prompt.cmd               ← CLI 快捷入口
  targets/cli/bin/prompt.js         ← Node.js CLI 入口
  engine/
    core/engine.js                  ← 框架无关的 prompt 引擎
    core/dpl/                       ← DPL (Dynamic Prompt Language) 编译器
    data/lists/                     ← 74 个 txt 词表 (12 类别)
    data/blocks/                    ← 89 个 DPL 块生成器 (6 类别)
```

## 前置条件

```bash
# 进入引擎目录
cd .workbuddy/random-engine

# 安装依赖（仅需一次）
npm install

# 验证可用
node targets/cli/bin/prompt.js --version
```

## CLI 使用

### 基础生成

```bash
# 生成一个随机 prompt
node targets/cli/bin/prompt.js "a {#scene} with {#style} lighting"

# 生成 N 个
node targets/cli/bin/prompt.js --prompts 5

# JSON 输出（机器可读）
node targets/cli/bin/prompt.js --json --prompts 3

# 可复现 seed
node targets/cli/bin/prompt.js --seed 12345 --prompts 4
```

### 块引用（Block References）

```bash
# 随机场景 + 随机风格
"{#scene} at {time}, {#style}"

# 随机动物主题
"{#animal} in {biome}, {#lighting}"

# 指定类别的一选一群组
"{#scene} with {#person}, {#artists}"

# 成人内容
"{#any-nsfw}" --nsfw
```

### 关键词控制

| 参数 | 说明 |
|------|------|
| `--count N` | 每 prompt 随机关键词数 (默认 5) |
| `--max-count N` | 最大关键词数 (默认 7) |
| `--emphasis false` | 关闭随机强调 |
| `--use-artists false` | 不添加艺术家标签 |
| `--mode <mode>` | 强调方言: StableDiffusion / NovelAI / Midjourney / Plain |

### 输出格式规范

生成 prompt 时，每组提示词前必须附加一行 **简洁的碰撞概述**，格式为：

```text
# {角色名} · {场景核心词} · {情绪}-{动作} · {风格}
{prompt内容}
```

**概述规则：**
- 从 raw prompt 中提取 3-4 个关键词构成语义摘要
- 场景取最具体的 2-3 个名词（如 `zoo exhibit squid`）
- 情绪+动作用 `-` 连接（如 `terror-staring`）
- 风格取最独特的 1-2 个艺术风格词
- 整个概述控制在 60 字符以内

**示例：**
```text
# Fluttershy · 云海大桥 · 不安-行军 · 3D felt toy
1girl, fluttershy, equestria_girls, pink_hair, long_hair, green_eyes...

# Twilight Sparkle · 赛博朋克夜 · 羞辱-着陆 · Haboku
1girl, twilight_sparkle, equestria_girls, purple_hair, purple_eyes, glasses...

# Rainbow Dash · 荧光洞穴 · 愤怒-跪下 · Squishy plush
1girl, rainbow_dash, equestria_girls, multicolored_hair, short_hair...
```

### 列表浏览

```bash
# 浏览所有块
node targets/cli/bin/prompt.js list blocks
# 浏览所有列表
node targets/cli/bin/prompt.js list lists
# 浏览预设
node targets/cli/bin/prompt.js list presets
```

## 在我们的工作流中的用法

### 模式 1: 碰撞组合（替代手工 P-roll）

```bash
# 生成 8 个不可预测的 prompt 作为场景起点
node targets/cli/bin/prompt.js --json --prompts 8 --seed $(date +%s) \
  "{#scene} at {time}, {#person} {action}, {emotion} mood, {#style} style"
```

输出 JSON 解析后，每个 prompt 的随机元素作为 P1 交叉合成的素材。

### 模式 2: 单维度随机

```bash
# 只随机场景
node targets/cli/bin/prompt.js --json --prompts 1 "{#scene}"

# 只随机风格
node targets/cli/bin/prompt.js --json --prompts 1 "{#style}"

# 只随机情绪+动作
node targets/cli/bin/prompt.js --json --prompts 1 "{emotion} while {action}"
```

### 模式 3: 模板变形

```bash
# 固定主体 + 随机环境
node targets/cli/bin/prompt.js --json --prompts 8 \
  "1girl, {character}, equestria girls, {#scene}, {emotion}, {#style}, {clothes}, {#lighting}"
```

## 数据池容量

| 类别 | 文件数 | 说明 |
|------|--------|------|
| artist/ | 16 | 按风格分类的艺术家 |
| danbooru/ | 8 | Danbooru 标签（角色/通用 SFW/NSFW） |
| look/ | 13 | 动作、服装、情绪、发型、表情、焦点、天气等 |
| scene/ | 6 | 房间、学校、船、商店、车辆场景 |
| style/ | 5 | 艺术运动、技法、建筑、构造风格 |
| word/ | 10 | 形容词、副词、名词、动词、感叹词 |
| place/ | 2 | 城市、地点名 |
| nature/ | 5 | 动物、花、树、行星、神话生物 |
| lore/ | 6 | 天文、历史、神话、工作、宗教、人群 |
| 块(blocks) | 89 | DPL 场景/主题/风格/片段生成器 |

## 预设系统

26 个预配置的生成预设:

```bash
# 列出预设
node targets/cli/bin/prompt.js list presets

# 使用预设
node targets/cli/bin/prompt.js --preset landscape
node targets/cli/bin/prompt.js --preset portrait,cinematic
```

## 注意事项

- **运行时要求**: Node.js >= 24（`.nvmrc` 固定版本）
- **无需 API 密钥**即可生成 prompt 文本
- **图片生成需提供者密钥**: 使用 `-p <provider>` + `--images` + 通过 `prompt keys set` 设置密钥
- **用户自定义**: `user/` 目录可放置自定义 lists/blocks/settings，覆盖引擎默认值
- **引擎与 CLI 分离**: engine/core 是纯 JS，无 Node 特定依赖，可独立使用
- **种子确定性**: 相同 seed + 相同设置 = 相同输出，批次可复现

## 快速测试

```bash
cd .workbuddy/random-engine
echo '{}' | node -e "process.stdin.resume()" 2>/dev/null  # 确保 Node 可用
node targets/cli/bin/prompt.js --json --prompts 1 --seed 42 "{#scene}"
```
