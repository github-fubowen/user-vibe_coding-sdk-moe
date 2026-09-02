# 模型测试基座（models-testing harness）

> 分支 `ai-painting-workflow-models` 专属。为 ai-painting-workflow 提供**多后端模型测试**能力：以 8-Block 结构化抽取为统一任务，对比不同模型的延迟/成功率/置信度/内存，并给出接入新模型的方法。

## 为什么选"8-Block 结构化抽取"作为测试任务

流水线的确定性环节（validate/预检/digest）都是脚本；**digest 拆解入库**（快速路径第 5 步）需要把一条 prompt 拆回 8-Block 维度——这是流水线里唯一适合"小模型做结构化抽取"的落点。规则版拆解器关键词有限，恰好是模型值得测试的地方。

## 文件结构

```
models/
├── __init__.py
├── schema.py        # 8-Block 抽取 JSON Schema（needle 引擎据此编译字节级 grammar）
├── backends.py      # Backend 协议 + RuleBackend（规则基线）+ NeedleBackend（cactus-needle）
├── bench.py         # CLI 基准：延迟/置信度/成功率/agreement + JSON 导出
└── samples/
    ├── prompts.json         # 12 条 Danbooru 风格样本（EQG 足袜控/反差系，符合 8-Block 纪律）
    └── bench-needle.json    # 最近一次 needle 运行指标
```

## 运行

```bash
# 规则基线（任意 python）
python models/bench.py --backend rule

# needle 后端（需要 cactus-needle 环境；bench 自动把 cwd 加入 sys.path）
cd D:\models\needle && .venv\Scripts\python.exe <skill>/models/bench.py --backend needle

# 全部后端 + 导出 JSON
python models/bench.py --backend all --json out.json --n 6
```

## 2026-08-21 needle 2.0.8 首测结果（12 样本）

| 指标 | 规则基线 | needle 2.0.8 |
|---|---|---|
| 成功率（产出有效 8-Block 拆分） | 100% | **0%** |
| 平均延迟 | 0.1 ms | **5887 ms**（p50 5427 / p95 8340） |
| 置信度（校准头） | —（确定性） | avg ~0.000（min 0 / max 0.001） |
| 与规则基线 agreement | 100% | 0%（无产出可比） |
| LLM token 消耗 | 0 | 0（本地推理，无 API） |
| 引擎内存 | — | ~28MB 宣称（RSS 实测未捕获） |

### 机制性发现（已写入 backends.py 注释）
1. **引擎崩溃怪癖**：同一 agent 连续 `complete()` 第二次调用会**进程级崩溃**（exit 1 无 traceback，faulthandler 也抓不到）；`reset()`（保留 schema 重绕会话）后稳定。→ NeedleBackend 每次提取前 `reset()`。
2. **9 字段 schema → 0 calls**：无论 prompt 长短、是否带 system 引导，45M 基座模型都放弃产出调用（type=call 但 calls=0），置信度头 ~0 —— **模型自己在给低置信信号**。
3. **2 字段 mini schema → 1 call 但"全塞进所有字段"**：模型把所有标签原样复制进每个数组，无语义分区能力。
4. HF 直连被墙：`huggingface.co` HTTP 000，需走 `hf-mirror.com` 镜像（引擎 wheel 13.3MB）。

### 结论（截至 2026-08-21，已测 3 后端）
- **needle 2.0.8 与 MiniCPM5-1B 均不适合 8-Block 语义分区任务**（9 类语义判别超出 1B 级能力；规则基线 0.1ms 完胜，且零延迟/零依赖）。
- needle 的置信度门控真实工作（低能力任务置信度头 ~0）；MiniCPM5 无校准头，缺少这层护栏。
- 潜在适用面（未来可测）：**单/双字段简单抽取**（只提角色名、只提服装）；needle 引擎工具调用机制本身正常（能产出合法 JSON 调用）。
- 下一步建议测 **Qwen3-30B-A3B**（3B active，本地 MoE，MoE-4 T2/T3 路由目标）——同协议接入即可对比。

### 2026-08-21 MiniCPM5-1B 二测结果（12 样本，同一任务）

| 指标 | 规则基线 | needle 2.0.8 | **MiniCPM5-1B** |
|---|---|---|---|
| 成功率（产出有效 8-Block 拆分） | 100% | 0% | **0%** |
| 平均延迟 | 0.1 ms | 5887 ms | **10666 ms**（p50 10773 / p95 11258） |
| 置信度 | — | avg ~0.000 | 无校准头（Ollama API） |
| LLM token 消耗 | 0 | 0 | 0（本地推理） |

- 部署：`openbmb/minicpm5:latest`（688MB Q4，Ollama 0.32.14）；Ollama 存储已从 C 迁移到 `D:\ollama\models`（`setx OLLAMA_MODELS` 持久化；托盘应用会自拉起服务进程，需一并终止才释放 11434 端口）
- 现象：9 组分类任务输出**空内容**且烧满 num_predict 预算（空白 token）；2 组最小任务能出 JSON 但**全部标签塞进所有组**——与 needle 行为一致
- 结论：**1B 级模型（needle 45M / MiniCPM5 1.08B）均不具备 9 类语义分区能力**，该任务最小可做规模 > 2B；MiniCPM 无校准置信头，比 needle 还少一层"不会就放手"护栏
- 性能：MiniCPM 空输出病态烧满预算 → 延迟 ≈ needle 的 1.8×；规则基线仍完胜

## 接入新模型（3 步）
1. 在 `backends.py` 实现同名类：`name` + `extract(prompt)->dict|None` + `last_confidence`（可选）+ `rss_mb()`（可选）。
2. `load_backend()` 注册名字。
3. `python models/bench.py --backend <name>` — agreement 自动对照规则基线。

## Token 消耗与改进点清单（2026-08-21 盘点，IMP-* 编号待办）

> 目的：给流水线降 token 提供一张带优先级的路标。总方向 = **引擎化 / 本地化 / 缓存化**（对齐 PromptOS no-LLM 重构线）。

### Token 消耗全图

| 环节 | 消耗 | 量级 | 路由层级 | Thinking |
|---|---|---|---|---|
| P0 搜索/热门清单（关键词扩展、注入卡 token 提取） | ⚠️ LLM | 小（1-2 调用/批） | T2 | OFF |
| P-pre 成瘾卡（反差决策、低热度弹药挑选） | ⚠️ LLM | 小-中 | T0 | ON low-med |
| **P1a 匿名场景设计**（6 场景叙事+反差创作） | 🔴 **LLM（最大头）** | 大 | T0 | ON high |
| P1b 角色分配（随机洗牌） | ✅ 0 | — | 确定性 | OFF |
| 8-Block 填充（标签补全+跨块去重） | ⚠️ LLM | 中（每场景 1-2 调用） | T1 | ON low-med |
| essay 作文 v2.10 | 🔴 LLM | 大（6 篇作文） | T0 | ON medium |
| 预检/validate/digest（脚本） | ✅ 0 | — | 引擎层 | OFF |
| flow 引擎（promptos v14 no-LLM） | ✅ 0 | — | 引擎层 | OFF |
| MoE-5.4 Reflection（仅高价值批次） | ⚠️ LLM | ~3× 批次成本 | T0 | 2 阶段 |

注：`--resolve --online` 每词 1 次走 CLI 非 LLM（0 token）；`runtime/verified_tags.json`（554 词）是已工程化的缓存。

### 改进点（IMP 编号，按性价比排序）

| ID | 环节 | 改进方向 | 预期收益 |
|---|---|---|---|
| IMP-01 | P1a 场景设计 | PromptOS no-LLM 流水线接管（`;;` 分隔符小模型并行）——模板场景库+变量填充，LLM 仅兜底 | 最大头归零 |
| IMP-02 | 8-Block 填充 | 弹药库语义检索替代 LLM：ammo.md + 本地 embedding（MiniLM）近邻补全，LLM 仅跨块去重 | 中量级归零 |
| IMP-03 | P0 关键词扩展 | 本地 embedding 近邻召回替代 LLM 发散 + 热度清单跨批次缓存复用 | 小头归零 |
| IMP-04 | essay 作文 | 骨架模板化（记忆点/灯光/情绪/镜头四要素占位）+ LLM 只填变量；thinking 预算再压 | 大→中 |
| IMP-05 | Reflection | 批判 pass 降级 V4-Flash，仅产出阶段用 T0 | ~3× → ~1.5× |
| IMP-06 | 全链路 | 稳定前缀缓存命中率监控（<60% 即前缀坏了）；verified_tags 扩容 554→2k+ | 单价 ×1/10（DeepSeek 缓存价） |
| IMP-07 | 全链路 | G6 落地：T2 全切本地 Qwen3-30B-A3B；needle 不适语义分区，可试单字段抽取 | API→0 |
| IMP-08 | 本基座 | 对 IMP-02/03 新方案用 bench.py 做 A/B（agreement+延迟），勿凭感觉替换 | 回归证据 |

### 优先级
1. IMP-01（最大头，且与 PromptOS 重构天然衔接）
2. IMP-06（零成本、立即生效的单价下降）
3. IMP-02/03 合并为"弹药检索层"一次落地（共用本地 embedding 基建）
