# 多 Agent 流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/multi-agent, reference/cc-haha/docs/agent

## 阶段1：子 Agent 创建

1. **主 Agent 提出任务** - 使用 AgentTool 或用户手动创建子任务。
2. **选择 Agent 类型** - reviewer、researcher、coder 等类型决定 prompt 和工具。
3. **隔离上下文** - 子 Agent 有独立 messages，但继承 cwd、配置和权限策略。

## 阶段2：并行执行

1. **任务注册** - 每个子 Agent 显示在任务面板。
2. **独立运行** - 子 Agent 不阻塞主输入。
3. **结果回传** - 完成后生成摘要给主 Agent 或用户。

## 阶段3：协作收敛

1. **主 Agent 汇总** - 将多个子结果合并为下一步计划。
2. **冲突处理** - 文件写操作默认由主 Agent 串行落地。
3. **用户审核** - 关键决策交给用户确认。

## v1 简化流程

1. 先实现用户手动多任务。
2. AgentTool 后置。
3. 子 Agent 写文件默认禁用。

