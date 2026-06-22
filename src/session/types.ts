import type { RuntimeEvent } from '../runtime/events.js'
import type { PermissionDecision } from '../permissions/types.js'
import type { TaskItem } from '../tui/types.js'

// ---------------------------------------------------------------------------
// ChatMessage — persisted message with parent chain
// ---------------------------------------------------------------------------

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  text: string
  createdAt: number

  /** 父消息 UUID（形成有序链表，加载时沿链回溯） */
  parentUuid?: string

  /** 写入时的 cwd */
  cwd?: string

  /** 所属 sessionId */
  sessionId?: string
}

// ---------------------------------------------------------------------------
// SessionRecord — session index entry for listing
// ---------------------------------------------------------------------------

export type SessionRecord = {
  id: string
  title: string
  cwd: string
  model: string
  createdAt: number
  updatedAt: number
  messageCount: number

  /** JSONL 文件大小 (bytes) */
  fileSize: number

  /** 是否只加载了元数据（lite 模式，未读取完整消息体） */
  isLite: boolean

  /** 是否为 sidechain 会话（子 agent / fork 分支） */
  isSidechain: boolean

  /** 第一条有意义用户消息（用于未命名会话的标题显示） */
  firstPrompt: string

  /** 用户自定义标题（通过 /rename 设置） */
  customTitle?: string

  /** Git 分支名 */
  gitBranch?: string

  /** JSONL 文件绝对路径 */
  fullPath: string
}

// ---------------------------------------------------------------------------
// SessionEvent — one line in the JSONL file
// ---------------------------------------------------------------------------

export type SessionEvent =
  | { type: 'message'; message: ChatMessage }
  | { type: 'runtime_event'; event: RuntimeEvent }
  | { type: 'permission_decision'; requestId: string; decision: PermissionDecision }
  | { type: 'task_state'; task: TaskItem }
  | { type: 'metadata'; patch: Partial<SessionRecord> }
  | { type: 'custom_title'; title: string }
  | { type: 'tag'; tag: string }

// ---------------------------------------------------------------------------
// Create / filter input types
// ---------------------------------------------------------------------------

export type CreateSessionInput = {
  cwd: string
  model: string
  title?: string
  gitBranch?: string
}

export type SessionFilter = {
  limit?: number
  cwd?: string
  allProjects?: boolean
  gitBranch?: string
}

// ---------------------------------------------------------------------------
// LoadedSession — result of a full session load
// ---------------------------------------------------------------------------

export type LoadedSession = {
  record: SessionRecord
  events: SessionEvent[]
  messages: ChatMessage[]
  tasks: TaskItem[]
}

// ---------------------------------------------------------------------------
// Lite read result
// ---------------------------------------------------------------------------

export type LiteSessionFile = {
  mtime: number
  size: number
  head: string
  tail: string
}

// ---------------------------------------------------------------------------
// Resume entrypoint tracking
// ---------------------------------------------------------------------------

export type ResumeEntrypoint =
  | 'picker'       // 从列表选择器中选择
  | 'session_id'   // 通过 UUID 直接恢复
  | 'title'        // 通过标题匹配恢复
  | 'cli_resume'   // --resume CLI 参数
  | 'cli_continue' // --continue CLI 参数
