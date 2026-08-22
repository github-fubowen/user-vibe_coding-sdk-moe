# ref-14 — Anthropic Cybersecurity Skills（网络安全技能库）集成说明

> **本地落地（v1.8.1，2026-08-18）**：全量库已 clone 至 `~/.workbuddy/skills/cybersecurity-skills/`（49MB / 4510 文件 / 817 SKILL.md，pinned commit `4c0b700`，2026-08-08 main HEAD）。
> **入口路由器**：`cybersecurity-skills-router` skill（`scripts/search.py` 只读检索，stdlib 零依赖）。
> **Repo**: `mukul975/Anthropic-Cybersecurity-Skills` | **License**: Apache-2.0 | **Stars**: 28,624（2026-08-18 复核，28.6K+；HEAD 仍为 `4c0b700` 零漂移）

---

## 1. 仓库画像（2026-08-18 实测复核）

| 维度 | 数值 | 校验方式 |
|------|------|----------|
| 规模 | 817 个 SKILL.md · 34 规范安全域（含别名 46 个原始 subdomain 值） | `find skills -name SKILL.md \| wc -l` / `grep ^subdomain: \| sort -u` |
| 仓库大小 | **~49 MB**（4510 文件：817 SKILL.md + 1453 references + **1095 py** + 2 ps1） | `du -sh` / `find` 实测（⚠️ 早前记 13.5MB 有误，已修正） |
| 活跃度 | 2026-08-08 最后推送（HEAD `4c0b700`）· 更新频繁、main 无稳定 tag（仅旧版 v1.0.0 734 技能） | `git log` / `git ls-remote` |
| 平台兼容 | agentskills.io 标准 → Claude Code / Copilot / Codex CLI / Cursor / Gemini CLI / LangChain / CrewAI 等 26+ 平台 | README |
| ⚠️ 命名注意 | **名称含 "Anthropic" 但 README 明确声明：社区项目，与 Anthropic PBC 无关** | README |

**六框架映射（frontmatter 字段实测，2026-08-18）**：
| 框架 | 覆盖技能数 | 备注 |
|------|-----------|------|
| MITRE ATT&CK | **805** / 817 | 库内 291 唯一技术 / 149 父技术 / 14 战术（ATTACK_COVERAGE.md；上游 badge 标注 v16） |
| NIST CSF 2.0 | **804** / 817 | |
| MITRE D3FEND | **139** / 817 | v1.4.0 |
| NIST AI RMF | **97** / 817 | |
| MITRE F3（反欺诈） | **94** / 817 | 2026-04 新增 Position/Monetization 战术 |
| MITRE ATLAS | **93** / 817 | 2026.07 |

**34 个规范安全域（Top 10）**：cloud-security 66 · threat-hunting 58 · threat-intelligence 52 · network-security 43 · web-application-security 42 · digital-forensics 41 · malware-analysis 39 · identity-access-management 37 · soc-operations 35 · red-teaming 33 …

## 2. 技能结构（agentskills.io 标准）

```
skills/<kebab-name>/
├── SKILL.md       ← YAML frontmatter + Markdown 正文（四段：When to Use / Prerequisites / Workflow / Verification）
├── references/    ← standards.md（框架映射）/ workflows.md（深度流程）
├── scripts/       ← agent.py / process.py 操作助手脚本
└── assets/        ← 模板、清单
```

- **frontmatter**：`name / description / domain / subdomain / tags / version / author / license / nist_csf / mitre_attack / atlas_techniques / d3fend_techniques / nist_ai_rmf / mitre_f3`
- **渐进披露**：frontmatter 扫描 ~30 tokens/技能，全量加载 500–2000 tokens —— 与 SDK §7 Context Assembly 同构
- **发现索引**：根目录 `index.json`（v1.1.0，817 技能 name+description+domain+path 全量索引，2026-08-02 生成；注意**无 subdomain 字段**，子域过滤需读 SKILL.md frontmatter）
- **CI 校验**：`.github/workflows/validate-skills.yml` 委托 `tools/validate-skill.py --all`，只校验 frontmatter 必填字段/命名/去重/域别名，**不校验脚本内容**（已读源码确认）

## 3. 安全审计结论（2026-08-18 复核，全量模式扫描 + 代表性深读）

| 检查项 | 结果 |
|--------|------|
| eval / exec / os.system / __import__ | **全库 1095 py 中仅 9 文件命中**，逐文件深读确认全部为**静态正则/检测 sink 表**（如 `re.compile(...)`、检测 `os.system(` 的模式串），无任何对远程内容的动态执行 |
| subprocess / shell=True | 仅 3 文件含 `shell=True`：atomic-red-team 模拟脚本（**设计如此**——执行 ATT&CK emulation 命令，参数经 shlex.quote、带 timeout 与注释说明）；另两处为检测正则或注释 |
| base64 | 命中集中在 PowerShell/JS 反混淆脚本（对**本地样本**解码是其功能），无远程载荷链 |
| curl \| bash | 30 处命中全部为**检测正则**（如 SUSPICIOUS_PATTERNS 列表）或**官方安装文档示例**（Sliver `curl https://sliver.sh/install \| sudo bash`，官方 BishopFox 源）；无一为隐蔽自动执行的下载即运行 |
| rm -rf / | 唯一命中是 PAM 监控技能里的**高风险命令检测规则**（监控别人别跑 rm -rf /，非自身执行） |
| 硬编码凭证 | 命中的 AKIA…/sk-… 全部是 **AWS 官方文档 EXAMPLE 假 key**（canary 诱饵文件内容）或检测规则示例，无真实密钥 |
| 网络调用 | 公开威胁情报 API（virustotal / abuseipdb / mb-api.abuse.ch）与云 API，key 走环境变量（`os.environ.get`）；SSRF 技能访问 169.254.169.254 属**授权测试**正当用途 |
| 混淆/供应链投毒 | 未发现（结构平实、带 docstring、声明清晰） |
| SKILL.md 法律声明 | 每个攻击类技能头部均有 Legal Notice 授权使用声明 |

**审计结论**：**Benign（可信）**。0 Malicious / 0 实质 Suspicious / 信息性提醒 2 条（① Sliver 安装示例为远程安装模式，官方源可接受但建议改 pin 版本；② 依赖建议未锁版本，按需在 venv/uv 环境装）。内容为**双用途**（含 red-team C2、钓鱼模拟、利用代码等攻击性 playbook），且 CI 不校验脚本 → **使用纪律**：仅授权目标；执行 scripts/ 前先人工过目标脚本；建议隔离环境运行。

## 4. 集成方式（WorkBuddy / 本 SDK，v1.8.1 现状）

**已本地落地**（用户选型：路由器技能 + 本地全量库）：

1. **本地全量库**：`~/.workbuddy/skills/cybersecurity-skills/`（当前 pinned `4c0b700`）。⚠️ **该目录不是独立 git 仓库**（无 `.git`，已并入 skills 主仓库作普通文件，2026-08-18 复核）→ **不能 `git pull`**。更新流程：`gh api repos/mukul975/Anthropic-Cybersecurity-Skills/commits/main --jq '.sha'` 取上游 HEAD → 若 ≠ `4c0b700`：临时目录 `git clone --depth 1` 该 commit → 与本地对比（`diff -r`）→ 按需替换文件 → 提交进 skills 主仓库 → 本文件同步新 SHA
2. **路由器技能**：`cybersecurity-skills-router` —— 检索 `scripts/search.py --keyword/--subdomain [--json]`（stdlib 只读，子域过滤自动扫 frontmatter）；命中后加载目标 SKILL.md 走 Workflow→Verification
3. **上游取新**：`gh api repos/mukul975/Anthropic-Cybersecurity-Skills/contents/index.json` → jq 过滤（未拉最新时兜底）
4. **官方 CLI**（可选）：`npx skills add mukul975/Anthropic-Cybersecurity-Skills`

**版本漂移**：main 无稳定 tag，更新频繁 → 升级库前先记旧 SHA（当前 `4c0b700`），变更后跑一次 §5 的任务抽查。

## 5. 任务路由（Tier 映射）

| 任务类型 | Tier | 思考 | 说明 |
|----------|------|------|------|
| 安全技能检索 / 框架映射查询 / 索引过滤 | **T2** | OFF | search.py / index.json 过滤即可 |
| 安全分析执行（DFIR / 狩猎 / 加固 / 应急） | **T1** | ON medium | 加载 1-3 个匹配技能 → 按 Workflow 执行 → Verification 验证 |
| 授权渗透 / 红队（主动利用） | **T0/T1** | ON high | **前置授权门禁**（目标归属 + 书面授权确认），配合 ref-13 Strix 执行 |
| 脚本审计（执行前） | **T1** | ON medium | 目标脚本过 `ocr`/code-review-graph 再跑 |

**授权门禁（与 ref-13 Strix 相同硬规则）**：未确认目标归属与书面授权 → 禁止调用任何攻击类技能/脚本。路由入口见 `reverse-skill-router` skill。

## 6. 与 SDK 其他 ref 的关系

- **ref-13 Strix**：主动执行工具（AI 渗透测试代理，出 PoC 报告）；**ref-14**：知识库/playbook（教 agent 每一步做什么、验证什么）。两者互补：Strix 跑，ref-14 给方法。
- **ref-12 public-apis**：与 index.json 同属"离线检索层"模式；public-apis 用 pinned commit + SHA256 溯源，本库同思路但直接本地 clone。
- **§6 工具路由**：Security/DFIR 任务链 = `reverse-skill-router`（入口）→ `cybersecurity-skills-router`（本地库检索）→ ref-14 技能库（方法）→ ref-13 Strix / 既有工具（执行）。

## 7. 坑位速查

1. **名称误导**：repo 名带 "Anthropic" 但与 Anthropic 无关 —— 对外引用时不要写成官方出品。
2. **双用途内容**：攻击性 playbook 与正常防御 playbook 同库 —— 检索命中后先看 subdomain 再执行。
3. **CI 只校验 frontmatter**：脚本质量靠社区 review，使用前必须自查（§3）。
4. **仓库漂移快**：817 是 main 分支实时数，v1.0.0 仅 734 —— 依赖时 pin commit（当前 `4c0b700`）。
5. **Windows 环境**：部分脚本为 Windows 取证/AD 攻击场景（DPAPI、EVTX、Kerberoast），在 Linux 跑需注意工具链差异（Impacket 跨平台可替代）。
6. **index.json 无 subdomain**：域过滤必须经 frontmatter（search.py 已自动处理）；直接 jq 过滤会得到全部 817 条。
7. **symlink 环境**（`~/.workbuddy` 为符号链接指向 home 外实际位置）：search.py 用 `Path.resolve()` 定位，symlink 下工作正常（已实测）。
