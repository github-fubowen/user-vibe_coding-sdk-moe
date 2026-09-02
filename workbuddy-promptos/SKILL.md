---
name: workbuddy-promptos
description: AI 绘画提示词生成产品 workbuddy-promptos v2.3 的跨 session 调用入口。当用户提到"workbuddy-promptos"、"promptos"、"生成提示词"、"提示词生成"、"cn2tags"、"提示词校验"、"提示词改写"、"拆解入库"、或需要 Danbooru 标签生成/校验/评分/组合推荐/创意组合时使用。提供 8 大命令（generate/validate/analyze/cn2tags/rewrite/digest/combine/creative）的完整调用方法、环境坑与已知边界。
agent_created: true
---

# workbuddy-promptos v2.20 — 跨 session 提示词生成工具

## 当前版本要点（v2.20 变更 2026-08-17: Danbooru 在线核验三条 + 缺失标签解析器）

- **Danbooru 在线核验三条**（token 消耗调查实测）: ① `tags.json` API 直连必 403（Cloudflare）——可用通道仅 CLI `danbooru search`（有实帖=存在）或 WebFetch `wiki_pages/<tag>`（HTML 可达，仅辅助）；② **wiki 页缺失 ≠ tag 缺失**（blush 330 万帖无 wiki 页），判死依据 = CLI post search 无实帖；③ `tag_index.json` 结构 = `{version,total,category_names,tags:[{n,p,c,w}]}`，是 153K 子集，高频 tag 也可能漏收（bangs ~2.6M 帖 / slight_smile 均漏收）
- **缺失标签解析器**: 工作区 `_resolve_missing.py`（v1.0）——缺失词一次定位替代表（本地 tag_index 单遍扫描出 头词精确/头词系/语义系 候选）+ `--online` 每词 1 次 CLI 确认，确认存在即打印可粘贴的 `KNOWN_VALID_EXTRA` 补漏行；预检接驳 `python3 _precheck_spec.py <tags.txt> --resolve [--online]`——把过去 ~18 次工具调用的核验链路收敛为 1 次

## 当前版本要点（v2.19 九层结构，对齐 v13 优秀样例）

- **输出结构**: `质量锚A,, 质量锚B,, 身份层(角色变体+系列+count+yuri+solo_focus),, 角色1外观层,, 角色2外观层,, 服装层,, 动作层,, 场景层,, 氛围镜头层`（每角色外观独立层 + 人格注入）
- **质量锚双行**: masterpiece 系列 + score_9_up 系列（头尾各一份）
- **PERSONALITY_MAP**: rarity→makeup/elegant、applejack→freckles/blush、twilight→glasses
- **混合检索 resolve_token()**: 153K→组件词库→fuzzy 替代——设计层不管合规，引擎自动找/替代
- **去重**: 角色层各自独立（保留完整外观）、其他层全局去重；氛围层=设计层自由词出口
- **纯标签输出**: nl2prompt 无自然语言叙事锚（TXT 纯标签）；严格 tags 检查 lookup_resource()=153K OR 组件词库 OR IP 资源 OR Pony 质量锚
- **多人结构**: 单人(1girl+solo)/双人(2girls)/三人(3girls)/多人(multiple_girls)，N 人 N 角色层
- 版本演进全文（v2.1~v2.18）: `references/CHANGELOG.md`

## 位置与入口

```bash
# 必须在 workspace 根目录执行
cd "D:/WorkBuddy/2026-07-23-18-07-50"
python3 .workbuddy/promptos/__main__.py <命令> [参数]
python3 .workbuddy/promptos/__main__.py --help        # 帮助
```

## 环境准备（必须先做）

**关键坑: WorkBuddy 沙箱注入 `PYTHONUSERBASE=D:\Software\python3.13.2\myenv\Scripts`** → import 命中 myenv 里 DLL 损坏的 torch → `WinError 126`。
`__main__.py` 已内置 `_clean_sandbox_env()` 自动清除，**直接调用 CLI 无需手动处理**。仅直接 import 引擎（不走 CLI）时手动清理:

```python
import os, sys
os.environ.pop("PYTHONUSERBASE", None); os.environ.pop("PYTHONPATH", None); os.environ.pop("PYTHONHOME", None)
sys.path[:] = [p for p in sys.path if "myenv" not in p and "vendor" not in p]
```

## 命令速查（一行一命令）

```bash
WB="python3 .workbuddy/promptos/__main__.py"

# 1. generate — 中文需求→标签→8-Block→校验（最常用）
$WB generate "中文需求" [--char 角色] [--ip mlp] [--flat] [--analyze] [--detail] [--std-char] [--nl "短语1;短语2"]

# 2. validate — O(1) 153K 库, 0.05s; --strict fuzzy 判违规, TXT 必须 tags-only, 退出码 1 = 拒交付
$WB validate "<文件>.txt" [--strict] [--cross-check] [--output 报告.md]

# 3. analyze — QSv3 客观评分 + 商业化 7 维
$WB analyze "<文件>.txt"

# 4. cn2tags — 中文→标签（--per-word 2+ 看更多候选，纠正 cn_index 映射偏差）
$WB cn2tags "黑丝竖纹过膝长袜" [--top 3] [--min-count 500]

# 5. rewrite — 风格切换改写
$WB rewrite "<文件>.txt" [--style 熟女|御姐|清纯|Q版] [--remove a,b] [--add a,b]

# 6. digest — 拆解入库 → runtime/tag_frequency.json + skeletons.json 累积
$WB digest "<文件>.txt" [--output 报告.md]

# 7. combine — L1精确+L2 FAISS语义+L3共现+ReRank 精排; 中文种子自动转换
$WB combine "thighhighs,pantyhose" [--top 12] [--layers l1,l2,l3] [--no-rerank] [--allow-nsfw]

# 8. creative — 创意组合采样
$WB creative "主题" [--count 3] [--mode default|addictive|anonymous|meme] [--char 角色] [--seed N] [--validate]

# 9. flow — design_spec.json 契约桥（v2.4）: 角色分配→8-Block组装→注入审计→validate--strict→analyze→MD+TXT双文件
$WB flow design-spec.json [--analyze] [--essay]
#    schema 见 ai-painting-workflow.md §v8.0；示例: design-spec-pure-desire-dhot.json
#    关键: TXT 行必须以质量锚(masterpiece/best quality)开头；inject_card 缺失 token 强制补入并记录审计；scene_seed 保证随机可复现

# 10. danbooru — L4 D 站 tags 爬虫（tags 语法: 空格=AND ~=OR -=排除 score:>N date:>YYYY-MM-DD）
$WB danbooru search "foot_focus white_socks" --limit 20 --order score --detail
$WB danbooru trend --tags "foot_focus" --days 7 --limit 50 --min-score 10
$WB danbooru tags --tags "foot_focus white_socks" --days 7 --limit 100 --top 30   # 高频+低热度(2-6次)反AI疲劳弹药
#    坑: UA 必须 curl 风格否则 403; 某些组合查询 422 → 拆词单查; `-`排除/括号分组 422(仅 ~a 单 OR 可用); --output 导出含画师签名tag 需人工甄别

# 11. nl2prompt — 小作文→v13 完整提示词（引擎生成: IP 外观+组件库扩展+质量锚; 依赖 v13 源仓库 D:\Hermes\projects\promptos）
$WB nl2prompt essay.txt --char "rarity" --theme "cyberpunk popstar" [--model Pony|Illustrious|Flux|MJ]

# 12. nl2tags — 小作文→标签提示词（映射直译: EN_PHRASE_MAP 500+ 映射 + 颜色识别 + DetailExpand + 8-Block）
$WB nl2tags "英文小作文" [--char 角色] [--output out.txt]
#    坑: 裸颜色词非标签(black→black_hair); cinematic/medium_shot 非法→depth of field/close-up; --essay 输出自然语言, nl2tags 输出标签
```

## 完整工作流示例

```bash
$WB combine "丝袜,警察" --top 8            # 1. 探索标签
$WB generate "熟女警花丝袜场景" --analyze  # 2. 生成 + 评分
$WB validate "输出.txt" --strict           # 3. 严格终检
$WB digest "输出.txt"                      # 4. 拆解入库
```

## 已知边界

- combine 英文单种子 + 仅 l1,l3 → 输出空（默认 l1,l2,l3 可用）
- L2 语义噪声（角色名混入）/ PG-13 场景可能漂出 NSFW → ReRank+cat 过滤已压制，非 100%，先人工核对
- FAISS/模型原位引用 `D:\Hermes\projects\promptos\components\` 与 `D:\TEST\embedding_models\`，依赖目录存在
- 依赖: managed Python 环境（torch 2.13/faiss 1.14/sentence-transformers 5.6/jieba/pandas），缺失时 `UV_CACHE_DIR=/tmp/uv-cache-ai uv pip install --system --no-cache <pkg>`
- **153K 缺失词核验**（v2.20 补）: 先跑 `_resolve_missing.py` 本地替代表；必须在线时用 CLI `danbooru search`，**禁止 urllib 直连 tags API（403）**；wiki 页只作辅助不作判据；判死 = CLI 无实帖

## 与 ai-painting-workflow 对接

- P2 校验: validate 替代 danbooru-tags CLI 主查（快 40 倍）+ --cross-check 双引擎
- P0 需求: cn2tags 中文一键转标签；generate --ip 驱动 IP 宇宙
- P1-P3: generate 快路径 / --detail 细节展开 / --pipeline v13 深度链路 / creative 8-Block
- P4 终检: validate --strict（TXT 必须 tags-only；`_nl` 伪标签已豁免）
- P0-P1b → 引擎: flow --spec（design_spec.json 契约桥，v8.0）
- 完整流程文档: `D:\WorkBuddy\2026-07-23-18-07-50\ai-painting-workflow.md`
- 工作流编排/设计纪律: `ai-painting-workflow` skill
