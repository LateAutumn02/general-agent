# 会话持久化流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/session-persistence, reference/cc-haha/src/utils/sessionStorage.ts

## 阶段1：创建会话

1. **生成 session id** - 新会话启动时创建 UUID。
2. **记录项目上下文** - 保存 cwd、git root、模型和启动参数。
3. **创建 JSONL 文件** - 每条消息和运行事件按追加方式写入。

## 阶段2：持续写入

1. **用户输入写入** - 保存原始输入、mode 和附件引用。
2. **助手消息写入** - 保存完整 assistant message，不只保存最终纯文本。
3. **工具调用写入** - 保存 tool_use、tool_result、权限决策和错误。
4. **任务状态写入** - 后台任务创建、更新、完成都写入 session 附件记录。

## 阶段3：恢复会话

1. **列出候选会话** - 按 cwd、最近时间和标题排序。
2. **加载完整上下文** - 恢复 messages、tool summaries、task metadata。
3. **重建 TUI transcript** - 把历史消息重新渲染出来，而不是只显示一行摘要。
4. **继续对话** - 新输入追加到恢复后的 AgentState。

## v1 简化流程

1. JSONL 存储。
2. `/resume` 列表选择。
3. 恢复完整 messages。
4. 标题生成先使用第一条真实用户消息。

