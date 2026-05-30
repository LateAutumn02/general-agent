# 数据结构

> MCP (Model Context Protocol) 系统的核心数据结构。

---

## 配置作用域

```
ConfigScope:
  'local' | 'user' | 'project' | 'dynamic' | 'enterprise' | 'claudeai' | 'managed'

优先级（高→低）:
  enterprise > local > project > user > plugin > claudeai
```

---

## 传输类型

```
Transport:
  'stdio'        # 子进程 stdin/stdout
  'sse'          # Server-Sent Events（远程）[v1置空]
  'sse-ide'      # SSE IDE 集成 [v1置空]
  'http'         # Streamable HTTP [v1置空]
  'ws'           # WebSocket [v1置空]
  'ws-ide'       # WebSocket IDE 集成 [v1置空]
  'sdk'          # SDK 控制传输 [v1置空]
```

---

## 服务器配置

McpServerConfig 是一个 8 路判别联合：

```
McpStdioServerConfig:              # v1 使用
  type: 'stdio' | None
  command: str                     # 可执行命令
  args: list[str]                  # 命令参数
  env: dict[str, str]             # (可选) 环境变量

McpSSEServerConfig:               # [v1置空]
  type: 'sse'
  url: str                         # SSE 端点 URL
  headers: dict[str, str]         # (可选) 自定义标头
  headersHelper: str              # (可选) 标头帮助器脚本
  oauth: McpOAuthConfig           # (可选) OAuth 配置

McpWebSocketServerConfig:         # [v1置空]
  type: 'ws'
  url: str
  headers: dict[str, str]

McpSdkServerConfig:               # [v1置空]
  type: 'sdk'
  name: str
```

### Scoped 版本（附加来源信息）

```
ScopedMcpServerConfig:
  ...McpServerConfig
  scope: ConfigScope              # 配置来源作用域
  pluginSource: str               # (可选) 插件来源标识
```

---

## MCP JSON 配置

`.mcp.json` 文件格式：

```
McpJsonConfig:
  mcpServers: dict[str, McpServerConfig]
```

**示例：**

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"]
    }
  }
}
```

---

## 连接状态

```
MCPServerConnection:
  type: 'connected'               # 连接成功
    client: Client                 # MCP SDK Client 实例
    capabilities: dict             # 服务器能力集合
    serverInfo: dict              # 服务器信息
    instructions: str             # (可选) 服务器指令
    config: McpServerConfig       # 原始配置
    cleanup: fn                   # 清理函数
   | type: 'failed'               # 连接失败
    config: McpServerConfig
    error: str                    # (可选) 错误消息
   | type: 'needs-auth'           # 需要认证 [v1置空]
    config: McpServerConfig
   | type: 'pending'              # 正在连接
    config: McpServerConfig
    reconnectAttempt: int         # (可选) 重连尝试次数
    maxReconnectAttempts: int     # (可选) 最大重连次数
   | type: 'disabled'             # 已禁用
    config: McpServerConfig
```

---

## MCP 工具序列化

```
SerializedTool:
  name: str                        # mcp__<server>__<tool> 格式
  description: str                 # 工具描述
  inputJSONSchema: dict            # 输入参数 JSON Schema
  isMcp: bool                      # true 表示 MCP 工具
  originalToolName: str            # 原始工具名（无前缀）
```

---

## MCP CLI 状态

```
MCPCliState:
  clients: list                    # 客户端列表
  configs: dict[str, ScopedMcpServerConfig]  # 配置字典
  tools: list[SerializedTool]      # 工具列表
  resources: dict                  # 资源字典
  normalizedNames: dict[str, str]  # 规范化名称映射
```

---

## MCP 工具定义（内部）

```
MCPTool:
  name: str                        # mcp__<server>__<tool>
  isMcp: true
  mcpInfo:
    serverName: str
    toolName: str
  inputJSONSchema: dict            # 来自 MCP 服务器
  description() -> str             # 来自 MCP 服务器
  call(args, context) -> ToolResult  # 转发给 MCP 服务器
  isConcurrencySafe() -> bool      # 从 tool.annotations.readOnlyHint 派生
  isReadOnly() -> bool             # 从 tool.annotations.readOnlyHint 派生
  isDestructive() -> bool          # 从 tool.annotations.destructiveHint 派生
```

---

## 工具执行结果

```
MCPToolResult:
  data: list                       # MCP 内容块数组（文本/图像/资源）
  mcpMeta:
    _meta: dict                    # 服务器元数据
    structuredContent: dict        # 结构化输出内容
```

---

## MCP 内容估计（用于 Token 计算）

```
MCPContentEstimation:
  textContent_length: int          # 文本内容长度
  totalBinarySize: int             # 二进制内容总大小
```

---

## v1 实际实现

general-agent v1 已实现的数据结构（`general_agent/mcp/types.py`）：

```
MCPServerConfig:
  command: str                          # 可执行命令
  args: list[str]                       # 命令参数
  env: dict[str, str]                   # (可选) 环境变量

MCPToolDef:
  name: str                             # 工具原始名称
  description: str                      # 工具描述（截断至 2048 字符）
  inputSchema: dict                     # 输入参数 JSON Schema
  readOnlyHint: bool                    # 只读提示（默认 True）
```

运行时结构（不在 types.py 中，分布于 client/transport 模块）：
- `MCPServerProcess` — 管理子进程生命周期，发送/接收 JSON-RPC 消息
- `MCPServerClient` — 封装握手、工具发现、工具调用、自动重连
- `MCPTool(Tool)` — 实现 Tool 基类的包装器，名称格式 `mcp__<server>__<tool>`

---

> 最后更新: 2026-05-30 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/services/mcp/types.ts, config.ts, client.ts
