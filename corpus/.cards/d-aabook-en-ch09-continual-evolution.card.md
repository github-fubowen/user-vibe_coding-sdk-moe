# chapter9 · 摘要卡
- id: d-aabook-en-ch09-continual-evolution · type: book · bytes: 79,523 · sections: 17 · tokens: ~15,216
- source: bojieli/ai-agent-book@006d2368 · sha256: bd58b28dbdb2525c · status: abstracted
- generated_by: template-scaffold + auto-extract + agent-written（2026-09-07 一句话/关键条款/关系由 agent 补写，待人工复核；首屏/术语为机械抽取，**未校对**）

## 首屏要点（自动抽取 · 未校对）
Today’s Agents face a striking capability paradox: they can solve previously unseen complex tasks zero-shot, yet after handling ten thousand similar tasks, they may still repeat tomorrow the mistakes they made on the first day. Once a model is on the job, can it keep getting better at that job the way a new hire does? **The ability to learn autonomously from…

## 高频术语（自动统计 Top-8 · 未校对）
`agent`×84 · `task`×55 · `only`×53 · `model`×50 · `evolution`×49 · `trajectories`×47 · `experience`×46 · `learning`×45

## 一句话
第 9 章：Agent 持续进化——从运营轨迹导出学习信号、四种更新方法的选择依据与长期运行的自进化闭环（Voyager 实证）。

## 章节地图（TOC 压缩，标 ★核心节）
- §Continual Evolution of Agents
- §Deriving Learning Signals from Operational Trajectories
- §Four Methods for Continual Agent Evolution
- §Building a Continual-Evolution Closed Loop for Long-Term Operation
- §Chapter Summary
- §Questions for Reflection

## 关键条款（≤8 条，每条 ≤2 行）
- 能力悖论：能零样本解复杂任务，却在万次同类任务后不进化（参数不自动更新）。
- 轨迹评测三问：完成了吗 / 方式合规吗 / 用户满意吗——学习信号的导出顺序。
- 四种更新方法（表 9-2）：按变更位置选择，非按"哪个新"；四方法不互斥。
- 闭环判据：四方法纳入同一自治循环才成为持续进化（图 9-5）。
- Voyager：按能力选目标→技能库→课程规划的完整闭环实证。
- 满意度陷阱：满意度升但违规率也升——不能作唯一学习信号（思考题）。

## 与 SDK 的关系
- 已吸收：未吸收——SDK 版本漂移维护/技能迭代（toolstack-pipeline 六阶段）的方法论出处互证
- 已排除：—
- 未决：—

## 引用约定
注入时打 `<source doc="d-aabook-en-ch09-continual-evolution" section="§x.y">`；引用必须可回查到本节。
