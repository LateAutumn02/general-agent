import { mkdir, open, readdir, readFile, stat, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { CreateSessionInput, LiteSessionFile, LoadedSession, SessionEvent, SessionFilter, SessionRecord } from './types.js'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** lite 模式下读取首尾的缓冲区大小 */
const LITE_READ_BUF_SIZE = 64 * 1024 // 64KB

/** 写队列刷新间隔 (ms) */
const WRITE_FLUSH_MS = 100

// ---------------------------------------------------------------------------
// UUID validation
// ---------------------------------------------------------------------------

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function isValidUuid(value: string): boolean {
  return UUID_RE.test(value)
}

// ---------------------------------------------------------------------------
// JSON field extraction (no full parse — works on truncated lines)
// ---------------------------------------------------------------------------

function extractJsonStringField(text: string, key: string): string | undefined {
  const patterns = [`"${key}":"`, `"${key}": "`]
  for (const pattern of patterns) {
    const idx = text.indexOf(pattern)
    if (idx < 0) continue
    const valueStart = idx + pattern.length
    let i = valueStart
    while (i < text.length) {
      if (text[i] === '\\') { i += 2; continue }
      if (text[i] === '"') {
        let raw = text.slice(valueStart, i)
        if (raw.includes('\\')) {
          try { raw = JSON.parse(`"${raw}"`) } catch { /* keep raw */ }
        }
        return raw
      }
      i++
    }
  }
  return undefined
}

function extractLastJsonStringField(text: string, key: string): string | undefined {
  const patterns = [`"${key}":"`, `"${key}": "`]
  let last: string | undefined
  for (const pattern of patterns) {
    let searchFrom = 0
    while (true) {
      const idx = text.indexOf(pattern, searchFrom)
      if (idx < 0) break
      const valueStart = idx + pattern.length
      let i = valueStart
      while (i < text.length) {
        if (text[i] === '\\') { i += 2; continue }
        if (text[i] === '"') {
          let raw = text.slice(valueStart, i)
          if (raw.includes('\\')) {
            try { raw = JSON.parse(`"${raw}"`) } catch { /* keep raw */ }
          }
          last = raw
          break
        }
        i++
      }
      searchFrom = i + 1
    }
  }
  return last
}

// ---------------------------------------------------------------------------
// First prompt extraction from head chunk
// ---------------------------------------------------------------------------

const SKIP_FIRST_PROMPT_PATTERN = /^(?:\s*<[a-z][\w-]*[\s>]|\[Request interrupted by user[^\]]*\])/
const COMMAND_NAME_RE = /<command-name>(.*?)<\/command-name>/

function extractFirstPrompt(head: string): string {
  const lines = head.split('\n')
  let commandFallback = ''

  for (const line of lines) {
    // Match the actual JSONL format: {"type":"message","message":{"role":"user","text":"..."}}
    if (!line.includes('"type":"message"')) continue

    try {
      const entry = JSON.parse(line) as Record<string, unknown>
      if (entry.type !== 'message') continue
      const message = entry.message as Record<string, unknown> | undefined
      if (!message) continue
      if (message.role !== 'user') continue

      const text = typeof message.text === 'string' ? message.text : ''
      if (!text.trim()) continue

      let result = text.replace(/\n/g, ' ').trim()

      // Skip slash-command messages but remember first as fallback
      const cmdMatch = COMMAND_NAME_RE.exec(result)
      if (cmdMatch) {
        if (!commandFallback) commandFallback = cmdMatch[1]!
        continue
      }

      // Format bash input with ! prefix
      const bashMatch = /<bash-input>([\s\S]*?)<\/bash-input>/.exec(result)
      if (bashMatch) return `! ${bashMatch[1]!.trim()}`

      if (SKIP_FIRST_PROMPT_PATTERN.test(result)) continue

      if (result.length > 200) {
        result = result.slice(0, 200).trim() + '…'
      }
      return result
    } catch {
      continue
    }
  }

  if (commandFallback) return commandFallback
  return ''
}

// ---------------------------------------------------------------------------
// Read head + tail of a file
// ---------------------------------------------------------------------------

async function readHeadAndTail(filePath: string, fileSize: number): Promise<{ head: string; tail: string }> {
  try {
    const fh = await open(filePath, 'r')
    try {
      const buf = Buffer.allocUnsafe(LITE_READ_BUF_SIZE)
      const headResult = await fh.read(buf, 0, LITE_READ_BUF_SIZE, 0)
      if (headResult.bytesRead === 0) return { head: '', tail: '' }
      const head = buf.toString('utf8', 0, headResult.bytesRead)

      const tailOffset = Math.max(0, fileSize - LITE_READ_BUF_SIZE)
      let tail = head
      if (tailOffset > 0) {
        const tailResult = await fh.read(buf, 0, LITE_READ_BUF_SIZE, tailOffset)
        tail = buf.toString('utf8', 0, tailResult.bytesRead)
      }
      return { head, tail }
    } finally {
      await fh.close()
    }
  } catch {
    return { head: '', tail: '' }
  }
}

async function readSessionLite(filePath: string): Promise<LiteSessionFile | null> {
  try {
    const fh = await open(filePath, 'r')
    try {
      const fileStat = await fh.stat()
      const buf = Buffer.allocUnsafe(LITE_READ_BUF_SIZE)
      const headResult = await fh.read(buf, 0, LITE_READ_BUF_SIZE, 0)
      if (headResult.bytesRead === 0) return null

      const head = buf.toString('utf8', 0, headResult.bytesRead)
      const tailOffset = Math.max(0, fileStat.size - LITE_READ_BUF_SIZE)
      let tail = head
      if (tailOffset > 0) {
        const tailResult = await fh.read(buf, 0, LITE_READ_BUF_SIZE, tailOffset)
        tail = buf.toString('utf8', 0, tailResult.bytesRead)
      }
      return { mtime: fileStat.mtime.getTime(), size: fileStat.size, head, tail }
    } finally {
      await fh.close()
    }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Parse helpers
// ---------------------------------------------------------------------------

function parseSessionEvents(text: string): SessionEvent[] {
  const events: SessionEvent[] = []
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue
    try {
      events.push(JSON.parse(line) as SessionEvent)
    } catch {
      // Skip bad lines — keep /resume resilient
    }
  }
  return events
}

function buildRecord(sessionId: string, events: SessionEvent[]): SessionRecord {
  const metadataEvent = events.find(
    (e): e is { type: 'metadata'; patch: Partial<SessionRecord> } => e.type === 'metadata',
  )
  const customTitleEvent = events.filter(e => e.type === 'custom_title').at(-1) as
    | { type: 'custom_title'; title: string }
    | undefined
  const messages = events.filter(e => e.type === 'message')
  const lastMessage = messages.at(-1)
  const now = Date.now()

  return {
    id: sessionId,
    title: customTitleEvent?.title ?? metadataEvent?.patch.title ?? firstUserTitle(events) ?? 'Untitled session',
    cwd: metadataEvent?.patch.cwd ?? process.cwd(),
    model: metadataEvent?.patch.model ?? 'unknown',
    createdAt: metadataEvent?.patch.createdAt ?? now,
    updatedAt:
      lastMessage?.type === 'message'
        ? lastMessage.message.createdAt
        : metadataEvent?.patch.updatedAt ?? now,
    messageCount: messages.length,
    fileSize: 0,
    isLite: false,
    isSidechain: false,
    firstPrompt: firstUserTitle(events) ?? '',
    customTitle: customTitleEvent?.title,
    fullPath: '',
  }
}

function firstUserTitle(events: SessionEvent[]) {
  const message = events.find(
    e => e.type === 'message' && e.message.role === 'user' && e.message.text.trim(),
  )
  if (message?.type !== 'message') return undefined
  const text = message.message.text.trim().replace(/\s+/g, ' ')
  return text.length > 80 ? `${text.slice(0, 77)}...` : text
}

/**
 * Build a SessionRecord from lite head+tail buffers (no full parse).
 * Extracts metadata via string patterns from the first and last 64KB.
 */
function buildRecordFromLite(
  sessionId: string,
  filePath: string,
  mtime: number,
  fileSize: number,
  head: string,
  tail: string,
): SessionRecord {
  const now = Date.now()
  const firstPrompt = extractFirstPrompt(head)
  const customTitle = extractLastJsonStringField(tail, 'title') // from metadata patch
  const model = extractJsonStringField(head, 'model') ?? 'unknown'
  const cwd = extractJsonStringField(head, 'cwd') ?? process.cwd()
  const gitBranch = extractLastJsonStringField(tail, 'gitBranch')
  const isSidechain = false

  // Count messages: scan head and tail for "type":"message" lines
  // Dedup: if file is small enough that head+tail overlap, count only once
  const headCount = (head.match(/"type"\s*:\s*"message"/g) ?? []).length
  const tailCount = (tail.match(/"type"\s*:\s*"message"/g) ?? []).length
  let messageCount: number
  if (fileSize <= LITE_READ_BUF_SIZE) {
    // Entire file fits in head; tail is same as head
    messageCount = headCount
  } else if (fileSize <= LITE_READ_BUF_SIZE * 2) {
    // Head+tail might overlap; estimate from tail (newer messages) + scale
    messageCount = Math.max(headCount, tailCount)
  } else {
    // Large file, head and tail don't overlap; estimate total
    messageCount = headCount + tailCount
  }

  const title = customTitle ?? firstPrompt ?? 'Untitled session'

  // Try to extract createdAt from metadata in head
  let createdAt = now
  const metaMatch = /"createdAt"\s*:\s*(\d+)/.exec(head)
  if (metaMatch) createdAt = Number(metaMatch[1])

  return {
    id: sessionId,
    title: title.length > 200 ? title.slice(0, 197) + '…' : title,
    cwd,
    model,
    createdAt,
    updatedAt: mtime,
    messageCount,
    fileSize,
    isLite: true,
    isSidechain,
    firstPrompt: firstPrompt ?? '',
    customTitle,
    gitBranch,
    fullPath: filePath,
  }
}

// ---------------------------------------------------------------------------
// Write queue — batches appends per session file
// ---------------------------------------------------------------------------

type WriteEntry = { event: SessionEvent; resolve: () => void }

export class JsonlSessionStore {
  private rootDir: string
  private writeQueues = new Map<string, WriteEntry[]>()
  private flushTimers = new Map<string, ReturnType<typeof setTimeout>>()
  /** 尚未物化到磁盘的会话记录（懒创建） */
  private pendingSessions = new Map<string, SessionRecord>()

  constructor(rootDir: string) {
    this.rootDir = rootDir
  }

  // ---- Session lifecycle ----

  /**
   * 创建会话记录（不立即创建 JSONL 文件）。
   * 文件在第一次 append() 时才物化到磁盘。
   */
  async create(input: CreateSessionInput): Promise<SessionRecord> {
    await mkdir(this.rootDir, { recursive: true })
    const now = Date.now()
    const record: SessionRecord = {
      id: crypto.randomUUID(),
      title: input.title ?? 'New session',
      cwd: input.cwd,
      model: input.model,
      createdAt: now,
      updatedAt: now,
      messageCount: 0,
      fileSize: 0,
      isLite: false,
      isSidechain: false,
      firstPrompt: '',
      gitBranch: input.gitBranch,
      fullPath: this.sessionPath(crypto.randomUUID()), // placeholder
    }
    // Don't write to disk yet — lazy materialize on first append
    this.pendingSessions.set(record.id, record)
    return record
  }

  /**
   * 追加事件到会话 JSONL。
   * 如果文件尚未物化则先创建。
   * 使用批量写入队列（100ms 刷新）减少磁盘 I/O。
   */
  async append(sessionId: string, event: SessionEvent): Promise<void> {
    await mkdir(this.rootDir, { recursive: true })
    const filePath = this.sessionPath(sessionId)

    // If this session hasn't been materialized yet, create the file
    if (this.pendingSessions.has(sessionId)) {
      const record = this.pendingSessions.get(sessionId)!
      this.pendingSessions.delete(sessionId)
      // Write metadata as first line
      await writeFile(
        filePath,
        `${JSON.stringify({ type: 'metadata', patch: record })}\n`,
        'utf8',
      )
    }

    return new Promise<void>(resolve => {
      let queue = this.writeQueues.get(sessionId)
      if (!queue) {
        queue = []
        this.writeQueues.set(sessionId, queue)
      }
      queue.push({ event, resolve })

      if (!this.flushTimers.has(sessionId)) {
        this.flushTimers.set(
          sessionId,
          setTimeout(() => {
            void this.flushQueue(sessionId)
          }, WRITE_FLUSH_MS),
        )
      }
    })
  }

  private async flushQueue(sessionId: string): Promise<void> {
    this.flushTimers.delete(sessionId)
    const queue = this.writeQueues.get(sessionId)
    if (!queue || queue.length === 0) return
    this.writeQueues.delete(sessionId)

    const filePath = this.sessionPath(sessionId)
    const lines = queue.map(entry => JSON.stringify(entry.event)).join('\n') + '\n'

    try {
      await writeFile(filePath, lines, { encoding: 'utf8', flag: 'a' })
      for (const entry of queue) entry.resolve()
    } catch {
      // ENOENT — ensure directory exists and retry
      await mkdir(this.rootDir, { recursive: true })
      await writeFile(filePath, lines, { encoding: 'utf8', flag: 'a' })
      for (const entry of queue) entry.resolve()
    }
  }

  /**
   * 强制刷新指定会话的写入队列。
   * 在退出或切换会话前调用以确保数据不丢失。
   */
  async flush(sessionId: string): Promise<void> {
    if (this.flushTimers.has(sessionId)) {
      clearTimeout(this.flushTimers.get(sessionId))
      await this.flushQueue(sessionId)
    }
  }

  // ---- Reading ----

  /**
   * 完整加载一个会话（读取全文件，解析所有事件，构建消息链）。
   */
  async load(sessionId: string): Promise<LoadedSession> {
    const filePath = this.sessionPath(sessionId)
    try {
      const text = await readFile(filePath, 'utf8')
      const events = parseSessionEvents(text)
      const record = buildRecord(sessionId, events)
      record.fullPath = filePath
      record.isLite = false
      return {
        record,
        events,
        messages: buildMessageChain(events),
        tasks: events.flatMap(e => (e.type === 'task_state' ? [e.task] : [])),
      }
    } catch {
      throw new Error(`Session not found: ${sessionId}`)
    }
  }

  /**
   * 列出会话（lite 模式）。
   * 只读取每个 JSONL 文件的首尾 64KB 提取元数据，不加载完整消息体。
   * 按 updatedAt 降序排列。
   */
  async list(filter: SessionFilter = {}): Promise<SessionRecord[]> {
    await mkdir(this.rootDir, { recursive: true })
    let files: string[]
    try {
      files = await readdir(this.rootDir)
    } catch {
      return []
    }

    const jsonlFiles = files.filter(f => f.endsWith('.jsonl'))
    const limit = filter.limit ?? 50

    // Phase 1: stat all files (no content read)
    const fileStats: { name: string; mtime: number; size: number }[] = []
    for (const name of jsonlFiles) {
      try {
        const s = await stat(join(this.rootDir, name))
        if (s.size > 0) fileStats.push({ name, mtime: s.mtime.getTime(), size: s.size })
      } catch {
        // File vanished
      }
    }
    // Sort by mtime descending
    fileStats.sort((a, b) => b.mtime - a.mtime)
    const batch = fileStats.slice(0, limit)

    // Phase 2: read head+tail 64KB for each, extract metadata
    const records: SessionRecord[] = []
    for (const { name, mtime, size } of batch) {
      const sessionId = name.replace(/\.jsonl$/, '')
      const filePath = join(this.rootDir, name)

      try {
        const { head, tail } = await readHeadAndTail(filePath, size)
        if (!head && !tail) continue

        const record = buildRecordFromLite(sessionId, filePath, mtime, size, head, tail)

        // Apply filters
        if (filter.cwd && record.cwd !== filter.cwd) continue
        if (filter.gitBranch && record.gitBranch && record.gitBranch !== filter.gitBranch) continue
        if (record.isSidechain) continue

        records.push(record)
      } catch {
        // Skip unreadable files
      }
    }

    return records
  }

  /**
   * 按 UUID 在所有项目目录中查找会话。
   * 当 enriched list 中找不到时（例如首条消息 >16KB 导致 firstPrompt 提取失败），
   * 用于 `/resume <uuid>` 的回退查找。
   */
  async getLastSessionLog(sessionId: string): Promise<SessionRecord | null> {
    const filePath = this.sessionPath(sessionId)
    try {
      const s = await stat(filePath)
      if (s.size === 0) return null
      const { head, tail } = await readHeadAndTail(filePath, s.size)
      return buildRecordFromLite(sessionId, filePath, s.mtime.getTime(), s.size, head, tail)
    } catch {
      return null
    }
  }

  // ---- Utilities ----

  private sessionPath(sessionId: string): string {
    return join(this.rootDir, `${sessionId}.jsonl`)
  }

  /**
   * 验证字符串是否为合法 UUID 格式。
   */
  static isValidUuid(value: string): boolean {
    return isValidUuid(value)
  }
}

// ---------------------------------------------------------------------------
// Message chain building
// ---------------------------------------------------------------------------

/**
 * 从事件列表构建有序消息链。
 * 优先使用 parentUuid 链回溯，回退到时间戳排序。
 */
function buildMessageChain(events: SessionEvent[]): import('./types.js').ChatMessage[] {
  const messageEvents = events.filter(
    (e): e is { type: 'message'; message: import('./types.js').ChatMessage } => e.type === 'message',
  )

  // If messages have parentUuid, build the chain
  const withParent = messageEvents.filter(e => e.message.parentUuid)
  if (withParent.length > 0) {
    return buildChainFromParents(messageEvents.map(e => e.message))
  }

  // Fallback: sort by createdAt
  return messageEvents
    .map(e => e.message)
    .sort((a, b) => (a.createdAt ?? 0) - (b.createdAt ?? 0))
}

function buildChainFromParents(
  messages: import('./types.js').ChatMessage[],
): import('./types.js').ChatMessage[] {
  const byId = new Map(messages.map(m => [m.id, m]))
  const byParent = new Map<string, import('./types.js').ChatMessage[]>()
  const roots: import('./types.js').ChatMessage[] = []

  for (const m of messages) {
    const parentId = m.parentUuid
    if (parentId && byId.has(parentId)) {
      let children = byParent.get(parentId)
      if (!children) {
        children = []
        byParent.set(parentId, children)
      }
      children.push(m)
    } else {
      roots.push(m)
    }
  }

  // Walk from roots through children, chronological within each level
  const result: import('./types.js').ChatMessage[] = []
  const visited = new Set<string>()

  function walk(msg: import('./types.js').ChatMessage) {
    if (visited.has(msg.id)) return
    visited.add(msg.id)
    result.push(msg)
    const children = byParent.get(msg.id) ?? []
    for (const child of children) {
      walk(child)
    }
  }

  // Sort roots by createdAt then walk
  for (const root of roots.sort((a, b) => (a.createdAt ?? 0) - (b.createdAt ?? 0))) {
    walk(root)
  }

  return result
}
