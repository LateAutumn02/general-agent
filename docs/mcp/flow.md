# 流程

> MCP (Model Context Protocol) 的完整生命周期。从配置加载、连接建立、工具发现到执行。

---

## 概览

MCP 让 Claude Code 接入外部工具服务器。一个 MCP 服务器可以暴露多个工具、资源和提示词，Claude Code 将它们合并到统一的工具池中。v1 实现基础 stdio 传输 + 工具发现和执行，跳过 OAuth、channel、IDE 等高级功能。

---

## 阶段1：配置加载

### 配置来源与优先级

MCP 支持 7 种配置作用域（priority 从高到低）：

```
enterprise (managed) → local → project → user → dynamic → plugin → claudeai
```

1. **Enterprise 配置** — `managed-mcp.json`，如果存在则覆盖所有其他配置
2. **插件配置** — `loadAllPluginsCacheOnly()` → `getPluginMcpServers()`
3. **用户配置** — `~/.claude.json` → `mcpServers`
4. **项目配置** — `.mcp.json`，从根目录向当前目录遍历，就近覆盖
5. **Local 配置** — project-local `settings.json` → `mcpServers`
6. **Dynamic 配置** — `--mcp-config` CLI 标志
7. **Claude.ai 连接器** `[v1置空]` — 从 claude.ai 获取的 MCP 连接器

### 配置去重

- 插件服务器与手动配置的去重（手动配置优先）
- Claude.ai 连接器与手动配置的去重（手动配置优先）
- 通过 `getClaudeCodeMcpConfigs()` 生成并哈希配置用于变更检测

### 策略过滤 `[v1置空]`

- **Allowlist**（`allowedMcpServers`）：只允许列出的服务器，支持名称匹配、命令匹配、URL 匹配（`*` 通配符）
- **Denylist**（`deniedMcpServers`）：明确阻止，优先于允许列表
- **`allowManagedMcpServersOnly: true`**：仅使用托管设置中的允许列表

### 环境变量展开

`expandEnvVarsInString()` 处理 `${VAR}` 和 `${VAR:-default}` 语法，用于命令、参数、环境变量、URL 和标头。

---

## 阶段2：传输类型

MCP 支持 7 种传输方式：

| 传输 | 类型 | 用途 | v1 |
|---|---|---|---|
| `stdio` | 子进程 stdin/stdout | 本地命令行工具 | 实现 |
| `sse` | Server-Sent Events | 远程 HTTP 服务 | 不实现 |
| `sse-ide` | SSE（IDE 内部） | IDE 集成 | 不实现 |
| `http` | Streamable HTTP | 远程服务 | 不实现 |
| `ws` | WebSocket | 远程服务 | 不实现 |
| `ws-ide` | WebSocket（IDE 内部） | IDE 集成 | 不实现 |
| `sdk` | SDK 控制传输 | VSCode 扩展等 | 不实现 |

---

## 阶段3：连接建立

### 批量连接

`getMcpToolsCommandsAndResources()` 批量连接所有服务器：

1. **分区**：disabled 和 active
2. **分组**：本地（stdio/sdk）和远程（sse/http/ws）
3. **并行处理**：本地并发限制 3，远程并发限制 20

**每个服务器处理**：

1. 跳过 disbaled
2. 跳过认证缓存的需要认证（<15 分钟）
3. 调用 `connectToServer(name, config)`
4. 如果成功连接：并行获取 tools、prompts、resources、skills
5. 触发 `onConnectionAttempt()` 更新 AppState
6. 注册通知处理器（工具/提示词/资源的 list_changed 事件）

### 连接函数

```typescript
connectToServer(name, config) → ConnectedMCPServer
```

**stdio 传输**：
1. 特殊处理：Claude-in-Chrome → 进程内 InProcessTransport
2. 特殊处理：Computer Use → 进程内 InProcessTransport
3. 默认：StdioClientTransport，通过子进程 stdin/stdout 通信

**sse/http 传输**：
1. 创建 `ClaudeAuthProvider` 处理 OAuth
2. 获取自定义 headers
3. 创建 SSE/HTTP 传输

所有传输类型：
- 创建 `Client` 实例
- 注册 ListRootsRequest 处理器
- `Promise.race([client.connect(), timeoutPromise])` — 默认 30 秒超时
- 注册 onerror/onclose 处理器

### 连接状态

```
MCPServerConnection:
  'connected'   — 连接成功，有 client、capabilities、serverInfo
  'failed'      — 连接失败，有 error
  'needs-auth'  — 需要 OAuth 认证 [v1置空]
  'pending'     — 正在连接中
  'disabled'    — 已禁用
```

### 错误处理

- **UnauthorizedError (401)**：返回 `'needs-auth'`，写入 15 分钟 TTL 认证缓存
- **会话过期**（404 + -32001）：触发传输关闭 + 重新连接
- **终端错误**（ECONNRESET 等）：3 次连续错误后关闭传输
- **超时**：默认 30 秒（MCP_TIMEOUT 环境变量）

### 清理

1. stdio：`SIGINT` → `SIGTERM` → `SIGKILL` 升级（500ms）
2. 进程内：`inProcessServer.close()` → `client.close()`
3. 通过 `registerCleanup()` 注册优雅关闭

---

## 阶段4：工具发现

### 获取工具

```typescript
fetchToolsForClient(client) → Tool[]
```

从 MCP 服务器请求 `tools/list`，将每个 MCP 工具映射为 Claude Code 内部 `Tool` 对象：

1. 使用 `MCPTool` 模板（基础 Tool 定义）
2. **工具名称**：`mcp__<serverName>__<toolName>`
3. 名称规范化：`/[^a-zA-Z0-9_-]/g → '_'`
4. **描述**：来自 MCP 服务器元数据，截断至最大长度
5. **inputJSONSchema**：来自 MCP 服务器

### 工具池集成

- **添加**：连接时，所有工具以 `mcp__<server>__<tool>` 前缀加入 AppState 工具池
- **移除**：断开连接时，该服务器的所有工具通过前缀匹配移除
- **列表变更通知**：服务器发送 `notifications/tools/list_changed` 时，缓存失效并重新获取

### 额外工具

- **`ListMcpResourcesTool`**：任何服务器支持 resources 时添加
- **`ReadMcpResourceTool`**：任何服务器支持 resources 时添加
- **`McpAuthTool`** `[v1置空]`：服务器需要认证时添加

### 缓存层次

| 缓存 | 键 | 失效 |
|---|---|---|
| `connectToServer` | `name + config_hash` | `clearServerCache()` |
| `fetchToolsForClient` | `client.name` | `list_changed` 通知 |
| `fetchResourcesForClient` | `client.name` | `list_changed` 通知 |
| `fetchCommandsForClient` | `client.name` | `list_changed` 通知 |

---

## 阶段5：工具执行

```
MCPTool.call(args, context)
  |
  ├── emit progress: 'started'
  ├── ensureConnectedClient() — 检查连接是否有效
  ├── callMCPToolWithElicitationRetry() [v1置空]
  │   ├── client.callTool(tool, args, signal, onProgress)
  │   └── Elicitation 错误时：运行 hooks + 重试最多 3 次
  ├── emit progress: 'completed' / 'failed'
  └── return { data, mcpMeta }
```

### 执行特点

- **进度通知**：工具通过进度事件报告进度
- **Elicitation** `[v1置空]`：工具在运行时可以请求用户输入
- **URL Elicitation** `[v1置空]`：工具可以重定向到 OAuth URL
- **会话恢复**：HTTP 工具在会话过期时自动重试一次

### 结果收集

```
ToolResult:
  data: mcpResult.content           # MCP 工具输出内容
  mcpMeta:
    _meta: result._meta             # 元数据
    structuredContent: result.structuredContent  # 结构化内容
```

---

## 阶段6：OAuth 认证 `[v1置空]`

Claude Code 完整的 OAuth 流程：

1. **检查 XAA** — 如果启用跨应用访问则跳过同意页
2. **清除现有令牌** — 保留 step-up 范围
3. **找到可用端口** → 构建重定向 URI
4. **创建 OAuth 提供者** + 获取元数据
5. **启动本地 HTTP 服务器**（localhost 回调）
6. **打开浏览器** → 用户同意
7. **等待回调或手动粘贴**（远程会话）
8. **用授权码交换令牌**
9. **保存令牌** → 返回 AUTHORIZED

### 令牌管理

- **主动刷新**：5 分钟内过期的令牌触发刷新
- **临时锁定**：磁盘锁文件防止竞争
- **元数据发现**：`.well-known/openid-configuration` 动态发现

### XAA（跨应用访问）`[v1置空]`

企业 IdP 替代方案：
- `acquireIdpIdToken()` — 一次 OIDC 浏览器弹出
- `performCrossAppAccess()` — RFC 8693 令牌交换 + RFC 7523 JWT Bearer 授权

---

## 阶段7：Channel 通知 `[v1置空]`

Channel 服务器通过 `notifications/claude/channel` 推送消息到对话中。Gate 顺序：

```
能力声明 → 运行时 Gate（tengu_harbor）→ OAuth 授权
  → 组织策略（channelsEnabled: true）→ 会话 --channels 列表
  → 市场验证 → Allowlist 检查
```

### 权限中继

Channel 服务器也可以中继权限审批：
1. Claude Code 发送 `notifications/claude/channel/permission_request`
2. 服务器通过 channel（Telegram/Discord 等）将提示发送给用户
3. 用户回复 `yes tbxkq`
4. 服务器解析回复并发出 `notifications/claude/channel/permission`
5. Claude Code 匹配待处理请求并解析权限对话框

---

## v1 实际实现

general-agent v1 的 MCP 实现：

1. **仅 stdio 传输** — 支持本地命令行 MCP 服务器，自实现轻量 JSON-RPC 客户端，不依赖外部 MCP SDK
2. **工具发现和执行** — 完整的 initialize → notifications/initialized → tools/list → tools/call 流程
3. **连接管理** — 启动时批量并行连接，断线自动重连一次，退出时优雅关闭
4. **工具集成** — MCP 工具包装为 Tool 子类，命名 `mcp__<server>__<tool>`，注册到 ToolsRegistry，无缝接入现有 Agent 循环
5. **配置** — 项目 `.mcp.json` + 用户 `~/.general_agent/mcp_settings.json`，项目覆盖用户
6. **权限** — 默认只读，除非服务器声明 readOnlyHint=false
7. **不做** — OAuth、channel、远程传输（sse/http/ws）、IDE 传输、Plugins、Elicitation、资源/提示词发现、list_changed 通知

实现文件位于 `general_agent/mcp/`，共 6 个模块：
- `types.py` — MCPServerConfig, MCPToolDef 数据类
- `config.py` — 配置加载（项目 .mcp.json + 用户设置）
- `transport.py` — JSON-RPC stdio 传输层（asyncio 子进程）
- `client.py` — MCP 协议客户端（握手、发现、调用、重连）
- `tool.py` — MCPTool 包装器（实现 Tool 基类）
- `__init__.py` — 公共 API（init_mcp_servers / shutdown_mcp）

---

## 与 Claude Code 源项目的差异说明

| 功能 | Claude Code | general-agent v1 | 原因 |
|---|---|---|---|
| OAuth 认证 | 完整（授权码 + XAA + 令牌管理） | 不做 | 只需 stdio |
| 远程传输 | SSE / HTTP / WebSocket | 不做 | 只需 stdio |
| Channel 集成 | Telegram / Discord | 不做 | 单一 CLI |
| IDE 集成 | sse-ide / ws-ide | 不做 | 单一 CLI |
| Plugin MCP | 插件配置 + 授权 | 不做 | 无插件系统 |
| Elicitation | URL + 表单模式，3 次重试 | 不做 | 基础工具即可 |
| 企业策略 | allowlist / denylist / managed only | 不做 | 个人使用 |
| 官方注册表 | claude.ai 连接器 | 不做 | 个人使用 |

---

> 最后更新: 2026-05-30 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/services/mcp/config.ts, client.ts, types.ts, auth.ts, src/tools/MCPTool/MCPTool.ts
