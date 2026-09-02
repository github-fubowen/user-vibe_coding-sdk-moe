---
name: public-apis
description: 公共免费 API 大全离线检索。基于 GitHub 上 46.3 万星标的 public-apis/public-apis 仓库（MIT）的本地数据副本，提供 50 个分类、1668 个公共 API 的离线搜索（按分类/关键词/Auth/HTTPS/CORS 过滤）。当用户要找 API、查询公共接口、问"有没有免费的 XX API"、"找数据源接口"、需要了解某个 API 的鉴权/HTTPS/CORS 情况时使用。纯本地 stdlib 脚本，无网络、无写入，安全。
agent_created: true
---

# public-apis — 公共 API 离线检索

基于 [public-apis/public-apis](https://github.com/public-apis/public-apis)（MIT，46.3 万+ stars）的**本地数据副本**，不依赖网络即可检索 50 个分类、1668 个公共 API。

## 何时使用

- 用户找 API："找天气 API"、"有没有免费的表情包接口"、"股票数据 API"
- 需要对比候选 API 的鉴权方式（No/apiKey/OAuth）、HTTPS、CORS 支持
- 需要按领域（Finance、Weather、Books、Machine Learning…）盘点可用公共接口

## 数据（data/ 目录）

| 文件 | 说明 |
|------|------|
| `data/README.md` | 上游 README.md 原样副本（唯一数据源，解析器只读它） |
| `data/LICENSE` | 上游 MIT 许可证文本（保留署名） |
| `data/PROVENANCE.md` | 溯源信息：仓库、commit SHA、拉取日期、文件 SHA256 |

**数据新鲜度**：以 `data/PROVENANCE.md` 中的 commit SHA 与日期为准。需要更新时按"同步数据"流程操作，不要手工改 README.md（会破坏校验和）。

## 检索（Tier T2，无需思考预算）

```bash
PY=<python3>  # 任意 Python 3.8+
SCRIPT="C:/Users/fu268/.workbuddy/skills/public-apis/scripts/search_apis.py"

$PY "$SCRIPT" --category Finance          # 按分类
$PY "$SCRIPT" --keyword weather           # 名称+描述关键词
$PY "$SCRIPT" --auth No --limit 20        # 免鉴权 API 前 20
$PY "$SCRIPT" --category Books --https yes --cors yes   # 组合过滤
$PY "$SCRIPT" --stats                     # 各分类 API 数量
$PY "$SCRIPT" --category Finance --json   # 结构化 JSON 输出
```

常用过滤参数：`--category`（子串，忽略大小写）、`--keyword`、`--auth`（`No`/`apiKey`/`OAuth`，精确匹配）、`--https yes|no`、`--cors yes|no|unknown`、`--limit`、`--json`/`--csv`/`--stats`。

## 向用户交付的格式

默认表格行：`[分类] 名称  auth  https=  cors=  URL  描述`。回答时给出：
1. 匹配数量与分类
2. 3-5 个最相关结果（名称 + URL + 鉴权 + HTTPS + CORS + 一句话描述）
3. 提醒：列表为社区人工维护，使用前请以 API 官方文档为准

## 同步数据（可选，需用户确认后执行）

```bash
# 1. 记录上游最新 commit
gh api repos/public-apis/public-apis/commits/master --jq '.sha'
# 2. 拉取原样副本
curl -sL https://raw.githubusercontent.com/public-apis/public-apis/master/README.md -o data/README.md
curl -sL https://raw.githubusercontent.com/public-apis/public-apis/master/LICENSE -o data/LICENSE
# 3. 重算 SHA256 并更新 PROVENANCE.md
sha256sum data/README.md
```

同步后必须更新 `data/PROVENANCE.md` 的 commit SHA / 日期 / SHA256，并验证 `--stats` 输出正常。

## 安全说明

- `scripts/search_apis.py`：仅 Python 标准库（argparse/json/re/csv/pathlib），**无网络、无 subprocess、无文件写入**，纯只读解析。
- 数据文件为纯文本（Markdown + MIT 许可证），无可执行内容。
- 供应链口径：数据来自 pinned commit SHA，同步时校验 SHA256。

## 溯源与许可

- 上游：https://github.com/public-apis/public-apis （MIT License）
- 本 skill 为数据检索封装，遵循上游 MIT 许可并保留 LICENSE 文件。
