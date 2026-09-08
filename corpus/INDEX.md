# SDK_Reference · 语料索引

> 由 `doc-pipeline.py index` 生成于 2026-09-08T15:02:28+08:00 · 29 份 / 2,425,955B · **正文不进上下文**：先读 `.cards/` 摘要卡，再按章节取原文（≥8K token 禁止整份注入）。
> 语料根：`${SDK_DOCS_ROOT}`（环境变量 `SDK_DOCS_ROOT` 可覆盖）

| id | 文档 | type | bytes | sections | tokens | status | 切分 |
|---|---|---|---|---|---|---|---|
| `d-aabook-en-afterword` | afterword | book | 13,048 | 3 | ~2,735 | abstracted | §可切 |
| `d-aabook-en-ch01-getting-started` | chapter1 | book | 93,764 | 25 | ~18,209 | abstracted | §可切 |
| `d-aabook-en-ch02-context-engineering` | chapter2 | book | 146,315 | 41 | ~28,312 | abstracted | §可切 |
| `d-aabook-en-ch03-memory-knowledge` | chapter3 | book | 118,993 | 29 | ~22,971 | abstracted | §可切 |
| `d-aabook-en-ch04-tools` | chapter4 | book | 83,893 | 20 | ~16,320 | abstracted | §可切 |
| `d-aabook-en-ch05-coding-agent` | chapter5 | book | 139,158 | 20 | ~26,955 | abstracted | §可切 |
| `d-aabook-en-ch06-interaction` | chapter6 | book | 110,782 | 40 | ~21,936 | abstracted | §可切 |
| `d-aabook-en-ch07-evaluation` | chapter7 | book | 130,551 | 48 | ~25,439 | abstracted | §可切 |
| `d-aabook-en-ch08-post-training` | chapter8 | book | 167,789 | 42 | ~33,078 | abstracted | §可切 |
| `d-aabook-en-ch09-continual-evolution` | chapter9 | book | 79,523 | 17 | ~15,216 | abstracted | §可切 |
| `d-aabook-en-ch10-multi-agent` | chapter10 | book | 122,060 | 34 | ~23,345 | abstracted | §可切 |
| `d-aabook-en-introduction` | introduction | book | 24,682 | 5 | ~4,832 | abstracted | §可切 |
| `d-aabook-en-reference-answers` | reference-answers | book | 85,616 | 11 | ~16,443 | abstracted | §可切 |
| `d-agent-doctor-architecture` | agent-doctor-architecture | architecture | 49,276 | 43 | ~8,045 | absorbed | §可切 |
| `d-agent-rag-architecture` | agent-rag-architecture | architecture | 71,528 | 70 | ~10,779 | abstracted | §可切 |
| `d-agentic-cicd-design` | agentic-cicd-design | design | 80,116 | 51 | ~12,396 | absorbed | §可切 |
| `d-agentos-architecture` | agentos-architecture | architecture | 65,811 | 46 | ~9,651 | absorbed | §可切 |
| `d-coding-agent-os-acceptance-system` | coding-agent-os-acceptance-system | architecture | 134,621 | 165 | ~20,042 | abstracted | §可切 |
| `d-coding-agent-os-architecture` | coding-agent-os-architecture | architecture | 60,676 | 51 | ~10,730 | absorbed | §可切 |
| `d-coding-agent-os-dr-architecture` | coding-agent-os-dr-architecture | architecture | 128,031 | 49 | ~19,997 | indexed | §可切 |
| `d-gpt-2026-8-27` | GPT-软件工厂架构-2026.8.27 | guide | 25,577 | 18 | ~2,377 | abstracted | §可切 |
| `d-gpt-agent` | GPT-当前主流agent技术栈 | survey | 41,161 | 39 | ~4,696 | abstracted | §可切 |
| `d-gpt-github-action` | GPT-Github_Action集成方案 | guide | 40,028 | 26 | ~4,681 | abstracted | §可切 |
| `d-gpt-github-action-cicd` | GPT-Github_Action_CICD集成方案 | guide | 35,049 | 26 | ~4,090 | abstracted | §可切 |
| `d-resourceos-architecture` | ResourceOS-Architecture | architecture | 125,131 | 88 | ~19,327 | absorbed | §可切 |
| `d-security-world-model-architecture` | security-world-model-architecture | architecture | 72,068 | 55 | ~11,064 | abstracted | §可切 |
| `d-self-evolving-agentos-architecture` | self_evolving_agentos_architecture | architecture | 63,020 | 55 | ~10,046 | abstracted | §可切 |
| `d-ucsa-architecture` | ucsa-architecture | architecture | 61,747 | 39 | ~9,123 | indexed | §可切 |
| `d-verification-kernel-architecture` | verification-kernel-architecture | architecture | 55,941 | 39 | ~9,205 | absorbed | §可切 |

## 用法

```bash
python scripts/doc-search.py "<query>" --top-k 3 --section   # 命中章节（≤8K tok）
python scripts/doc-pipeline.py check --all --json             # D-01..D-08 巡检
```
