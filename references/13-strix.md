# ref-13 — Strix (AI Penetration Testing Agent) — pointer entry

> Load when: 安全审计/渗透测试类任务（授权范围内：自有应用、API、代码库、CI 门禁）；Review/Debug 模式遇到
> "找出并验证漏洞"需求；需要带 PoC 证据、可落 SARIF 的漏洞报告。
> Investigated 2026-08-18 (54.5K stars / 5.8K forks, Apache-2.0, Python 主包 + Go/Bubble Tea TUI,
> v1.5.3 @ 2026-08-10, 活跃开发 last push 2026-08-17; 复核 2026-08-18 = 54,513 stars).

## 1. What it is

- usestrix/strix：开源 **AI 渗透测试工具**——自主 AI 黑客代理（Graph of Agents：侦察/利用/后渗透多代理
  协作、共享情报、链式利用），**动态执行代码、真实验证漏洞并产出 PoC**（而非静态扫描误报）。
- 覆盖 OWASP Top 10 及更广：访问控制破坏（IDOR/提权/认证绕过）、注入（SQL/NoSQL/OS/SSTI）、SSRF/XXE/
  反序列化/RCE、XSS/CSRF/原型污染、业务逻辑（竞态/支付操纵）、JWT/会话、云与基础设施、API 安全。
- 产品形态：① OSS CLI（自托管，Docker 沙箱 + BYO-LLM）② 托管云 app.strix.ai（REST API，免 Docker/key）
  ③ 本地 Web 查看器 `strix view`（127.0.0.1 + token）④ 官方 4 个编码 agent 技能（SKILL.md 协议）。
- 关键依赖（pyproject 实测）：`openai-agents[litellm]`（agent 框架 + LLM 网关）、`litellm`、`docker`（沙箱）、
  `caido-sdk-client`（HTTP 拦截代理）、外部 Nuclei（扫描）、Playwright（浏览器自动化 XSS/CSRF）、
  reportlab/pypdf（PDF 报告）。入口：`strix = strix.interface.main:main`。

## 2. Install & use (pointer — 未本地安装，按需部署)

```bash
# 方式 A：一键脚本（⚠️ curl|bash 供应链注意，见 §4）
curl -sSL https://strix.ai/install | bash
# 方式 B：pipx（推荐，可锁版本）
pipx install strix-agent          # PyPI: strix-agent

# 前置条件：Docker 运行中 + LLM key（LiteLLM 模型 id）
export STRIX_LLM="openai/gpt-5.4"      # 任意 LiteLLM 支持 id：openai/ anthropic/ openrouter/ ...
export LLM_API_KEY="<key>"

# 运行扫描（-n 无头模式是 agent 环境唯一正确姿势；务必 --max-budget 封顶 LLM 花费）
strix -n -t ./                            # 本地代码（白盒）
strix -n -t https://staging.example.com --scan-mode quick --max-budget 10
strix -n -t https://github.com/org/app -t https://staging.example.com   # 仓库+线上
strix -n --mount ./huge-monorepo          # 大仓库 bind-mount 免拷贝
strix -n -t <target> --resume <run-name>  # 续跑 strix_runs/<run-name>
strix view                                # 本地仪表盘（漏洞/代理图谱/历史/报告）
```

关键 flag：`-t/--target`（URL/仓库 URL/本地路径/域名/IP，可重复）、`-m/--scan-mode`（quick 分钟级 /
standard ~30min / deep 小时级默认）、`--instruction`（凭据/范围/重点）、`--max-budget USD`（LLM 硬上限）、
`--max-turns`（每代理轮次上限，默认 500）。

**退出码**（无头模式）：`0`= 无已验证漏洞（⚠️ 预算/轮次耗尽提前收尾也可能 0，需查
`strix_runs/<run>/run.json` 的 status 与成本核对）、`1`= 致命错误、`2`= 发现漏洞。

**产物**（`strix_runs/<run-name>/`）：`penetration_test_report.md`（执行摘要，先读这个）、
`vulnerabilities/*.md`（每洞一个：PoC + 修复建议）、`vulnerabilities.json/.csv`、`findings.sarif`
（SARIF 2.1.0，可入 GitHub code scanning/ASPM）、`run.json`（元数据/状态/成本）。

## 3. SDK 对接点

| 场景 | 用法 |
|------|------|
| 安全审计（Review 模式扩展） | 授权目标 → `strix -n -t <target> --max-budget N` 后台跑（deep 数小时），先收 `penetration_test_report.md`，再按严重级（critical/high/medium/low/info）汇总结论，PoC 作证据 |
| 修复闭环 | 漏洞清单 → 修根因（勿只修表象）→ **重扫验证 PoC 是否关闭**（官方 fix 技能工作流） |
| CI/CD 门禁 | 官方 ci-security-scanning 技能：GitHub Actions 每 PR diff-scoped 扫描，SARIF 上传 code scanning；云端免 runner/Docker/key |
| 托管云 | 沙箱/无 Docker 环境 → app.strix.ai REST API（`STRIX_API_TOKEN`，注册资产→发起→轮询→SARIF 导出）；Enterprise 有 PDF/DOCX 合规报告（SOC 2/ISO 27001/PCI DSS） |
| LLM 成本复用（本机兴趣点） | 基于 LiteLLM 网关 → `STRIX_LLM` 可指任意 LiteLLM 支持 provider，含自建 OpenAI 兼容端点（如 OmniRoute 本地路由），**具体配置以 docs.strix.ai 实测为准** |
| 安全任务路由 | 与 `reverse-skill-router`（授权渗透/逆向门禁）联动：未确认授权禁止对任何目标执行 |

模式/分层：扫描编排（多代理长链）= T0/T1（thinking ON，旗舰模型）；结果整理/漏洞分级 = T1/T2（OFF，V4-Flash
可承担批量整理）。质量闸门：**引用溯源**——每条发现必须对应 `vulnerabilities/*.md` 的 PoC 证据，与 SDK §5.2 一致。

## 4. Security audit (2026-08-18 调研评估)

- **官方 4 技能（`npx skills add usestrix/strix` 安装物）= 纯 SKILL.md 协议文件，无脚本/无自动执行 → Benign**；
  技能内容即上述命令工作流，不引入可执行载荷。
- **OSS CLI 运行时**：主动攻击型工具——必须 Docker 沙箱 + 自有 LLM key；LLM key 走环境变量；配置存
  `~/.strix/cli-config.json`；本地查看器绑定 127.0.0.1 + token。**仅可对有权测试的目标运行**（README 明示，
  未授权测试多数司法辖区违法，使用者自负合规责任）。
- **⚠️ 供应链提醒**：官方安装链 `curl -sSL https://strix.ai/install | bash` 未锁版本——生产/敏感环境改用
  `pipx install strix-agent==<pinned>` 或 `uv tool install`。
- **⚠️ 未完全核实项**：包内含 `telemetry/` 模块，上报内容未深挖——敏感/气隙环境建议断网运行或先审查源码；
  沙箱 Docker 镜像首次运行自动拉取（体积大）。
- 依赖均为主流库（openai-agents/litellm/docker/caido-sdk-client/cvss/reportlab/cryptography），无怪异性。

## 5. Risks (investigation notes)

- **LLM 花费**：deep 扫描可烧大量 token——必须 `--max-budget`，并核对 `run.json` 成本 vs 预算；
- **退出码语义陷阱**：预算/轮次耗尽提前收尾仍可能 exit 0——"无漏洞"不等于"扫完"，需查 run.json status；
- **时间**：quick 分钟级 / deep 数小时——放后台 + 轮询，勿阻塞；
- **法律边界**：主动利用型测试，授权确认是硬门槛（见 §3 安全路由）；
- **迭代快**：Alpha(2025-08) → v1.5.3(2026-08)，TUI 重写为 Go/Bubble Tea——参考时 pin 版本/commit；
- **未本地安装**：需要 Docker 环境 + LLM key 才可落地，SDK 内仅指针引用。
