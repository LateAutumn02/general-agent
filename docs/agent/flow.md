# Agent 核心循环流程

> 最后更新：2026-06-17

## 阶段1：接收用户回合

1. **创建 TurnRequest** - 普通 prompt、bash mode、slash command 和 resumed input 都转为统一请求。
2. **追加用户消息** - 写入内存状态和 session JSONL。
3. **准备 AbortController** - TUI 的 Esc/Ctrl+C 可以取消当前回合。

## 阶段2：构造模型输入

1. **压缩上下文** - 检查 token 预算，必要时调用 compact。
2. **构建系统提示词** - 注入工具、记忆、cwd、安全规则和当前任务上下文。
3. **准备工具定义** - 只暴露当前权限和平台允许的工具。

## 阶段3：流式模型调用

1. **文本实时输出** - 每个 delta 变成 `assistant_delta`。
2. **工具调用登记** - tool_use 被加入 pending tool calls。
3. **工具早启动** - 对可安全并行的只读工具允许提前执行。

## 阶段4：工具编排

1. **权限检查** - 每个工具调用先进入权限控制器。
2. **只读并发** - Read/Glob/Grep/WebSearch 可并发执行。
3. **写入串行** - Edit/Write/Bash 写操作串行执行，避免竞态。
4. **结果回填** - 工具结果变成 tool_result 消息并写入 session。

## 阶段5：循环或结束

1. **有工具结果** - 将 assistant message 和 tool_result 追加后进入下一轮模型调用。
2. **无工具结果** - 结束当前回合，TUI 恢复输入状态。
3. **发生错误** - 发送 error 事件，保留可诊断信息。

## v1 简化流程

1. 先实现单 agent 主循环。
2. 工具执行可以先在模型响应结束后启动，后续再做 streaming tool executor。
3. 只读工具并发上限先设为 4。
4. Stop hooks 和复杂恢复后置。

