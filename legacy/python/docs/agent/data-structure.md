# 数据结构

> 描述 general-agent Agent 系统中核心的数据结构。设计参考 Claude Code。

---

## State

每次循环迭代维护的对话状态。在 `continue` 时传递到下一轮，在压缩/恢复等自愈路径中重新构建。

```
State:
  messages: list              # 当前对话全部消息列表
  toolUseContext: dict        # 工具执行上下文（配置、文件缓存、权限等）
  turnCount: int              # 当前回合轮次计数
  autoCompactTracking: dict   # 自动压缩追踪状态
  maxOutputTokensRecoveryCount: int  # max_tokens 恢复次数（最多 3 次）
  maxOutputTokensOverride: int  # 手动覆盖的 max_tokens 值
  pendingToolUseSummary: str  # 上一轮工具调用摘要（异步生成，本轮 yield）
  stopHookActive: bool        # 是否激活了 stop hook
  hasAttemptedReactiveCompact: bool  # 本轮是否已尝试过响应式压缩
  transition: str             # 本轮 State 转换原因（如 compress/retry/collapse）
```

---

## Message 消息类型

对话中的每一条消息。按角色分为以下类型：

### user（用户消息）
```
UserMessage:
  role: 'user'
  content: list[ContentBlock]  # 文本 + 图片 + 工具结果等混合块
```

### assistant（AI 回复）
```
AssistantMessage:
  role: 'assistant'
  content: list[ContentBlock]  # 文本 + 工具调用等混合块
  stop_reason: str             # 'end_turn' | 'max_tokens' | 'tool_use'
  usage: dict                  # API 返回的 token 用量
    input_tokens: int
    output_tokens: int
  isApiErrorMessage: bool      # 是否为 API 错误消息
```

### system（系统消息）
```
SystemMessage:
  role: 'system'               # 或 'user'，以 user 角色注入保持 API 兼容
  content: str                 # 系统提示词、指令、上下文信息
```

### attachment（附件/注入）
```
AttachmentMessage:
  role: 'user'
  content: str                 # 文件内容、记忆、skill prompt 等注入文本
  attachment_type: str         # 'memory' | 'skill' | 'file' | 'hook'
```

### tool_result（工具结果）
```
ToolResultMessage:
  role: 'user'
  content: list[ToolResultBlock]  # tool_result 内容块
```

---

## ContentBlock 内容块

消息的 content 字段是 ContentBlock 数组，支持混合多种类型：

```
TextBlock:
  type: 'text'
  text: str

ImageBlock:
  type: 'image'
  source:
    type: 'base64'
    media_type: str            # 'image/png' | 'image/jpeg' 等
    data: str                  # base64 编码

ToolUseBlock:
  type: 'tool_use'
  id: str                      # 唯一标识，与 tool_result 配对
  name: str                    # 工具名
  input: dict                  # 工具参数

ToolResultBlock:
  type: 'tool_result'
  tool_use_id: str             # 对应的 ToolUseBlock.id
  content: str                 # 工具执行结果
  is_error: bool               # 是否为错误
```

---

## ToolUseContext 工具上下文

传递给每个工具 call() 的上下文对象：

```
ToolUseContext:
  # 配置
  options:
    commands: list[str]        # 可用命令列表
    tools: list                # 可用工具列表
    mainLoopModel: str         # 主循环模型名
    thinkingConfig: dict       # thinking 配置
    mcpClients: list           # MCP 连接
    agentDefinitions: list     # Agent 定义
    maxBudgetUsd: float        # 费用上限
    customSystemPrompt: str    # 自定义系统提示词
    appendSystemPrompt: str    # 附加系统提示词

  # 运行时状态
  abortController: AbortController  # 中止信号
  messages: list               # 当前全部消息
  agentId: str                 # 子 Agent ID（主线程为 None）

  # 文件状态
  readFileState: FileStateCache  # 文件读取缓存（LRU）

  # 对话状态（回调函数）
  getAppState() -> AppState           # 获取全局状态
  setAppState(fn) -> None              # 更新全局状态
  addNotification(notif) -> None      # 添加通知

  # 消息注入
  appendSystemMessage(msg) -> None    # 向对话注入系统消息
```

---

## AppState 全局状态

> 以下列出 Claude Code 源码中 AppState 的关键字段，按功能分组。标注 `[v1]` 的为 general-agent v1 需要的字段，其余 v1 暂不需要。

```
AppState:
  # === 核心配置（v1 需要）===
  [v1] toolPermissionContext:
    mode: 'default' | 'acceptEdits' | 'bypassPermissions'  # 权限模式
    alwaysAllowRules: dict     # 始终允许的规则
    alwaysDenyRules: dict      # 始终拒绝的规则
    alwaysAskRules: dict       # 始终询问的规则
  [v1] mainLoopModel: str      # 主循环使用的模型
  [v1] verbose: bool           # 是否详细输出模式
  [v1] settings: dict          # 全局用户设置（settings.json）
  [v1] sessionId: str          # 会话 ID

  # === MCP 集成（v1 可能需要）===
  [v1] mcp:
    tools: list                # MCP 工具列表
    clients: list              # MCP 连接列表
    commands: list             # MCP 命令
    resources: dict            # MCP 资源
    pluginReconnectKey: int    # 重连计数器

  # === Agent / 任务 ===
  [v1] tasks: dict             # 任务状态字典 { taskId: TaskState }
  agent: str                   # CLI --agent 指定的 agent
  agentDefinitions: dict       # Agent 定义结果
  agentNameRegistry: dict      # Agent 名称注册表

  # === 对话状态（v1 不需要）===
  statusLineText: str          # 状态栏文本（TUI 专用）
  expandedView: str            # 展开的面板（TUI 专用）
  isBriefOnly: bool            # 简洁模式
  notifications:               # 通知系统
    current: any
    queue: list

  # === 文件 / 历史 ===
  fileHistory: dict            # 文件历史快照
  todos: dict                  # 每个 agent 的待办事项

  # === 高级特性（v1 不需要，仅列概要）===
  # 远程/Bridge/插件/Computer Use/推测解码 等约 20 个字段省略
  # 完整定义见源文件 src/state/AppStateStore.ts:89-249
```

> general-agent v1 仅需要核心配置 + MCP + tasks 共约 12 个字段。

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/state/AppStateStore.ts:89-249
>
> Tool、ToolResult、PermissionResult 等工具相关数据结构详见 [tools/data-structure.md](../tools/data-structure.md)。
