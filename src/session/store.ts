import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { CreateSessionInput, LoadedSession, SessionEvent, SessionRecord } from './types.js'

export class JsonlSessionStore {
  constructor(private rootDir: string) {}

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
    }
    await writeFile(this.sessionPath(record.id), `${JSON.stringify({ type: 'metadata', patch: record })}\n`, 'utf8')
    return record
  }

  async append(sessionId: string, event: SessionEvent) {
    await mkdir(this.rootDir, { recursive: true })
    await writeFile(this.sessionPath(sessionId), `${JSON.stringify(event)}\n`, {
      encoding: 'utf8',
      flag: 'a',
    })
  }

  async load(sessionId: string): Promise<LoadedSession> {
    const text = await readFile(this.sessionPath(sessionId), 'utf8')
    const events = text
      .split(/\r?\n/)
      .filter(Boolean)
      .map(line => JSON.parse(line) as SessionEvent)
    const record = buildRecord(sessionId, events)
    return {
      record,
      events,
      messages: events.flatMap(event => event.type === 'message' ? [event.message] : []),
      tasks: events.flatMap(event => event.type === 'task_state' ? [event.task] : []),
    }
  }

  async list(): Promise<SessionRecord[]> {
    await mkdir(this.rootDir, { recursive: true })
    const files = await readdir(this.rootDir)
    const sessions = await Promise.all(
      files
        .filter(file => file.endsWith('.jsonl'))
        .map(file => this.load(file.replace(/\.jsonl$/, '')).then(loaded => loaded.record)),
    )
    return sessions.sort((a, b) => b.updatedAt - a.updatedAt)
  }

  private sessionPath(sessionId: string) {
    return join(this.rootDir, `${sessionId}.jsonl`)
  }
}

function buildRecord(sessionId: string, events: SessionEvent[]): SessionRecord {
  const metadata = events.find(event => event.type === 'metadata') as
    | { type: 'metadata'; patch: Partial<SessionRecord> }
    | undefined
  const messages = events.filter(event => event.type === 'message')
  const lastMessage = messages.at(-1)
  const now = Date.now()
  return {
    id: sessionId,
    title: metadata?.patch.title ?? firstUserTitle(events) ?? 'Untitled session',
    cwd: metadata?.patch.cwd ?? process.cwd(),
    model: metadata?.patch.model ?? 'unknown',
    createdAt: metadata?.patch.createdAt ?? now,
    updatedAt: lastMessage?.type === 'message' ? lastMessage.message.createdAt : metadata?.patch.updatedAt ?? now,
    messageCount: messages.length,
  }
}

function firstUserTitle(events: SessionEvent[]) {
  const message = events.find(
    event => event.type === 'message' && event.message.role === 'user' && event.message.text.trim(),
  )
  if (message?.type !== 'message') return undefined
  const text = message.message.text.trim().replace(/\s+/g, ' ')
  return text.length > 80 ? `${text.slice(0, 77)}...` : text
}
