---
name: rsshub-art
description: RSSHub 艺术内容管道 — 300+ 网站路由中提取 Pixiv/Civitai/Konachan/Gelbooru/ArtStation 等平台的实时热门数据。用于 AI 绘画工作流 P0a 深度搜索层，直接抓取平台原始 prompt、标签、参数数据，替代传统 WebSearch 返回的榜单 SEO 文章。
agent_created: true
---

# RSSHub 艺术管道 Skill

## 概述

RSSHub 是 34K+ star 的开源 RSS 引擎（[GitHub](https://github.com/DIYgod/RSSHub)），将任何网站变成 RSS/JSON Feed。本 Skill 聚焦其艺术/图像平台路由，从中提取 AI 绘画相关的 trending prompt、标签、风格趋势。

## 快速使用

```bash
# 引擎路径
ENGINE="D:/WorkBuddy/2026-07-23-18-07-50/.workbuddy/rsshub"

# 安装依赖
cd "$ENGINE" && npm install

# 启动服务（开发模式）
cd "$ENGINE" && npm run dev    # 端口 1200

# 启动服务（生产模式）
cd "$ENGINE" && npm start

# Docker 部署（推荐）
docker run -d --name rsshub -p 1200:1200 \
  -e PIXIV_REFRESHTOKEN=xxx \
  -e CACHE_TYPE=memory \
  diygod/rsshub
```

## 核心路由

### Pixiv（需要 PIXIV_REFRESHTOKEN）

| 路由 | 功能 | 示例 |
|------|------|------|
| `/pixiv/ranking/:mode` | 排行榜 | `/pixiv/ranking/day_ai` |
| `/pixiv/search/:keyword/:order?` | 搜索 | `/pixiv/search/厚塗り/popular` |
| `/pixiv/user/:id` | 画师作品 | `/pixiv/user/123456` |
| `/pixiv/user/bookmarks/:id` | 画师收藏 | `/pixiv/user/bookmarks/123456` |

**排行榜模式（核心用于 AI 绘画工作流）：**

```
/pixiv/ranking/day_ai          ← AI 生成作品日榜（最重要！）
/pixiv/ranking/week            ← 综合周榜
/pixiv/ranking/month           ← 综合月榜
/pixiv/ranking/week_original   ← 原创作品周榜
/pixiv/ranking/day_r18_ai      ← R-18 AI 作品日榜
```

### Civitai

| 路由 | 功能 | 说明 |
|------|------|------|
| `/civitai/models` | 最新 AI 模型 | 监控新 LoRA/Checkpoint |
| `/civitai/discussions/:modelId` | 模型讨论 | 含示例图 + 社区 prompt |

NSFW 模型需要 `CIVITAI_COOKIE` 环境变量。

### Konachan / Gelbooru（Danbooru 标签体系）

| 路由 | 功能 |
|------|------|
| `/konachan/post/popular_recent/:period` | 热门动画壁纸 (1d/1w/1m/1y) |
| `/gelbooru/post/:tags?` | 标签搜索（如 `thighhighs+blush`） |

### 其他平台

| 路由 | 功能 |
|------|------|
| `/artstation/:handle` | ArtStation 画师作品 |
| `/wallhaven/latest` | 最新壁纸 |
| `/wallhaven/search/:filter?` | 壁纸搜索 |

## JSON 输出解析

所有路由支持 `?format=json`，返回结构化 JSON Feed：

```json
{
  "items": [{
    "title": "作品标题",
    "url": "https://www.pixiv.net/artworks/12345678",
    "content_html": "描述<br><img src='...'>",
    "tags": ["厚塗り", "��リジナル", "女の子"],
    "authors": [{"name": "画师名"}],
    "date_published": "2026-07-24T..."
  }]
}
```

**关键字段：**
- `content_html` — 包含完整图片 URL，可解析为参考图
- `tags` — 画师标注的标签，直接对应 Danbooru 词表
- `authors[].name` — 画师名
- `url` — 原链接

## 环境配置 `.env`

```bash
# ==== Pixiv Token（通过 pixiv-token 工具自动获取） ====
PIXIV_REFRESHTOKEN=your_pixiv_refresh_token
PIXIV_IMG_PROXY=https://i.pixiv.re     # 国内访问图片反代

# ==== 可选 ====
CIVITAI_COOKIE=your_civitai_cookie     # NSFW 模型
GELBOORU_API_KEY=your_key              # Gelbooru API
PORT=1200
CACHE_TYPE=memory
CACHE_EXPIRE=300                       # 5 分钟缓存
LOGGER_LEVEL=info
```

### Pixiv Token 获取

**方式 A — 手动获取（推荐，绕过 CAPTCHA）：**

1. 在浏览器中登录 https://www.pixiv.net
2. 按 `F12` → `Application` → `Storage` → `Cookies` → `pixiv.net`
3. 找到 `refresh_token`，复制其值
4. 执行: `export PIXIV_REFRESHTOKEN="复制的token"`

> pixiv-token 自动化方案: `piglig/pixiv-token` (MIT) 已尝试但 Pixiv 要求 CAPTCHA 验证，自动化登录超时。手动方式 30 秒完成且永久有效。

**方式 B — pixiv-token 自动化（CAPTCHA 风险）：**

```bash
cd .workbuddy/pixiv-token && pip install -r requirements.txt
python pixiv_token_fetcher.py -u "邮箱" -p "密码" --no-headless
# 在弹出的浏览器中手动完成 CAPTCHA，工具会自动捕获 token
```

## 工作流集成

```bash
# 工作流 P0a-L2: RSSHub 数据提取示例

# 1. Pixiv AI 日榜 Top 20（JSON 格式）
curl -s "http://localhost:1200/pixiv/ranking/day_ai?format=json&limit=20" \
  | python3 -c "
import sys, json
feed = json.load(sys.stdin)
for item in feed['items'][:20]:
    tags = ', '.join(item.get('tags', [])[:10])
    print(f\"{item['title']} | tags: {tags}\")
"

# 2. 搜索风格词，获取热门作品标签
curl -s "http://localhost:1200/pixiv/search/厚塗り+女の子/popular?format=json&limit=10"

# 3. Civitai 最新模型监控
curl -s "http://localhost:1200/civitai/models?format=json&limit=10"

# 4. Konachan 热门标签趋势
curl -s "http://localhost:1200/konachan/post/popular_recent/1d?format=json&limit=10"
```

### 数据注入到 P1

从 RSSHub 提取的数据直接注入 P1 五元交叉矩阵：

| RSSHub 来源 | 注入维度 | 用途 |
|------------|----------|------|
| Pixiv 排行榜标签 `tags[]` | soft_phrases 素材 | 正在流行的风格标签 |
| Civitai 模型描述 | nltags_block 素材 | prompt 结构、LoRA trigger words |
| Covitai 示例图 prompt | soft_phrases 对比 | 社区实际使用的 prompt 结构 |
| Konachan/Gelbooru 标签 | hard_tags 校验 | Danbooru 标签流行度排行 |

## 许可证

AGPL-3.0
