# 多 Agent 数据结构

> 最后更新：2026-06-22 | 参考：reference/cc-haha/src/tools/AgentTool, loadAgentsDir, agentToolUtils

## 核心类型概览

```
AgentInput        → Agent Tool 的调用参数
AgentResult       → Agent Tool 的返回结果
AgentDefinition   → agent 类型定义（工具集 + 使用条件）
AgentProfile      → 简化版 agent 描述（当前项目使用）
AgentTask         → 后台 agent 任务状态
```

---

## AgentInput（Agent Tool 参数）

```ts
type AgentInput = {
  /** 3-5 词的简短任务描述 */
  description: string

  /** 给 agent 的完整任务指令（自包含，含文件路径、上下文） */
  prompt: string

  /** agent 类型标识符。omit = fork 自身 / general-purpose */
  subagent_type?: string

  /** 模型覆盖（sonnet | opus | haiku | fable）。omit = 继承父 agent */
  model?: string

  /** 后台运行，完成后自动通知 */
  run_in_background?: boolean

  /** 隔离模式："worktree" 创建临时 git worktree */
  isolation?: 'worktree'

  // ---- 蜂群模式参数（TeamCreate 后可用） ----
  /** agent 名称，用于 SendMessage({ to: name }) */
  name?: string

  /** 团队名 */
  team_name?: string

  /** 权限模式 */
  mode?: PermissionMode
}
```

---

## AgentResult（Agent Tool 返回值）

```ts
type AgentResult = {
  /** agent 的最终文本响应 */
  result: string

  /** fork agent 的转录输出文件路径 */
  output_file?: string

  /** token 使用统计 */
  usage?: {
    input_tokens: number
    output_tokens: number
  }

  /** agent ID（用于后续 SendMessage） */
  agentId?: string

  /** worktree 路径（如果用 worktree 隔离） */
  worktreePath?: string

  /** worktree 分支名 */
  worktreeBranch?: string
}
```

---

## AgentDefinition（cc-haha 完整版）

```ts
type AgentDefinition = {
  /** 标识符，对应 subagent_type 参数 */
  agentType: string

  /** 人类可读名称 */
  name: string

  /** 一句话描述 */
  description: string

  /** 何时使用此 agent */
  whenToUse: string

  /** 工具允许列表（undefined = 全部除 disallowed） */
  tools?: string[]

  /** 工具禁止列表 */
  disallowedTools?: string[]

  /** 默认模型 */
  model?: string

  /** MCP 服务器依赖 */
  mcpServers?: string[]

  /** 是否为内置 agent */
  builtIn?: boolean
}
```

### 内置 Agent 类型

```ts
const BUILTIN_AGENT_TYPES = {
  'general-purpose': {
    whenToUse: 'Catch-all for any task. Default when no agent type specified.',
    tools: undefined,  // 全部工具
  },
  'Explore': {
    whenToUse: 'Read-only search for broad fan-out searches',
    tools: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  },
  'Plan': {
    whenToUse: 'Software architect for designing implementation plans',
    tools: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  },
  'code-reviewer': {
    whenToUse: 'Review code for bugs, reuse, simplification',
    tools: ['Read', 'Glob', 'Grep', 'Write', 'Edit'],
  },
}
```

---

## AgentProfile（当前项目简化版）

```ts
type AgentProfile = {
  name: string
  description: string
  systemPrompt: string
  allowedTools: string[]
}
```

### 当前 Profile 定义

```ts
const PROFILES = {
  researcher: {
    name: 'researcher',
    description: 'Search and analyze code, documents, and web resources',
    systemPrompt: 'You are a research agent...',
    allowedTools: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  },
  coder: {
    name: 'coder',
    description: 'Write, edit, and refactor code',
    systemPrompt: 'You are a coding agent...',
    allowedTools: ['Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep'],
  },
  reviewer: {
    name: 'reviewer',
    description: 'Review code for correctness and quality',
    systemPrompt: 'You are a code reviewer...',
    allowedTools: ['Read', 'Glob', 'Grep'],
  },
  executor: {
    name: 'executor',
    description: 'Execute shell commands and scripts',
    systemPrompt: 'You are an execution agent...',
    allowedTools: ['Bash', 'Read'],
  },
}
```

---

## AgentTask

```ts
type AgentTask = TaskState & {
  type: 'agent'

  /** 使用的 agent profile */
  profile: AgentProfile

  /** 父 session ID */
  parentSessionId: string

  /** 任务完成后的结果摘要 */
  resultSummary?: string

  /** 传递给 agent 的 prompt */
  prompt: string

  /** 可用工具列表 */
  allowedTools: string[]
}
```

---

## 子 Agent 转录存储

```
~/.claude/
  projects/{sanitized_cwd}/
    {sessionId}.jsonl                      ← 主 agent 转录
    {sessionId}/
      subagents/
        agent-{agentId}.jsonl              ← 子 agent 转录
        agent-{agentId}.meta.json          ← 子 agent 元数据
```

子 agent 元数据：
```ts
type AgentMetadata = {
  agentType: string
  worktreePath?: string
  description: string
}
```

---

## 工具权限

```ts
/** 所有子 agent 全局禁止 */
const DISALLOWED_TOOLS = [
  'Agent',           // 防止递归
  'AskUserQuestion',
  'TaskStop',
  'EnterPlanMode',
  'ExitPlanMode',
]

/** 按 profile 的白名单 */
const PROFILE_TOOLS = {
  researcher: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  coder:      ['Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep'],
  reviewer:   ['Read', 'Glob', 'Grep'],
  executor:   ['Bash', 'Read'],
}
```
