import { appendFile, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { JsonlSessionStore } from './store.js'

const root = await mkdtemp(join(tmpdir(), 'general-agent-sessions-'))
const store = new JsonlSessionStore(root)
const session = await store.create({ cwd: process.cwd(), model: 'test-model' })

await store.append(session.id, {
  type: 'message',
  message: {
    id: crypto.randomUUID(),
    role: 'user',
    text: 'hello session',
    createdAt: Date.now(),
  },
})

const loaded = await store.load(session.id)
if (loaded.messages.length !== 1) throw new Error('message was not loaded')
if (loaded.record.messageCount !== 1) throw new Error('message count mismatch')

const sessions = await store.list()
if (sessions.length !== 1 || sessions[0]?.id !== session.id) throw new Error('session list failed')

await appendFile(join(root, `${session.id}.jsonl`), 'not-json\n', 'utf8')
const loadedWithBadLine = await store.load(session.id)
if (loadedWithBadLine.messages.length !== 1) throw new Error('bad JSONL line should be ignored')

await writeFile(join(root, 'broken-session.jsonl'), '\uFFFD\n', 'utf8')
const sessionsWithBrokenFile = await store.list()
if (!sessionsWithBrokenFile.some(candidate => candidate.id === session.id)) {
  throw new Error('broken session file should not break listing')
}

await rm(root, { recursive: true, force: true })
console.log('session smoke ok')
