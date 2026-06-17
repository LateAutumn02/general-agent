# Swarm 协作流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/swarm, reference/cc-haha/docs/agent

## 阶段1：团队规划

1. **识别复杂任务** - 主 Agent 判断是否需要多个角色协作。
2. **创建团队计划** - 定义成员、依赖关系、交付物和验收标准。
3. **用户确认** - v1 中团队启动需要用户确认。

## 阶段2：成员执行

1. **分配任务** - 每个成员成为 AgentTask。
2. **状态同步** - 团队看板展示 running/blocked/completed。
3. **消息传递** - 成员之间通过 mailbox 或共享摘要交流。

## 阶段3：质量收敛

1. **合并结果** - coordinator 收集成员输出。
2. **质量检查** - reviewer 或 tester 检查结果。
3. **最终报告** - 主 Agent 给用户交付统一结论和下一步。

## v1 简化流程

1. 只写文档和类型。
2. 实现排在单任务、多任务和 AgentTool 后面。

