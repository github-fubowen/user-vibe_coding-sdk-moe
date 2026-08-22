# ref-19 — Token 脚本化流水线（scripted pipelines for token reduction）

> Load when: 任何"降低 token 消耗 / 脚本化 / pipeline"需求；Debug 验证、工具探测、版本 bump、金标回归、token 计量。
> 依据：Agent Doctor 控制面纪律（ref-17）"确定性先行、LLM 后置" + SDK §3 G-gates + ref-05 指标。
> 实现状态：**P0 三件 + P1 两件 + P2 三件全部实现（v1.12.0）**，共 9 个脚本。

---

## 1. 原则（所有脚本共同遵守）

1. **stdlib-only Python 3.9+**，零第三方依赖，放 `scripts/`（对齐 ref-15 先例）。
2. **JSON 进出**：`--json` 机器可读输出；后续阶段/agent 直接消费，中间零 LLM 叙述。
3. **Exit code 门禁**：0=干净/通过，2=失败/漂移（对齐 toolstack-pipeline）。
4. **绝不自动 push**：写操作最多到本地 commit（tier-4 门，§10.9）。
5. **输出有界**：tail 截断（默认 12 行），禁止全量日志倾倒（G1）。
6. **稳定前缀保护**：SKILL.md 只加指针行，规格全在本文件（渐进披露）。

## 2. 已实现（P0 三件，v1.11.0）

### 2.1 `scripts/probe-tools.py` — 会话级工具探测单次化
- **替代**：§6 每会话 6+ 次 `--version` 探测 tool call → 1 次确定性调用。
- **数据源**：`toolstack.json` `local_tools` manifest（单一事实源，与 ref-15 共用，防双份漂移）。
- 用法：`python scripts/probe-tools.py --json`（agent 会话首步跑一次）；`--group <g>` 过滤。
- 特性：Windows npm shim `.cmd/.exe` 回退；缺失工具不致命（G3 降级原则）。

### 2.2 `scripts/verify-runner.py` — 确定性验证闸
- **替代**：§5.6/ref-18 §4 的 LLM 叙述验证环 → 1 次调用拿 pass/fail 事实。
- 用法：
  ```bash
  python scripts/verify-runner.py --config verify.json --json   # 项目内 verify.json
  python scripts/verify-runner.py --cmd pytest -q --tail 8      # 临时单步
  ```
- `verify.json` schema：`{"steps":[{"name":"test","cmd":["pytest","-q"],"timeout":120}]}`
- **职责边界**：脚本只报 pass/fail 事实；五态判定（REGRESSION/UNKNOWN，ref-18 §4）留在 agent。

### 2.3 `scripts/bump-version.py` — 版本 bump 单命令化
- **替代**：§10.8 每次 bump 的 6-10 次手工编辑+提交 → 1 命令。
- 用法：`python scripts/bump-version.py v1.12.0 --apply --commit`
  - 自动改：SKILL.md（frontmatter+title）、README（blurb+version-line）、CHANGELOG 插入日期头。
  - 默认 dry-run；`--json` 机器可读；**永不 push**（§10 纪律内置）。
- 注意：CHANGELOG 条目**正文**留给 agent 填写（叙述性内容不脚本化），脚本只插头部。

## 3. 已实现 P1（Debug 零 LLM 首轮）

### 3.1 `scripts/golden-run.py` — 金标回归 1 命令化
- **替代**：§8/ref-05 金标回归（手动/LLM-as-judge 多回合）→ 1 命令。
- 结构性判分（regex/contains，**零 LLM-judge**）；默认接 OmniRoute `$OMNIROUTE_URL`（OpenAI 兼容），`--offline` 纯判分模式。
- 用法：
  ```bash
  python scripts/golden-run.py --set golden-set.json --model auto --json
  python scripts/golden-run.py --set golden-set.json --offline        # 判分预填 response 的样本
  python scripts/golden-run.py --set golden-set.json --baseline base.json --json  # A/B diff（回归 >2% exit 2）
  python scripts/golden-run.py --set golden-set.json --validate-set   # 预检 accept 规则（v1.15.0，fail-fast，零 LLM 调用）
  ```
- 输出：pass rate / in/out tokens / token efficiency / baseline diff（ref-05 §2 指标表）。
- 金标集 schema：`{"samples":[{"id","task_type","prompt","accept":[{"type":"regex|contains","pattern"}],"expected","difficulty"}]}`。
- **`--validate-set`（v1.15.0）**：跑回归前预编译全部 accept regex + 校验字段，坏规则立即列出并 exit 2——避免把坏集跑进 LLM 烧 token。

### 3.2 `scripts/error-sig.py` — 错误签名库 add/match
- **替代**：ref-18 确定性先行步骤 2（日志/签名匹配）→ 持久化零 LLM 查询。
- 用法：`add --pattern "a,b" --label .. --fix ..`（写 `scripts/data/error-signatures.json`）｜`match --text "..." --json`｜`list`。
- 首次 Debug 遇到新颖错误 → `add` 沉淀；后续 `match` 直接命中已知修复，跳过一次完整诊断。

### 3.3 `scripts/case-search.py` — 问题案例库检索
- **替代**：ref-18 §5 案例库手工翻查 → grep 式检索（按命中数排序，标题优先）。
- 用法：`case-search.py --q "症状关键词"`（默认 `.workbuddy/debug-cases/`，可 `--dir` 指定）；多关键词空格分隔 = 文件内 AND。

## 4. 已实现 P2（按需）

| 脚本 | 替代的 LLM 消耗 | 用法 |
|---|---|---|
| `env-snapshot.py` | ref-18 "查环境"多轮 → 一次性快照 | `--json --log app.log --configs "a.json,b.json"`；PATH 默认截断 10 条（G1），npm 等 `.cmd` 回退 |
| `review-prefilter.py` | Review 大 diff 全量注入 → 精简关注包 | `--base main --json`（diff 统计 top-N + 检查步骤）；检查失败 exit 2（阻塞标记） |
| `token-meter.py` | G4/G6 人工计量 → 自动指标 | `--log calls.jsonl --prices '{"model":x}' --json`；ref-05 §7 JSONL schema，缺失字段 CJK-aware 估算 |
| `robustness-suite.py` | 鲁棒性回归套件（v1.15.0） | `python scripts/robustness-suite.py`（22 用例，exit 0/2）；`--only <脚本名>` 过滤；`--json` 机器可读 |
| `privacy-scan.py` | 公开推送前人工 grep 隐私扫描 → 脚本化（v1.16.0） | `python scripts/privacy-scan.py <dir> [--user <名>] [--allow-user <名>]`；五组模式（users/paths/endpoints/keys/emails），文档 EXAMPLE 与通用路径自动过滤，exit 0 干净 / 2 阻断 |

## 4.5 种子数据（v1.13.0，v2 于 v1.14.0 更新）

| 路径 | 内容 | 用途 |
|---|---|---|
| `scripts/data/golden-set-v1.json` | 20 条 CN 样本，5 族（qa 4 / code 4 / long-text 3 / extraction 4 / tool-use 5），全结构性 accept 规则 | 初版判分规则（个别过严，已被 v2 取代） |
| `scripts/data/golden-set-v2.json` | 同 20 样本，放宽 ext-03（中英键皆可）与 tool-05（同义词组） | **推荐使用**：`golden-run.py --set scripts/data/golden-set-v2.json --model <id> --json` |
| `scripts/data/baseline-longcat-v1.json` | LongCat（lc/LongCat-2.0）首条基线（v1 集，18/20=90%） | `--baseline` A/B 对比参照 |
| `scripts/data/error-signatures.json` | 12 条已知签名（沙箱 shim / tmp 路径 / PAT 403 / index.lock / OmniRoute 503 / SSE 流等） | `error-sig.py match --text "$(cat err.log)"` 直接命中已知修复 |
| `.workbuddy/debug-cases/` | 4 个真实 incident 轨迹（pytest shim / changelog 布局 / tmp 路径 / OmniRoute 503） | `case-search.py --q "关键词"` 复用；新 Debug 收尾按 ref-18 §5 模板追加 |

## 5. 与 SDK 其他部分的关系

- **§6 工具路由**：probe-tools 是 §6 "probe once per session" 的落地实现（G3 静态路由）。
- **§5.6/ref-18**：verify-runner 是验证阶段的确定性事实源；五态判定仍在 agent。
- **§8/ref-05**：golden-run（P1）把"回归纪律"变成 1 命令，指标表按 ref-05 §2 定义输出。
- **§10.8**：bump-version 把自版本管理脚本化；push 门禁纪律原样保留。
- **ref-15**：probe-tools 复用 toolstack.json；所有新脚本应纳入 toolstack 管治（防漂移）；**robustness-suite.py 建议并入月度巡检**（脚本变更后先跑套件再提交，即 ref-15 probe 阶段前置自检）。
- **公开推送前门禁（v1.16.0）**：`privacy-scan.py` 作为推送前置检查——公开仓库推送前跑一次（`--user <本机用户名>` 等），0 项才允许 push；v1.15.1 脱敏、v1.15.2 OmniRoute 端点脱敏均由人工 grep 完成，脚本化后防复发（sdk-snapshot 分支教训）。

## 6. 已知边界

1. verify-runner 判定只含 exit code——不解析测试断言文本（保持确定性，不依赖脆 regex）。
2. bump-version 只替换与旧版本**精确匹配**的版本 token，不做正则横扫（防误伤）；changelog 头插入**布局健壮**（v1.13.1 起：插到首条 `## v` 之前，不再依赖标题位置）；CHANGELOG 仍建议保持规范布局（标题最上、新条目最上）。
3. 沙箱 PYTHONPATH shim 可能干扰系统 python 的包（实测 pytest 在其 myenv 下报 `__spec__`）——脚本自身零依赖不受影响，但**被探测的工具**可能因环境损坏而报失败，属预期降级。
4. Git Bash `/tmp` 路径在 Windows Python 下不被解析（token-meter 首测 no records）——测试/调用请用 Windows 风格路径。
