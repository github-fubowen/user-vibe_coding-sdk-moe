# PROVENANCE — public-apis 数据溯源

## 上游仓库

- **仓库**: https://github.com/public-apis/public-apis
- **分支**: master
- **stars**: 463,425（2026-08-18 复核）
- **许可证**: MIT（data/LICENSE 为上游许可证原文）

## 当前数据快照

| 项目 | 值 |
|------|-----|
| 上游 commit SHA | `28458cf5393339be7f8d07ba4806b0bfe6992dc7` |
| 上游提交时间 | 2026-08-17T21:04:12Z |
| 本地拉取时间 | 2026-08-18（GMT+8） |
| data/README.md SHA256 | `874dd7e28c0d568f2a89996847e9b0d77449cedf0b3c04e13a5ecba88622d651` |
| 文件大小 | 236,114 bytes（2176 行） |

## 数据形态

- 50 个分类（`### Category` 标题），每类一张 5 列表格：`API | Description | Auth | HTTPS | CORS`
- 1668 个 API 条目（2026-08-18 解析实测），含名称、URL、描述、鉴权（No/apiKey/OAuth 等）、HTTPS、CORS
- 解析脚本只读取本文件，不联网

## 同步流程

1. 获取最新 commit：`gh api repos/public-apis/public-apis/commits/master --jq '.sha'`
2. 重新下载 README.md / LICENSE（raw.githubusercontent.com）
3. 重算 SHA256，更新本表
4. 跑 `search_apis.py --stats` 验证解析正常
