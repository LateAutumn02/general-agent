# 会话持久化数据结构

> 最后更新：2026-06-22

## 核心类型概览

```
SessionRecord     → 会话索引记录（列表展示用）
SessionEvent      → 写入 JSONL 的单个事件
SessionStore      → 存储层接口（create / append / load / list）
LoadedSession     → 从磁盘加载后的完整会话
LogOption         → 会话列表项（lite 模式，不含完整消息）
Entry             → JSONL 文件中一行的所有可能类型
Message (enhanced) → 完整消息（含 persistence 字段）
```

---

## SessionRecord

会话索引记录，用于 `/resume` 列表展示和 `--continue` 查找。

```ts
type SessionRecord = {
  /** 会话唯一标识，UUID v4 格式 */
  id: string

  /** 会话标题：customTitle 或 firstPrompt（截断到 200 字符） */
  title: string

  /** 会话启动时的当前工作目录 */
  cwd: string

  /** 使用的模型名称 */
  model: string

  /** 会话创建时间 (Unix ms) */
  createdAt: number

  /** 最后更新时间 (Unix ms) */
  updatedAt: number

  /** 会话中的消息总数 */
  messageCount: number

  /** JSONL 文件大小 (bytes) */
  fileSize: number

  /** 是否为 lite 加载（只有元数据，无完整 messages） */
  isLite: boolean

  /** 是否为 sidechain 会话（子 agent / fork 分支） */
  isSidechain: boolean

  /** 第一条有意义用户消息（用于未命名会话的标题） */
  firstPrompt: string

  /** 用户自定义标题（通过 inline rename 设置） */
  customTitle?: string

  /** 会话标签（用于 Tag 过滤） */
  tag?: string

  /** JSONL 文件的绝对路径 */
  fullPath: string

  /** Git 分支名 */
  gitBranch?: string

  /** 项目路径（sanitized 之前） */
  projectPath?: string

  /** Agent 名称 */
  agentName?: string

  /** Agent 颜色 */
  agentColor?: string

  /** Agent 配置名称 */
  agentSetting?: string

  /** coordinator / normal 模式 */
  mode?: 'coordinator' | 'normal'

  /** PR 链接信息 */
  prNumber?: number
  prUrl?: string
  prRepository?: string

  /** Leaf UUID（链终端消息的 uuid） */
  leafUuid?: string

  /** 会话摘要（compact 后生成） */
  summary?: string
}
```

---

## LogOption（扩展版）

扩展版 `LogOption` 是 `SessionRecord` 的超集，包含更多字段用于高级功能：

```ts
type LogOption = {
  // --- 基础字段（对应 SessionRecord） ---
  date: Date              // 创建时间
  messages: number        // 消息数
  fullPath: string        // JSONL 文件路径
  value: string           // sessionId
  created: Date
  modified: Date

  // --- 元数据（从 JSONL 头尾 64KB 提取） ---
  firstPrompt: string
  messageCount: number
  fileSize: number
  isSidechain: boolean
  isLite: boolean         // 是否只有元数据无完整消息
  sessionId: string

  // --- Agent 相关 ---
  teamName?: string
  agentName?: string
  agentColor?: string
  agentSetting?: string

  // --- Fork 链 ---
  leafUuid?: string

  // --- 会话摘要 ---
  summary?: string

  // --- 用户自定义 ---
  customTitle?: string
  tag?: string

  // --- 状态快照 ---
  fileHistorySnapshots?: FileHistorySnapshot[]
  attributionSnapshots?: AttributionSnapshotMessage[]
  contextCollapseCommits?: ContextCollapseCommitEntry[]
  contextCollapseSnapshot?: ContextCollapseSnapshotEntry

  // --- Git / 项目 ---
  gitBranch?: string
  projectPath?: string

  // --- PR ---
  prNumber?: number
  prUrl?: string
  prRepository?: string

  // --- 模式 ---
  mode?: 'coordinator' | 'normal'

  // --- Worktree ---
  worktreeSession?: PersistedWorktreeSession | null

  // --- 内容替换 ---
  contentReplacements?: ContentReplacementRecord[]
}
```

---

## SessionEvent

写入 JSONL 文件的单个事件。每行一条。

```ts
type SessionEvent =
  | { type: 'message'; message: ChatMessage }
  | { type: 'runtime_event'; event: RuntimeEvent }
  | { type: 'permission_decision'; requestId: string; decision: PermissionDecision }
  | { type: 'task_state'; task: TaskState }
  | { type: 'metadata'; patch: Partial<SessionRecord> }
```

### 对应的 JSONL 条目类型（Entry）

```ts
/** JSONL 文件中一行的所有可能类型 */
type Entry =
  | TranscriptMessage        // 普通对话消息（user / assistant）
  | SummaryMessage           // compact 摘要
  | CustomTitleMessage       // 自定义标题
  | AiTitleMessage           // AI 生成的标题
  | LastPromptMessage        // 最后一条 prompt
  | TaskSummaryMessage       // 任务摘要
  | TagMessage               // 标签
  | AgentNameMessage         // Agent 名称
  | AgentColorMessage        // Agent 颜色
  | AgentSettingMessage      // Agent 配置
  | PRLinkMessage            // PR 链接
  | FileHistorySnapshotMessage   // 文件历史快照
  | AttributionSnapshotMessage   // 代码归属快照
  | QueueOperationMessage    // 队列操作
  | SpeculationAcceptMessage // 推测接受
  | ModeEntry                // coordinator / normal
  | WorktreeStateEntry       // worktree 进入/退出
  | ContentReplacementEntry  // 内容替换
  | ContextCollapseCommitEntry   // 上下文折叠提交
  | ContextCollapseSnapshotEntry // 上下文折叠快照
```

---

## SerializedMessage / TranscriptMessage

带有持久化字段的增强消息类型：

```ts
type SerializedMessage = Message & {
  /** 写入时的当前工作目录 */
  cwd: string

  /** 用户类型（human / system / hook） */
  userType?: string

  /** 入口点标识 */
  entrypoint?: string

  /** 所属会话 ID */
  sessionId: string

  /** ISO 8601 时间戳 */
  timestamp: string

  /** 协议版本 */
  version: number

  /** 写入时的 git 分支 */
  gitBranch?: string

  /** 路径 slug（用于跨平台） */
  slug?: string
}

type TranscriptMessage = SerializedMessage & {
  /** 父消息 UUID（形成链表） */
  parentUuid: string

  /** 是否为 sidechain */
  isSidechain?: boolean

  /** Agent 标识信息 */
  agentId?: string
  teamName?: string
  agentName?: string
  agentColor?: string

  /** Prompt ID（用于追踪） */
  promptId?: string
}
```

---

## SessionStore

存储层接口定义：

```ts
type SessionStore = {
  /**
   * 创建新会话记录。
   * 不立即创建 JSONL 文件 — 文件在第一条消息写入时才创建（懒初始化）。
   */
  create(input: CreateSessionInput): Promise<SessionRecord>

  /**
   * 追加一个事件到会话 JSONL 文件。
   * 如果文件不存在则创建。
   * 批量写入：100ms 刷新周期，减少磁盘 I/O。
   */
  append(sessionId: string, event: SessionEvent): Promise<void>

  /**
   * 完整加载一个会话。
   * - 大文件（>5MB）：分块读取 + compact_boundary 裁剪
   * - 小文件：直接读取全文件
   * - 沿 parentUuid 链构建有序消息列表
   * - 恢复 tasks / metadata / permissions
   */
  load(sessionId: string): Promise<LoadedSession>

  /**
   * 列出会话记录（lite 模式）。
   * - 只读取 JSONL 文件的首尾 64KB 提取元数据
   * - 不加载完整消息体
   * - 支持分页（startIndex / count）
   * - 按 updatedAt 降序排列
   */
  list(filter: SessionFilter): Promise<SessionRecord[]>

  /**
   * 按 UUID 直接查找会话的完整文件路径。
   * 用于 `/resume <uuid>` 无法在 enriched logs 中找到时的回退查找。
   * 扫描所有项目目录。
   */
  getLastSessionLog(sessionId: string): Promise<LogOption | null>
}

type CreateSessionInput = {
  cwd: string
  model: string
  gitBranch?: string
}

type SessionFilter = {
  /** 限制返回数量 */
  limit?: number

  /** 分页起始位置 */
  startIndex?: number

  /** 仅返回指定 cwd 下的会话 */
  cwd?: string

  /** 包含所有项目的会话（跨项目模式） */
  allProjects?: boolean

  /** 额外的 worktree 路径 */
  worktreePaths?: string[]

  /** 仅返回指定 git 分支的会话 */
  gitBranch?: string

  /** 仅返回指定 tag 的会话 */
  tag?: string
}
```

---

## LoadedSession

从磁盘完整加载后的会话对象：

```ts
type LoadedSession = {
  /** 会话索引记录 */
  record: SessionRecord

  /** 所有 JSONL 事件（按写入顺序） */
  events: SessionEvent[]

  /** 有序对话消息列表（沿 parentUuid 链构建） */
  messages: ChatMessage[]

  /** 后台任务状态列表 */
  tasks: TaskState[]

  /** 文件历史快照 */
  fileHistorySnapshots?: FileHistorySnapshot[]

  /** 代码归属快照 */
  attributionSnapshots?: AttributionSnapshotMessage[]

  /** 内容替换记录 */
  contentReplacements?: ContentReplacementRecord[]

  /** 上下文折叠提交 */
  contextCollapseCommits?: ContextCollapseCommitEntry[]

  /** 上下文折叠快照 */
  contextCollapseSnapshot?: ContextCollapseSnapshotEntry

  /** Worktree 会话信息 */
  worktreeSession?: PersistedWorktreeSession | null
}
```

---

## ResumeLoadResult

从 `loadConversationForResume()` 返回的原始加载结果：

```ts
type ResumeLoadResult = {
  messages: Message[]
  fileHistorySnapshots?: FileHistorySnapshot[]
  attributionSnapshots?: AttributionSnapshotMessage[]
  contentReplacements?: ContentReplacementRecord[]
  contextCollapseCommits?: ContextCollapseCommitEntry[]
  contextCollapseSnapshot?: ContextCollapseSnapshotEntry
  sessionId: UUID | undefined
  agentName?: string
  agentColor?: string
  agentSetting?: string
  customTitle?: string
  tag?: string
  mode?: 'coordinator' | 'normal'
  worktreeSession?: PersistedWorktreeSession | null
  prNumber?: number
  prUrl?: string
  prRepository?: string
}
```

---

## ProcessedResume

经过 `processResumedConversation()` 处理后的恢复结果：

```ts
type ProcessedResume = {
  messages: Message[]
  fileHistorySnapshots?: FileHistorySnapshot[]
  contentReplacements?: ContentReplacementRecord[]
  agentName: string | undefined
  agentColor: AgentColorName | undefined
  restoredAgentDef: AgentDefinition | undefined
  initialState: AppState
}
```

---

## PersistedWorktreeSession

记录会话是否在 worktree 中运行：

```ts
type PersistedWorktreeSession = {
  originalCwd: string
  worktreePath: string
  worktreeName: string
  worktreeBranch: string
  originalBranch: string
  originalHeadCommit: string
  sessionId: string
  tmuxSessionName?: string
  hookBased?: boolean
}
```

---

## ResumeEntrypoint

追踪用户通过哪种方式触发恢复（用于分析统计）：

```ts
type ResumeEntrypoint =
  | 'slash_command_picker'    // 从 LogSelector 选择器中选择
  | 'slash_command_session_id' // 通过 UUID 直接恢复
  | 'slash_command_title'      // 通过标题精确匹配恢复
  | 'cli_resume'               // --resume CLI 参数
  | 'cli_continue'             // --continue CLI 参数
```

---

## 关键常量

```ts
/** lite 模式下读首尾的缓冲区大小 */
const LITE_READ_BUF_SIZE = 65536  // 64KB

/** 跳过 precompact 过滤的文件大小阈值 */
const SKIP_PRECOMPACT_THRESHOLD = 5 * 1024 * 1024  // 5MB

/** 正向读取用的分块大小 */
const TRANSCRIPT_READ_CHUNK_SIZE = 1024 * 1024  // 1MB

/** 路径 sanitize 最大长度（超长则截断 + hash） */
const MAX_SANITIZED_LENGTH = 200

/** 深度搜索每会话最大搜索文本量 */
const DEEP_SEARCH_MAX_TEXT_LENGTH = 50000

/** Fuse.js 模糊搜索阈值 */
const FUSE_THRESHOLD = 0.3

/** 深度搜索防抖延迟 */
const DEEP_SEARCH_DEBOUNCE_MS = 300
```

---

## 项目存储路径

```
.general-agent/
  projects/
    <sanitized_cwd>/           # 如 -Users-foo-my-project
      <sessionId>.jsonl         # 主会话转录
      <sessionId>/
        subagents/
          agent-<agentId>.jsonl   # 子 agent 转录
          agent-<agentId>.meta.json  # 子 agent 元数据
        remote-agents/
          remote-agent-<taskId>.meta.json  # 远程 agent 元数据
  history.jsonl                # 提示历史（独立于会话转录）
```
