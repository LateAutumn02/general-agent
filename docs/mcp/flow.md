# MCP 流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/mcp, reference/cc-haha/src/services

## 阶段1：加载配置

1. **读取 mcp config** - 从 CLI、项目配置和用户配置读取 server 列表。
2. **启动 transport** - 支持 stdio，后续支持 SSE/HTTP。
3. **握手初始化** - 获取 server capabilities、tools、resources。

## 阶段2：注册 MCP 工具

1. **转换 tool schema** - MCP tool 映射为内部 ToolDefinition。
2. **加命名空间** - 使用 `mcp__server__tool` 避免和内置工具冲突。
3. **接入权限系统** - MCP 工具默认 ask。

## 阶段3：调用和清理

1. **执行 MCP callTool** - 带 timeout 和 abort signal。
2. **转换结果** - MCP content 转为 MessageContent。
3. **进程清理** - 会话结束或 server 失败时关闭 transport。

## v1 简化流程

1. 只支持 stdio MCP。
2. 只接入 tools。
3. resources 和 prompts 后置。

