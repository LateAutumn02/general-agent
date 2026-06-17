# 数据结构

> 多 Agent 系统中 Agent、Task、消息的核心数据结构。v1 暂不实现。

---

## AgentDefinition

Agent 的元信息定义。三种子类型：

```
BaseAgentDefinition:
  agentType: str                       # Agent 唯一名称
  whenToUse: str                       # 何时使用此 Agent
  tools: list[str]                     # 工具白名单（或 ['*'] 全部）
  disallowedTools: list[str]           # 禁止的工具
  skills: list[str]                    # 预加载的 Skill 名称
  mcpServers: list                     # Agent 专用 MCP 服务器
  model: str                           # 模型覆盖（或 'inherit'）
  permissionMode: str                  # 权限模式覆盖
  maxTurns: int                        # 最大轮次限制
  background: bool                     # 是否始终后台运行
  initialPrompt: str                   # 首次用户轮次前注入的提示
  memory: 'user' | 'project' | 'local' # 持久记忆范围
  isolation: 'worktree' | 'remote'     # 隔离方式
  omitClaudeMd: bool                   # 省略 CLAUDE.md
  source: str                          # 定义来源
  getSystemPrompt() -> str             # 系统提示词生成闭包

BuiltInAgentDefinition:
  继承自 BaseAgentDefinition
  source: 'built-in'

CustomAgentDefinition:
  继承自 BaseAgentDefinition
  source: 'custom'                     # 来自 .md/.json 文件

PluginAgentDefinition:
  继承自 BaseAgentDefinition
  source: 'plugin'                     # 来自插件
```

---

## FORK_AGENT（特殊内置 Agent）

```
FORK_AGENT:
  agentType: 'fork'
  tools: ['*']                         # 全部工具
  maxTurns: 200
  model: 'inherit'                     # 继承父模型
  permissionMode: 'bubble'             # 权限冒泡到父终端
  source: 'built-in'
  getSystemPrompt() -> ''
```

---

## Task

所有异步工作的基类。

```
TaskType:
  'local_bash'        |                # 后台 Shell
  'local_agent'       |                # 后台子 Agent
  'remote_agent'      |                # 远程 CCR Agent
  'in_process_teammate'|               # 进程内队友
  'local_workflow'    |                # 后台 Workflow
  'monitor_mcp'       |                # MCP 监控
  'dream'                               # 离线反思

TaskStatus:
  'pending' | 'running' | 'completed' | 'failed' | 'killed'

TaskStateBase:
  id: str                              # 任务 ID（前缀 + 8 位 base36）
  type: TaskType                       # 任务类型
  status: TaskStatus                   # 当前状态
  description: str                     # 任务描述
  toolUseId: str                       # 关联的 tool_use ID
  startTime: int                       # 开始时间戳（毫秒）
  endTime: int                         # 结束时间戳（毫秒）
  totalPausedMs: int                   # 累计暂停时间
  outputFile: str                      # 输出文件路径
  outputOffset: int                    # 输出读取偏移
  notified: bool                       # 是否已通知用户

Task接口:
  name: str                            # 显示名称
  type: TaskType                       # 任务类型
  kill(taskId: str, setAppState: fn) -> Promise<void>  # 杀死任务
```

---

## LocalAgentTask

最常用的 Agent 任务状态（扩展 TaskStateBase）：

```
LocalAgentTaskState:
  继承自 TaskStateBase
  type: 'local_agent'

  # Agent 标识
  agentId: str                         # Agent 唯一 ID（agent-xxxxxxxx）
  agentType: str                       # Agent 类型名
  selectedAgent: AgentDefinition       # 选中的 Agent 定义
  model: str                           # 使用的模型

  # 任务内容
  prompt: str                          # 给 Agent 的任务描述

  # 执行控制
  abortController: AbortController     # 中止控制器
  unregisterCleanup: fn                # 清理回调

  # 结果
  error: str                           # 错误消息（如果失败）
  result: any                          # Agent 执行结果

  # 进度
  progress:
    toolUseCount: int                  # 工具使用次数
    tokenCount: int                    # Token 使用量
    lastActivity: str                  # 最近一个活动（工具描述/搜索/读取分类）
    recentActivities: list             # 最近 5 个活动

  # 消息
  messages: list[Message]             # Agent 完整消息历史
  pendingMessages: list[str]          # 排队中的 SendMessage 消息

  # 状态标志
  isBackgrounded: bool                 # 是否已转入后台
  retrieved: bool                      # 结果是否已被检索
  retain: bool                         # 是否保留（不驱逐）
  diskLoaded: bool                     # 是否已从磁盘加载

  # 通知
  lastReportedToolCount: int           # 上次报告的工具使用数
  lastReportedTokenCount: int          # 上次报告的 Token 数
```

---

## InProcessTeammateTask

多 Agent 协作者（进程内队友）：

```
InProcessTeammateTaskState:
  继承自 TaskStateBase
  type: 'in_process_teammate'

  # 身份
  identity:
    agentId: str                       # Agent ID
    agentName: str                     # Agent 显示名
    teamName: str                      # 团队名
    color: str                         # 颜色代码
    planModeRequired: bool             # 是否需要计划审批

  # 执行控制
  abortController: AbortController
  awaitingPlanApproval: bool           # 正在等待计划审批

  # 消息
  pendingUserMessages: list[str]       # 邮箱投递队列
  messages: list[Message]              # 消息历史（上限 50）

  # 空闲检测
  isIdle: bool                         # 是否空闲
  onIdleCallbacks: list[fn]            # 空闲时通知
```

---

## Agent Tool 输入输出

```
AgentInput:                            # Agent 工具调用参数
  description: str                     # 3-5 词任务描述
  prompt: str                          # 详细任务描述
  subagent_type: str                   # (可选) Agent 类型
  model: str                           # (可选) 模型覆盖
  run_in_background: bool              # (可选) 异步执行
  name: str                            # (可选) 队友名称
  team_name: str                       # (可选) 团队名称
  mode: str                            # (可选) 权限模式
  isolation: str                       # (可选) 隔离方式
  cwd: str                             # (可选) 工作目录覆盖

AgentResultSync:                       # 同步执行结果
  status: 'completed'
  agentId: str                         # Agent ID
  content: str                         # Agent 最终输出
  totalToolUseCount: int               # 总工具使用次数
  totalDurationMs: int                 # 总耗时
  totalTokens: int                     # 总 Token 使用量
  usage: dict                          # 详细使用情况

AgentResultAsync:                      # 异步启动结果
  status: 'async_launched'
  agentId: str                         # Agent ID
  description: str                     # 任务描述
  prompt: str                          # 任务提示词
  outputFile: str                      # 输出文件路径
  canReadOutputFile: bool              # 是否可以读取输出文件
```

---

## SendMessage 消息格式

```
SendMessageInput:
  to: str                              # 接收方名称（或 '*' 广播）
  summary: str                         # (可选) 消息摘要
  message: str | StructuredMessage      # 消息内容

StructuredMessage:
  type: str                            # 消息类型
  # ... 类型特定字段

Mailbox:
  messages: list[str]                  # 待处理消息
  lastChecked: int                     # 上次检查时间戳
```

---

## v1 简化

general-agent v1 **不实现**多 Agent 系统的任何数据结构。原因：
- 所有类型都依赖于多 Agent 基础设施（Agent Tool、Task 系统、邮箱通信）
- 在不实现多 Agent 的情况下这些数据结构没有意义
- 后续版本在引入 Agent Tool 和 Task 系统时同步定义

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/tools/AgentTool/loadAgentsDir.ts, src/Task.ts, src/tasks/LocalAgentTask/LocalAgentTask.tsx, src/tasks/InProcessTeammateTask/types.ts, src/tools/SendMessageTool/SendMessageTool.ts
