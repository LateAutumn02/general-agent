import { mkdtemp, rm } from 'node:fs/promises'
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

await rm(root, { recursive: true, force: true })
console.log('session smoke ok')
