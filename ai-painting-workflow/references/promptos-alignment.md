# promptos v15 对齐 ai-painting-workflow 改进方案

> 设计稿（2026-08-21）。目标：让 promptos v15 引擎能力与 `ai-painting-workflow` v3.2 技能完全对齐，实现"技能出 spec 契约 → promptos 引擎 0-token 生产 → 权威终检 → 双文件交付"的闭环。
> 依据：promptos 源码（pipeline_v13/v15、brain、validate_gate、deliver、seed-pools v5.2、ip/）与 ai-painting-workflow SKILL.md v3.2、references/models-testing.md、references/token-improvements（IMP-01）。

## 1. 目标与对齐基准

- 对齐基准 = ai-painting-workflow 的 **spec 契约骨架**（meta/quality_anchor/inject_card/char_pool/scene_seed/forbidden/negative/notes/scenes[].blocks 8-Block）与**核心纪律**（P1a 匿名在前、注入卡强制落位、TXT tags-only、双文件交付、权威终检 rc=1 拒交付、IP 锚点置首）。
- 对齐后形态：`design-spec-<theme>.json`（技能产出）→ `pipeline_v15.py spec <spec> --analyze|--essay`（promptos 0-token 生产）→ `.txt + .md` 双文件。

## 2. 现状盘点（已对齐 vs 差距）

| 能力域 | promptos v15 现状 | 对齐状态 |
|---|---|---|
| 8-Block 补全 | components/engine/block_completer.py + inject_card.py | ✅ 已对齐 |
| 低热度弹药 | ammo_pool（post_count_threshold=50000）+ crossref_danbooru | ✅ 基本对齐（缺热度清单注入 spec 通道） |
| 权威终检 | validate_gate.py：153K 库 + KNOWN_VALID_EXTRA + rc=1 拒交付 | ✅ 已对齐（见代码头注释） |
| 双文件交付 | deliver.py：前缀表 + 注入审计 + QSv3 + 块分布 | ✅ 已对齐 |
| IP 角色库 | ip/my-little-pony.json + genshin-impact.json | ⚠️ 需校验 schema 对齐（name_cn/aliases/forms/uncommon+emph_tag/human 三拆） |
| 角色分配 P1b | seed-pools v5.2（chars + personality） | ⚠️ 缺随机洗牌 + 多角色补足（2girls/3girls）+ IP 锚点置首 |
| P1a 匿名场景 | creative-playbook.md + combo-presets.md（静态文档，未进引擎） | ❌ **最大差距**：无场景模板引擎（seed 化、叙事缺口） |
| spec 契约入口 | 仅 `batch "q1;;q2"` 文本入口 | ❌ 无 `design-spec.json` 摄入/校验/回写 |
| essay 小作文模式 | 无 | ❌ 无 essay→8-Block 拆解（记忆点/灯光/双情绪/镜头） |
| 预检链 | danbooru/tag_index.json + json_engine | ⚠️ 无 `_precheck_spec --resolve [--online]` 等价子命令 |
| verified_tags 共享 | 无（skill 侧 runtime/verified_tags.json 554 词） | ❌ 双存储，未统一 |
| brain（本地模型） | rule/small/auto 三模式 + schema 门 + 内存守卫 | ⚠️ 需对齐 models-testing 基座与黄金集 |

## 3. 改进方案（按差距编号 A-J）

### A. spec 契约桥（最高优先，一切的前提）
- 新增子命令：`pipeline_v15.py spec design-spec-<theme>.json --analyze|--essay [--seed N] [--prefix H]`
- 摄入字段与 skill 契约骨架**字节级一致**：meta/quality_anchor/inject_card/char_pool/scene_seed/forbidden/negative/notes/scenes[].blocks（8-Block 键名 block1_style…block8_quality）
- 校验：未知键告警不拒；缺失必填块（7 个内容块）→ rc=1 拒（对齐 8-Block 纪律）
- 回写：输出 TXT/MD 内嵌 spec 原文 + 注入审计（每个 inject token → 场景/块，可机检）
- **验收**：skill 的 design-spec-pure-desire-dhot.json 直接喂入 → 双文件与 `flow --analyze` 输出结构等价（字段级 diff ≤ 排版差异）

### B. P1a 匿名场景模板引擎（0-token 替代设计层）
- 把 creative-playbook.md / combo-presets.md 固化为 `data/scene_templates.json`：每个模板 = 场景骨架（环境+氛围灯+成瘾细节占位）+ **叙事缺口占位**（从 seed-pools 的 personality/ammo 池随机抽取，保证 1 场景 1 缺口）
- 生成：`scene_seed` 播种的确定性伪随机（同 seed 同输出，对齐"可复现"回归项）
- 反差轴：模板按"反差系"预分桶（innocent×setting / gothic×cute…），由 spec.theme 路由
- **验收**：6 场景生成 100% 确定性；每场景 ≥1 个 <50k 低热度标签（ammo_pool 轮换，跨场景不重复）；7 内容块全非空；无 blush/smile 裸词（forbidden 生效）

### C. P1b 角色分配与 IP 锚点
- 从 spec.char_pool / ip/*.json 装载角色（对齐 schema：name_cn/name_en/aliases/base_tags/species/gender/forms{anthro,human}/std_name/uncommon+emph_tag/human 三拆 skin/hair/eye）
- 分配：随机洗牌（scene_seed 播种）；`assign` 显式指定时跳过洗牌（对齐契约）
- 多角色自动补足：2 人→2girls、3→3girls、4+→multiple_girls；单人不误补
- **IP 锚点置首**：`equestria girls` 等系列名置于角色 tags 最前（先于 1girl/角色名）
- **验收**：EQG 双人 CP spec → 输出 identity 块 = 锚点 + 双角色 + 2girls；冷门角色带 `((emph))`

### D. 低热度弹药闭环
- ammo_pool 增加"注入卡落位"出口：每个 inject dimension 的关键 token 至少 1 个出现在最终 prompt（对齐强制落位纪律）
- 热度清单通道：`crossref_danbooru.py --today-hot --min-posts 2000` → 写入 spec 可引用文件（skill P0 搜索结果可直接落盘给引擎）
- **验收**：注入审计逐条可查；弹药轮换跨场景不重复

### E. 预检链子命令（对齐 _precheck_spec --resolve [--online]）
- `pipeline_v15.py precheck tags.txt [--resolve] [--online]`
- 本地单遍扫描 tag_index：头词精确/头词系/语义系候选；缺失词 ≤1 次在线确认（复用 crossref_danbooru CLI）；确认存在 → 打印 KNOWN_VALID_EXTRA 补漏行
- **验收**：coco-maid 三缺失词案例收敛为 1 本地调用 + 每词 1 次在线确认；判死依据 = 无实帖

### F. essay 模式（对齐 v2.10 小作文）
- `--essay`：摄入 scenes[].essay（匿名英文作文）+ assign → 规则拆解四要素（记忆点/灯光层次/双情绪/镜头语言）→ 映射 8-Block；拆解失败降级 small brain 或拒绝并提示
- **验收**：示例 design-spec-popstar-essay-ip.json 全量通过；拆解 0 token 达成率 ≥90%（无法规则化时明确报错而非静默劣化）

### G. verified_tags 统一存储
- 引擎配置新增 `verified_tags_path`（默认指向 skill 的 runtime/verified_tags.json），预检/终检共用；引擎新增命中词回写（跨批次缓存 = MoE-7 缓存命中）
- **验收**：同一词两次批次只在线确认一次

### H. brain 与 models-testing 基座对齐
- brain.small/auto 的模型选择由 `models/bench.py` 黄金集驱动：接入 Backend 协议（已实现 needle/MiniCPM，均 0% 成功 → 结论：**默认保持 rule**，升级阈值调高）
- brain 输出 JSON schema 门已存在（对齐质量闸门），补：失败计数上报（供 token 效率审计）
- **验收**：auto 模式在黄金集 9 组语义分区任务上的成功率 ≥ 规则基线（当前 1B 级模型不达标 → 维持 rule，文档记录）

### I. 回归对齐（引擎侧验收测试）
- 新增 `tests/test_alignment.py`：把 skill 的 25 项回归（可复现/随机/多人分配/注入/轮换补入/多样性审计/分块输出/质量锚/端到端）映射为引擎断言
- 商业化 7 维评分器（deliver QSv3 已含）作为批次级验收
- **验收**：`python -m pytest tests/test_alignment.py` 全绿 = 对齐达成

### J. 文档契约
- promptos docs 补 `SpecContract.md`：spec 契约骨架逐字段说明 + 与 skill 的对应关系（MoE-7 稳定前缀、G3 工具链映射）

## 4. 里程碑（每步可独立交付 + 验收）

| 里程碑 | 内容 | 依赖 | 验收门槛 |
|---|---|---|---|
| **M1** | A + I：spec 契约桥 + 回归骨架 | — | 现有 design-spec 喂入 → 结构等价 |
| **M2** | B + C：场景模板引擎 + 角色分配/IP 锚点 | M1 | 6 场景确定性 + 注入落位 + IP 锚点置首 |
| **M3** | E + G：预检链 + verified_tags 统一 | M1 | 三缺失词案例收敛；二次命中零在线确认 |
| **M4** | D + F：弹药闭环 + essay 模式 | M1, M2 | 注入审计可查；essay 拆解 ≥90% 规则化 |
| **M5** | H + J：brain 对齐 + 文档契约 | M1-M4 | 黄金集规则默认；SpecContract.md 落地 |

## 5. 风险与红线

1. **P1a 规则化是最大不确定**：叙事创作是 LLM 强项，模板引擎可能产出"样板化"场景 → 用反差轴分桶 + 弹药轮换对冲；M2 用商业化 7 维评分验收，<3 分则回退设计（skill 保留 LLM 设计层作为 T0，引擎仅做确定性生产）
2. **essay 拆解**：四要素规则化有失败面 → 明确报错降级，不静默劣化
3. **双引擎 validate 一致性**：skill 的 flow 与 promptos validate_gate 各有一份 153K/白名单 → G 统一 verified_tags，避免两套判罚打架
4. **brain 不达标不硬上**：H 结论已明确 1B 级模型语义分区 0%，rule 是当前正解；Qwen3-30B-A3B 测试通过前不开放 auto 默认

## 6. 落地归属

- 实现位置：**`D:\WorkBuddy\workbuddy-ai-painting-workflow\workbuddy-promptos-noLLM-demo`**（promptos v15 核心自包含克隆副本，已修 3 个接线 bug + 路径本地化，开箱可跑；README + IMPROVEMENT-PLAN.md 含 RAG/小模型方案，git commit c47ebf0）
- promptos 原仓库扩展（components/engine/ 新增 spec.py / scene_engine.py / precheck.py；scripts/pipeline_v15.py 扩展子命令）
- 本设计稿暂存于 skill 分支（ai-painting-workflow-models / references/promptos-alignment.md），待用户确认后同步到 promptos docs/

## 7. 2026-08-21 实测（batch 模式，6 条匿名英文场景）

运行方式：`pipeline_v15.py batch - --brain rule --deliver --model Pony --parallel 1`（stdin `;;` 分隔）。受 WorkBuddy 沙箱 + 机器级 faiss DLL 损坏影响，需运行时 stub（faiss/sentence_transformers 空实现 + PipelineV13 兼容补丁 + enable_cooc=False）——**不修改源码**。

### 结果
- ✅ 6/6 OK；单条实际生成 ~678ms（含 jieba 加载共 ~5.5s）；双文件交付（txt+md，前缀 B，时间戳命名）
- ✅ **0 token 达成**：rule 模式无任何 LLM/网络调用（纯本地规则 + 本地词典）
- ✅ 质量锚开头（score_9_up/score_8_up/masterpiece/best quality/very awa）
- ⚠️ 终检覆盖率 93%（27/29）→ 状态 **REJECT，但 TXT 仍产出**（未阻断交付，违反"rc=1 拒交付"）
- ⚠️ 未命中建议荒谬：`cinematic` → 建议 `slimecicle_cinematic_universe`（近似匹配无阈值）
- ⚠️ 8-Block 块分布仅 block3_attire:1（其余块未统计/未填满，远低于 7 内容块全非空纪律）
- ⚠️ `aged_up` 重复两次（去重缺失）；低热度弹药未见注入（NL 输入未触发 ammo_pool）

### 实测暴露的 v15 接线 bug（对照 M1/M2 差距）
1. `engine.batch` 不可导入：pipeline_v15.py 只把 `components/engine/` 加入 sys.path，`from engine.batch import` 需要 `components/` 在 path
2. `BatchRunner` 传 `target_model=` 给 `PipelineV13.__init__`（签名无此参数）→ 全部 job ERR
3. `enable_cooc=True` 默认读 parquet → 缺 pyarrow/fastparquet 即整条链路失败（官方宣称"自动降级"未实现）
4. 进程池 spawn 子进程不继承运行时 stub/环境 → 沙箱环境需 `--parallel 1`

### 对齐判定
**部分对齐（~40%）**：机制层（质量锚/双文件/终检/0-token）已就位；**纪律层未达标**——REJECT 不阻断、块分布不完整、语义建议无阈值、去重缺失、弹药未注入。这五点与方案 §3-B/D/F 及 M2/M4 验收门槛一一对应，可作为 M1-M4 的优先修复项。

### 角色带入复测（同日，6 主角 × 6 场景，v14/v15 对照）
输入前缀 `equestria girls, <char>, 1girl,`（IP 锚点置首语义），v15 batch 再跑：
- ❌ **IP 锚点全丢**：6 条输出均无 `equestria girls`
- ❌ **角色名大部丢失**：twilight sparkle / rainbow dash / rarity 完全消失；pinkie pie 被拆成 `pie`；仅 applejack、fluttershy 幸存且落于中后部（非置首）
- ✅ 质量锚、1girl 保留；覆盖率仍 93% REJECT（cinematic 未命中不变）
- 根因：组件解析器把角色锚当普通 NL 词处理，identity 块只保留 `1girl`——**M2 的 C 项（IP 锚点置首/角色白名单注入）为实证缺口**
- **v14 对照**（git a006f27 worktree @ D:\TEST\promptos_v14）：分析型管线（QSv3/预算/稀释），对同一输入报"无需优化"（QS=100 但**无生成能力、无身份概念**）——v14 不产出 8-Block，无从谈起锚点
- 结论：v15 生成链路存在，但"身份锚点保真"必须先于 M2 其余项修复（解析器需识别系列名/角色白名单并强制置首，对齐 SKILL §8-Block 规则 6）
