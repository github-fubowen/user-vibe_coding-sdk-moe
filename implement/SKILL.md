---
name: implement
description: 按 spec/ticket 文件实施工作。Use when tickets are ready and the user says
  "开始实现". 驱动 TDD、收尾双轴 review、提交分支。
agent_created: true
---

# Implement — 按 ticket 实施

根据用户提供的 spec 或 ticket 集实施工作。

## 流程

1. **逐张 ticket 实现**：
   - 读取 ticket 与 spec，理解该切片的目标
   - 确认测试接缝（seam）：在哪个公共接口上测
   - 驱动 `test-driven-development`：红 → 绿 → 重构
2. **全程纪律**：
   - 定期跑类型检查（typecheck）
   - 定期跑单文件测试；结束前跑全量测试套件一次
3. **收尾**：
   - 执行双轴 `requesting-code-review`（标准轴 + Spec 轴）审查本次工作
   - 提交到当前分支

## 规则

- 优先使用 `/tdd`，在预商定的 seams 上测试
- 不跳过测试接缝确认——测试先于实现，接缝先于测试
- 提交遵守项目约定；git push 前需用户确认
