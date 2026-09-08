# chapter8 · 摘要卡
- id: d-aabook-en-ch08-post-training · type: book · bytes: 167,789 · sections: 42 · tokens: ~33,078
- source: bojieli/ai-agent-book@006d2368 · sha256: 18bba724fd677c26 · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
The core formula of this book is Agent = LLM + Context + Tools. This chapter turns to the LLM itself—the "brain." We first use Mid-training to fill gaps in domain knowledge and foundational capabilities, then use post-training methods such as SFT and RL to shape how the model uses context and tools. The end of Chapter 7 pointed out that the evaluation system…

## 高频术语（自动统计 Top-8 · 未校对）
`training`×310 · `model`×295 · `reward`×160 · `sft`×155 · `policy`×141 · `data`×114 · `environment`×104 · `only`×90

## 一句话
第 8 章：模型后训练——Mid-training/SFT/RL 分别补基础/协议/策略，数据与环境比算法重要；GRPO、RLVR、蒸馏与坏案例转训练。

## 章节地图（TOC 压缩，标 ★核心节）
- §Model Post-Training
- §From Pre-training to RL: A Four-Part Panorama
- §From Classic RL Agents to Modern Agents `[Optional Reading]`
- §Model Pre-training Basics `[Optional Reading]`
- §Mid-training: Filling Knowledge and Foundational Capability Gaps
- §SFT (Supervised Fine-Tuning)
- §SFT Data Synthesis: From Demonstrations to Trainable Trajectories
- §When to Choose Mid-training, SFT, and RL
- §Single-Turn Reinforcement Learning: A Comparison of Memory and Generalization
- §RL Algorithms: From 16 Rollouts to One Parameter Update
- §RL Environments: From Evaluation to Simulation
- §From Single-Turn to Multi-Turn: Task Scenarios and Credit Assignment
- §Reward Design: Turning Task Goals into Learning Signals
- §Distillation: Improving Sample Efficiency
- §From Bad Cases to Post-Training
- §Post-Training Practical Takeaways
- §Chapter Summary
- §Thought Questions

## 关键条款（≤8 条，每条 ≤2 行）
- 四部全景与选型（表 8-1/8-4）：Mid-training 补知识基础、SFT 立协议、RL 修策略。
- Mid-training：在目标分布上续训基座，补知识与基础能力两类缺口。
- SFT 数据合成：从生产日志蒸馏可复用任务结构，非重放日志。
- GRPO：16 rollouts → 一次参数更新的直觉解释（DeepSeek 系算法）。
- RL 环境是瓶颈：真实/可重置/可并行，比算法更稀缺。
- RLVR：可验证奖励（测试/断言/diff/格式校验）是最可靠奖励源。
- 坏案例→后训练：Ch7 评测数据映射训练用途（表 8-5）。
- 常见陷阱清单：先识别陷阱省资源（§Post-Training Practical Takeaways）。

## 与 SDK 的关系
- 已吸收：未吸收——本地模型调优（MiniCPM5 等小参数模型）的知识背景层
- 已排除：—
- 未决：—

## 引用约定
注入时打 `<source doc="d-aabook-en-ch08-post-training" section="§x.y">`；引用必须可回查到本节。
