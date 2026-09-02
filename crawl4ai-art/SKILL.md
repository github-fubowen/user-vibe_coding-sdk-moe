---
name: crawl4ai-art
description: crawl4ai 深度网页提取引擎 — 面向 LLM 的异步 Web 爬虫，用于从 RSSHub 未覆盖的 AI 绘画社区页面深度提取 prompt、标签、模型参数和图片 URL。支持 CSS/XPath/LLM 三种提取策略，JS 渲染 + 反检测 + 无限滚动。
agent_created: true
---

# crawl4ai 深度提取 Skill

## 概述

crawl4ai 是 GitHub 50K+ star 的异步 Web 爬虫（[GitHub](https://github.com/unclecode/crawl4ai)），基于 Playwright + LiteLLM。在 AI 绘画工作流中的定位是 **深度提取层**——RSSHub 覆盖有 API 的站点，crawl4ai 覆盖需要浏览器渲染、点击交互、自定义提取逻辑的页面。

## 快速使用

```bash
# 引擎路径
ENGINE="D:/WorkBuddy/2026-07-23-18-07-50/.workbuddy/crawl4ai"

# 安装
cd "$ENGINE" && pip install crawl4ai

# 安装浏览器
python -c "import crawl4ai; crawl4ai.install_browser()"

# CLI 快速测试
crwl https://civitai.com -o markdown
```

## 三种提取策略

### 策略 A: CSS/XPath 结构化提取（免费、快速）

无需 LLM，通过 schema 定义提取规则：

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

# 从 Civitai 提取模型名和 prompt
schema = {
    "name": "Civitai Model Extractor",
    "baseSelector": "div.mantine-Card-root",
    "fields": [
        {"name": "model_name", "selector": "h1", "type": "text"},
        {"name": "tags", "selector": ".mantine-Badge-root", "type": "list", "fields": [
            {"name": "tag", "type": "text"}
        ]}
    ]
}
strategy = JsonCssExtractionStrategy(schema)

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
        url="https://civitai.com/models",
        config=CrawlerRunConfig(extraction_strategy=strategy)
    )
    print(result.extracted_content)  # JSON 字符串
```

### 策略 B: LLM 语义提取（理解任意页面）

即使页面结构变化，AI 仍能提取有意义内容：

```python
from pydantic import BaseModel
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from crawl4ai import LLMConfig

class ArtworkInfo(BaseModel):
    title: str
    artist: str
    prompt: str
    negative_prompt: str
    tags: list[str]
    image_url: str

strategy = LLMExtractionStrategy(
    llm_config=LLMConfig(
        provider="openai/auto",                    # auto 自动路由
        api_token="freellmapi-7a734b7fb7f6106f666c6203186158737fedcaa9c5da8b58",
        base_url="http://localhost:3001/v1"        # 已验证 Bearer token 连通
    ),
    schema=ArtworkInfo.model_json_schema(),
    instruction="Extract AI artwork metadata: prompt text, tags, artist name"
)
```

### 策略 C: 媒体文件直接提取

自动收集页面所有图片/视频 URL，无需编写规则：

```python
async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url="https://www.pixiv.net/artworks/123456")
    # result.media["images"] → [{src, alt, width, height, ...}]
    for img in result.media.get("images", []):
        print(img["src"])
```

## 工作流集成场景

### 场景 1: Civitai 模型页提取 prompt 参数

```python
# 从 Civitai 模型页的 "Example Images" 中提取 prompt
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "Civitai Prompt Extractor",
    "baseSelector": ".mantine-Carousel-slide",
    "fields": [
        {"name": "image_url", "selector": "img", "type": "attribute", "attribute": "src"},
        {"name": "prompt", "selector": ".prompt-text", "type": "text"},
        {"name": "negative_prompt", "selector": ".negative-prompt-text", "type": "text"}
    ]
}
```

### 场景 2: 社区帖子中的参数分享

```python
# 从任意 AI 绘画论坛帖子中提取分享的 prompt
# 使用 LLM 策略，无需预知页面结构
strategy = LLMExtractionStrategy(
    llm_config=LLMConfig(provider="openai/freellm", ...),
    instruction="""
    Extract all Stable Diffusion / Midjourney prompt text from this page.
    For each prompt found, also extract associated model name, sampler,
    CFG scale, steps, and any LoRA trigger words.
    """
)
```

### 场景 3: 批量监控多站点趋势

```python
# 并行爬取多个 AI 艺术社区首页，提取热门标签
urls = [
    "https://civitai.com/models?sort=Most+Downloaded",
    "https://www.pixiv.net/ranking.php?mode=daily_ai",
    "https://gelbooru.com/index.php?page=post&s=list&tags=highres"
]

async with AsyncWebCrawler() as crawler:
    results = await crawler.arun_many(urls)
    for result in results:
        if result.success:
            print(f"{result.url}: {len(result.media['images'])} images found")
```

### JS 重度站点处理

```python
config = CrawlerRunConfig(
    # 注入 JS 点击/滚动
    js_code=["""
        // 点击 "Show More" 按钮加载完整 prompt
        document.querySelectorAll('.show-more-btn').forEach(b => b.click());
    """],
    # 模拟无限滚动加载 20 页
    virtual_scroll_config=VirtualScrollConfig(
        container_selector="[data-testid='virtual-scroll-container']",
        scroll_count=20,
        scroll_delay=800
    ),
    # 等待网络空闲
    wait_for="networkidle",
    # 反检测模式（绕过 Cloudflare）
    browser_type="undetected"
)
```

## 与 RSSHub 的互补关系

| 场景 | RSSHub | crawl4ai |
|------|--------|----------|
| Pixiv 排行榜 | ✅ `/pixiv/ranking/day_ai` | ❌ 不需要 |
| Civitai 模型列表 | ✅ `/civitai/models` | ❌ 不需要 |
| Civitai 模型**页内 prompt 参数** | ❌ RSS 不含详情 | ✅ CSS 提取 prompt/sampler/CFG |
| 论坛帖子中的参数分享 | ❌ 无路由 | ✅ LLM 提取 |
| JS 渲染的无限滚动内容 | ❌ 不支持 | ✅ VirtualScroll + js_code |
| 反爬虫站点 | ❌ 弱 | ✅ undetected browser |
| 批量多 URL 并发 | ❌ 单路由 | ✅ arun_many 并行 |

## 数据注入到工作流 P1

从 crawl4ai 提取的数据直接注入 P1 五元交叉矩阵：

| crawl4ai 来源 | 注入维度 | 用途 |
|-------------|----------|------|
| Civitai 模型页 prompt 原文 | nltags_block 对照 | 社区实际 prompt 结构 |
| Civitai LoRA trigger words | hard_tags 扩展 | 新模型触发词 |
| 社区帖子参数 | soft_phrases 素材 | sampler/CFG/步数配置 |
| 图片 URL | P1 视觉参考 | 构图/光影借鉴 |

## 许可证

Apache 2.0 — 可商用、可修改、可集成。
