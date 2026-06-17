# 模型 API 流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/api, reference/cc-haha/src/services

## 阶段1：请求构建

1. **收集消息** - 从 AgentState 读取当前可发送消息。
2. **拼接系统提示词** - 合并基础规则、工具说明、cwd、记忆和项目上下文。
3. **选择工具 schema** - 根据工具注册表和权限模式生成模型可见的工具列表。
4. **设置流式参数** - 打开 streaming，携带 abort signal、timeout 和 token 限制。

## 阶段2：流式响应

1. **接收文本 delta** - 立即发出 `assistant_delta` 事件给 TUI。
2. **接收 tool_use** - 构造 ToolCall，并交给工具编排器决定何时执行。
3. **接收结束事件** - 写入 assistant message，进入工具结果或结束判断。

## 阶段3：错误恢复

1. **网络或超时错误** - 转成 RuntimeError 并允许 UI 显示重试提示。
2. **上下文过长** - 触发 compact 流程后重试。
3. **模型拒绝或格式错误** - 保留原始错误，避免吞掉失败原因。

## v1 简化流程

1. 先实现 Anthropic-compatible streaming。
2. 只支持 text + tool_use + tool_result。
3. 错误恢复先做显示和一次 compact 重试。

