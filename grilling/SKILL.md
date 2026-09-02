---
name: grilling
description: 需求/计划盘问。Use when the user says grill/盘问/打磨需求, or when starting Engineering/SDD work without a clear spec. 一次一问，走完决策树才动手。
agent_created: true
---

# Grilling — 需求盘问

Interview the user relentlessly about a plan, decision, or idea until we reach a shared understanding. 这是需求澄清的"收敛"阶段：把模糊想法逐分支盘问清楚，直到决策树每个分支都有答案。

> 与 brainstorming 的分工：brainstorming = 发散探索方案；grilling = 收敛决策树。两者可串联使用。

## 核心规则

1. **一次一问**。一次只问一个问题，等用户答复后再继续。一次问多个问题是 bewildering（令人困惑）。
2. **逐分支走决策树**。把计划/需求拆成决策点，按依赖关系逐层解决：先解决被依赖的决策，再解决依赖它的决策。
3. **每个问题先给推荐答案**。`For each question, provide your recommended answer.` 让用户只需确认或纠正，而不是从零思考。
4. **事实自查，决策问人**。凡是能通过探索环境查到的（文件系统、工具、代码库、文档），自己查，不问用户。只有"决策"才交给用户。
5. **共享理解前不动手**。未获得用户确认"我们已经达成一致"之前，禁止开始实现、禁止写代码。

## 反模式（禁止）

- 一次问多个问题
- 追问本可以自己查证的事实（如"这个函数在哪个文件？"）
- 不问清楚就开工
- 打断用户回答、替用户做决策

## 结束条件

- 决策树每个分支都已解决，且用户确认达成共享理解
- 产出：一份简短的决策收敛记录（决策点 + 结论），供后续 writing-plans / to-spec 使用
