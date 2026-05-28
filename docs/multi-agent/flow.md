# 流程

> 多 Agent 系统的完整生命周期。从 Agent 定义、生成、执行到协调。v1 暂不实现。

---

## 系统概览

Claude Code 的多 Agent 系统提供三种 Agent 范式：

| 范式 | 触发方式 | 用途 | 生命周期 |
|---|---|---|---|
| **子 Agent** | LLM 调用 Agent 工具 | 委派独立任务（搜索、探索、验证） | 创建 → 执行 → 完成/失败 |
| **Fork 子 Agent** | 省略 subagent_type，启用 fork gate | 并行执行多个独立任务，共享上下文缓存 | 分叉 → 并行执行 → 合并结果 |
| **协调者模式** | 环境变量 `CLAUDE_CODE_COORDINATOR_MODE=1` | 协调者 + 多个 worker Agent 协作 | 研究 → 综合 → 实现 → 验证 |

---

## 阶段1：Agent 定义

Agent 定义描述了 Agent 的元信息、工具集、模型和系统提示词。

### Agent 定义类型

```
AgentDefinition:
  agentType: str            # 唯一名称（如 "general-purpose"、"Explore"）
  whenToUse: str            # 何时应选择此 Agent
  tools: list[str]          # 工具白名单（或 ['*'] 全部）
  disallowedTools: list[str]  # 禁止的工具
  skills: list[str]         # 预加载的 Skill 名称
  mcpServers: list          # Agent 专用 MCP 服务器
  model: str                # 模型覆盖（或 'inherit'）
  permissionMode: str       # 权限模式覆盖
  maxTurns: int             # 最大轮次限制
  background: bool          # 是否始终后台运行
  initialPrompt: str        # 首次用户轮次前注入的提示
  memory: str               # 持久记忆范围（'user' | 'project' | 'local'）
  isolation: str            # 隔离方式（'worktree' | 'remote'）
  omitClaudeMd: bool        # 省略 CLAUDE.md（只读 Agent）
  getSystemPrompt(params) -> str  # 系统提示词生成函数
```

### 定义来源与优先级

1. **`getAgentDefinitionsWithOverrides(cwd)`** — memoized by cwd

**加载顺序**（高优先级覆盖低优先级）：

```
built-in > plugin > userSettings > projectSettings > flagSettings > policySettings
```

**内置 Agent**：
- `general-purpose` — 通用任务，始终可用
- `Explore` — 代码库探索（feature-gated）
- `Plan` — 任务规划（feature-gated）
- `Verification` — 验证任务（feature-gated）
- `StatuslineSetup` — 状态栏配置
- `ClaudeCodeGuide` — Claude Code 使用指南

**自定义 Agent**：通过 `.claude/agents/<name>/` 目录下的 markdown 文件定义。

### Agent 记忆

有 `memory` 属性的 Agent 在生成时获得持久 MEMORY.md 文件：
- `'user'` → `~/.claude/agent-memory/<agentType>/`
- `'project'` → `<project>/.claude/agent-memory/<agentType>/`

记忆提示词在生成时注入到 Agent 的系统提示词中。

---

## 阶段2：Agent 生成（Agent Tool）

LLM 通过调用 `Agent` 工具生成子 Agent：

### 输入参数

```
AgentInput:
  description: str          # 3-5 词任务描述
  prompt: str               # 给 Agent 的详细任务
  subagent_type: str        # (可选) Agent 类型，省略则 fork
  model: str                # (可选) 模型覆盖
  run_in_background: bool   # (可选) 异步执行
  name: str                 # (可选) 队友名称（多 Agent）
  team_name: str            # (可选) 团队名称（多 Agent）
  mode: str                 # (可选) 权限模式
  isolation: str            # (可选) 隔离方式
  cwd: str                  # (可选) 工作目录覆盖
```

### 生成路径分支

Agent 工具根据输入参数选择以下路径之一：

1. **多 Agent 生成** — `team_name` + `name` 存在
   - 通过 `spawnTeammate()` 创建独立的 Claude Code 进程
   - 支持 tmux/iTerm2 分屏或进程内运行
   - 通过邮箱系统（SendMessage）通信

2. **Fork 子 Agent** — 省略 `subagent_type` + fork gate 开启
   - 使用 `FORK_AGENT` 定义（工具 `['*']`，maxTurns 200，模型 `inherit`）
   - 子进程继承父进程的系统提示词和上下文
   - 生成缓存共享的 API 前缀（所有 fork 子进程的前缀字节相同）
   - 递归 fork 防护：fork 子进程不允许再次 fork（`querySource` 检查）

3. **远程隔离** — `isolation === 'remote'`（Ant 内部）
   - 创建 CCR 会话，注册为 `RemoteAgentTask`

4. **命名子 Agent** — 指定 `subagent_type`
   - 查询 `activeAgents` 查找定义
   - 验证 MCP 服务器可用性
   - 检查权限 deny 规则

### 同步 vs 异步决策

```
shouldRunAsync = (
  run_in_background === true ||
  agent.background === true ||
  isCoordinatorMode ||
  forkSubagentGate ||
  proactiveMode
) && !backgroundTasksDisabled
```

- **同步** — `runAgent()` 被 await，主循环阻塞直到子 Agent 完成
- **异步** — fire-and-forget，通过 `runWithAgentContext()` → `runAsyncAgentLifecycle()`，任务注册在 AppState，完成时排队通知

---

## 阶段3：Agent 执行引擎

**核心函数：`runAgent()`** — 异步生成器，yield Message 对象。

### 3.1 初始化设置

1. **解析模型** — `getAgentModel()`（可能继承父模型）
2. **创建 Agent ID** — `createAgentId()`，格式 `agent-xxxxxxxx`
3. **克隆文件状态** — `readFileState` 从父进程克隆（fork 共享）
4. **解析上下文**：
   - 用户/系统上下文（可选省略 CLAUDE.md 用于只读 Agent）
   - 权限模式（继承/覆盖/`shouldAvoidPermissionPrompts`）
5. **解析工具池** — `resolveAgentTools()` 或 `useExactTools`（fork）
   - `['*']` → 全部工具（过滤 disallowed 列表后）
   - 显式列表 → 针对可用工具解析
   - 异步 Agent → `ASYNC_AGENT_ALLOWED_TOOLS` 集合
   - Fork → 与父进程完全相同的工具池（缓存共享）
6. **构建系统提示词** — `getAgentSystemPrompt()`
7. **执行 SubagentStart hooks**
8. **预加载 Skills** — 从 agent frontmatter
9. **初始化 Agent 专用 MCP 服务器** — 与父进程去重
10. **构建 Agent 选项** — nonInteractive、thinking 禁用

### 3.2 上下文创建

`createSubagentContext()` 为子 Agent 创建隔离的 `ToolUseContext`：

- `readFileState` — 从父进程克隆
- `abortController` — 新子控制器链接到父（父 abort 传播）
- `getAppState` — 包装版（避免权限提示，除非共享 abortController）
- `setAppState` — 默认 no-op
- `UI 回调` — 全部 undefined
- `contentReplacementState` — 克隆用于缓存稳定性

### 3.3 执行循环

```
runAgent():
  for each turn:
    query(messages, systemPrompt, context, tools):
      ├── 转发 message_start 到父进程（TTFT/OTPS 指标）
      ├── 记录 assistant/user/progress/system:compact_boundary 消息
      └── yield 消息给调用方
```

### 3.4 清理

1. 断开 Agent 专用 MCP 服务器
2. 清除会话 hooks
3. 清理 prompt cache 追踪
4. 释放克隆的文件状态缓存
5. 清除 Agent 转录子目录
6. 从 AppState 移除 Agent 的 TodoWrite 条目
7. 杀死后台 bash 任务
8. 杀死监控 MCP 任务

---

## 阶段4：Task 系统

所有异步工作（Agent、Shell、Workflow）都作为 Task 追踪。

### Task 类型

| 类型 | 前缀 | 用途 |
|---|---|---|
| `local_bash` | `b` | 后台 shell |
| `local_agent` | `a` | 后台子 Agent |
| `remote_agent` | `r` | 远程 CCR Agent |
| `in_process_teammate` | `t` | 进程内队友 |
| `local_workflow` | `w` | 后台 Workflow |
| `monitor_mcp` | `m` | MCP 监控 |
| `dream` | `d` | 离线反思 |

### Task 生命周期

```
pending → running → completed
                  → failed
                  → killed
```

### Task ID 生成

`前缀` + `8 位随机 base36 字符`（例如 `agent-a3bf7k2q`）。
Task 输出写入磁盘上的符号链接。

### 进度追踪

`ProgressTracker` 累积：
- `toolUseCount` — 工具使用次数
- `latestInputTokens` — 最新输入 token
- `cumulativeOutputTokens` — 累计输出 token
- `recentActivities` — 最近 5 个活动（工具描述、搜索/读取分类）

### Agent 完成/失败通知

Agent 完成时通过 `<task-notification>` XML 排队通知：
- 任务描述、累计工具使用、token、耗时
- 写入的应用文件列表
- 调度到下一轮对话

---

## 阶段5：Fork 子 Agent（缓存共享）

Fork 是特殊模式——无需 `subagent_type`，fork gate 开启时，系统创建一个继承父上下文且共享缓存前缀的子 Agent。

### FORK_AGENT 定义

```
FORK_AGENT:
  agentType: 'fork'
  tools: ['*']
  maxTurns: 200
  model: 'inherit'
  permissionMode: 'bubble'  # 权限提示冒泡到父终端
  source: 'built-in'
```

### 缓存共享机制

`buildForkedMessages()` 确保所有 fork 子进程的 API 请求前缀字节相同：

```
[...parentHistory,
 assistant_with_tool_uses,
 user(placeholder_results + child_directive)]
```

- 父进程最后一个 assistant 消息的所有 tool_use 块被保留
- 所有 tool_result 使用相同占位符：`"Fork started — processing in background"`
- 只有最终每个子进程的指令文本块不同

### 子进程指令

- 子进程被指示不要生成自己的子 Agent（`querySource === 'agent:builtin:fork'` 时拒绝）
- 输出格式：`Scope:` / `Result:` / `Key files:` / `Files changed:` / `Issues:`
- 保持 500 词以内，简洁客观

---

## 阶段6：协调者模式（Coordinator）

通过 `CLAUDE_CODE_COORDINATOR_MODE=1` 启用。主 Agent 变为协调者，编排多个 worker Agent。

### 协调者系统提示词要点

1. **角色** — 协调者帮助用户，指导 worker，综合结果
2. **协调者工具** — Agent（生成 worker）、SendMessage（继续现有 worker）、TaskStop（停止运行中的 worker）
3. **Worker 工具** — 除 TeamCreate/TeamDelete/SendMessage/SyntheticOutput 外完整工具池
4. **工作流程阶段**：
   - **研究** — Worker 并行执行
   - **综合** — 协调者阅读发现结果，制定实现规范
   - **实现** — Worker 进行修改
   - **验证** — Worker 测试
5. **并发规则**：
   - 只读任务：自由并行
   - 写重任务：同一文件集任何时候只有一个
   - 验证可以与不同区域上的实现并行运行
6. **Worker 提示词编写** — 必须是自包含的（Worker 看不到对话）。先综合发现结果再指导后续工作。永远不要说"基于你的发现"
7. **继续 vs 生成** — 高上下文重叠的 Worker 用 SendMessage 继续；不相关任务或会污染的错误方法上下文则生成新的

---

## 阶段7：进程间通信（SendMessage）

多 Agent 系统通过邮箱系统进行进程间通信。

### 消息类型

1. **纯文本** — 写入接收方邮箱
2. **广播 `*`** — 发送给除发送方外的所有团队成员
3. **shutdown_request** — 请求队友关闭
4. **shutdown_response** — 队友批准/拒绝关闭
5. **plan_approval_response** — 团队领导批准/拒绝计划

### 子 Agent 路由

```
SendMessage({ to: "name", message: "..." })
  ├── 检查 agentNameRegistry 查找 name -> agentId 映射
  ├── 任务正在运行 → 通过 queuePendingMessage() 排队
  ├── 任务已停止 → 通过 resumeAgentBackground() 自动恢复
  └── 任务已驱逐 → 尝试从磁盘转录恢复
```

---

## Agent 恢复

`resumeAgentBackground()` 恢复已停止/驱逐的 Agent：

1. 从磁盘 JSONL + 元数据读取转录
2. 为缓存稳定性重构内容替换状态
3. 重新解析 Agent 定义（处理 fork vs 命名）
4. Fork：重构父系统提示词以实现缓存一致的恢复
5. 创建新任务，运行 `runAsyncAgentLifecycle()`

---

## v1 状态

多 Agent 系统在 general-agent v1 中**完全不实现**。原因：

- v1 目标是单 Agent、单轮对话的可用体验
- 多 Agent 系统依赖 Task 系统、Hook 系统、进程隔离、邮箱通信等复杂基础设施
- 这些子系统在单 Agent 场景下没有使用价值
- 后续版本在单 Agent 稳定后逐步引入

---

## 与 Claude Code 源项目的差异说明

| 功能 | Claude Code | general-agent v1 | 原因 |
|---|---|---|---|
| 子 Agent | 完整，6 个内置 + 自定义 + 插件 | 不实现 | 单 Agent 够用 |
| Fork 子 Agent | 缓存共享 + 并行 | 不实现 | 无并行需求 |
| 协调者模式 | 完整（研究→综合→实现→验证） | 不实现 | 单 Agent 够用 |
| Task 系统 | 7 种 Task 类型，完整生命周期 | 不实现 | 无异步任务 |
| 进程间通信 | SendMessage + 邮箱 + 广播 | 不实现 | 无多进程 |
| Agent 恢复 | 从磁盘转录恢复 | 不实现 | 无多轮 Agent |
| Agent 记忆 | 持久化 Agent MEMORY.md | 不实现 | 无多 Agent |
| 多 Agent 队友 | tmux/iTerm2 + 进程内 | 不实现 | 单人使用 |

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/tools/AgentTool/, src/tasks/, src/coordinator/, src/utils/forkedAgent.ts, src/Task.ts, src/tasks.ts
