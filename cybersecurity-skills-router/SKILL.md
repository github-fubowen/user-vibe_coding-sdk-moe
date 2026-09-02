---
name: cybersecurity-skills-router
description: >
  Router for the local Anthropic-Cybersecurity-Skills library (mukul975, Apache-2.0):
  817 structured cybersecurity skills / 34 canonical domains / 6 frameworks (MITRE
  ATT&CK v19.1, NIST CSF 2.0, MITRE ATLAS, D3FEND, NIST AI RMF, MITRE F3). USE when
  a task involves cybersecurity: threat hunting, DFIR, malware analysis, threat
  intelligence, IAM, cloud/network/web/API/container security, SOC playbooks,
  compliance mapping, or authorized red-team/pentest work. Searches the local index
  and loads the matching SKILL.md workflow. ⚠️ Dual-use library: offensive skills
  require confirmed target authorization (see reverse-skill-router gate).
version: 1.0.0
license: Apache-2.0
agent_created: true
---

# Cybersecurity Skills Router（本地 817 技能安全库入口）

> 本地库：`~/.workbuddy/skills/cybersecurity-skills/`（49MB，pinned commit `4c0b700`，2026-08-08 main）
> 检索：`scripts/search.py`（stdlib 只读，零依赖）· 索引：`index.json` v1.1.0（2026-08-02）

## When to Use

- 安全域任务的第一步：威胁狩猎 / DFIR / 恶意软件分析 / 威胁情报 / IAM / 云·网络·Web·API·容器安全 / SOC / 合规映射（ATT&CK、CSF、ATLAS、D3FEND、AI RMF、F3）
- 需要"标准 playbook + 可执行步骤 + Verification 清单"而非泛泛回答时
- 把攻击手法映射到检测规则 / 把检测需求映射到 ATT&CK 技术

**Do not use**：一般编程任务（走 SDK 主流程）；未授权目标上的攻击性操作（先过 `reverse-skill-router` 授权门禁）。

## 授权门禁（硬规则，与 ref-13 Strix 相同）

1. 未确认目标归属 + 书面授权 → 禁止加载/执行任何 `red-teaming` / `penetration-testing` / `offensive-security` 类技能
2. 攻击类技能正文均带 Legal Notice —— 视为门禁提醒，不是免罪声明
3. 执行 `scripts/` 下脚本前，先人工过一遍目标脚本（可配合 SDK §6 Review 的 `ocr`/graph 流程），建议隔离环境（Docker/沙箱）
4. 防御类技能（DFIR/狩猎/加固/应急/合规）无此限制

## 检索（T2，思考 OFF）

```bash
python ~/.workbuddy/skills/cybersecurity-skills-router/scripts/search.py --keyword "ransomware" --top 10
python ~/.workbuddy/skills/cybersecurity-skills-router/scripts/search.py --domain cloud-security --top 20
python ~/.workbuddy/skills/cybersecurity-skills-router/scripts/search.py --keyword "DPAPI" --json
```

或用索引直接过滤（jq 可选）：

```bash
jq -r '.skills[] | select(.domain=="digital-forensics") | .name' ~/.workbuddy/skills/cybersecurity-skills/index.json
```

## 加载与执行

1. 检索命中 1-3 个技能（T1，思考 ON medium）
2. 读目标 `SKILL.md`：`When to Use → Prerequisites → Workflow → Verification`
3. 需脚本时读 `scripts/agent.py` / `process.py`，确认输入/输出约定后执行
4. 按技能自带的 Verification 清单收尾（与 SDK §5.3 双保险）

## 框架映射查询（合规/检测规划）

- 某技术属于哪些技能：`grep -rl "mitre_attack:" ~/.workbuddy/skills/cybersecurity-skills/skills/*/SKILL.md | head`（或按 frontmatter 字段过滤）
- 总览：`~/.workbuddy/skills/cybersecurity-skills/ATTACK_COVERAGE.md`、`mappings/` 目录
- 更新库：`git -C ~/.workbuddy/skills/cybersecurity-skills pull`（更新前对比 pinned SHA）

## 坑位速查

1. **名称误导**：repo 名带 "Anthropic" 但为社区项目，与 Anthropic PBC 无关
2. **双用途**：攻击/防御 playbook 同库 —— 命中后先看 `subdomain` 再执行
3. **CI 只校验 frontmatter**（`.github/workflows/validate-skills.yml`），脚本质量靠社区 review，使用前自查
4. **Windows 工具链**：部分脚本面向 Windows 取证/AD 攻击（DPAPI、EVTX、Kerberoast），Linux 下注意工具链差异（Impacket 可跨平台替代）
5. **依赖未锁版本**：脚本头部 `pip install numpy scikit-learn...` 等为建议安装，按需在 venv/uv 环境装，勿全局裸装

## Verification（交付前自检）

- [ ] 检索结果与实际任务匹配（名称/描述/subdomain 三查）
- [ ] 目标归属与授权已确认（攻击类）
- [ ] 脚本输入输出契约已读，超时/错误分支已了解
- [ ] 执行结论有据（引用了技能 Workflow 中的步骤编号）
