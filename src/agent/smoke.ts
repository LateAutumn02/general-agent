import { mkdtemp, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { PermissionController } from '../permissions/controller.js'
import { JsonlSessionStore } from '../session/store.js'
import { MockModelClient } from './mockModel.js'
import { runAgentTurn } from './loop.js'
import type { AgentState } from './types.js'

const root = await mkdtemp(join(tmpdir(), 'general-agent-agent-'))
const store = new JsonlSessionStore(root)
const session = await store.create({ cwd: process.cwd(), model: 'mock' })
const state: AgentState = {
  sessionId: session.id,
  messages: [],
  turnCount: 0,
  cwd: process.cwd(),
  model: 'mock',
}

const textEvents = []
for await (const event of runAgentTurn({
  state,
  request: { id: crypto.randomUUID(), mode: 'prompt', text: 'hello', createdAt: Date.now() },
  modelClient: new MockModelClient(),
  sessionStore: store,
})) {
  textEvents.push(event.type)
}
if (!textEvents.includes('assistant_done')) throw new Error('assistant turn failed')

const shellEvents = []
for await (const event of runAgentTurn({
  state,
  request: { id: crypto.randomUUID(), mode: 'bash', text: 'echo agent-smoke', createdAt: Date.now() },
  modelClient: new MockModelClient(),
  permissionController: new PermissionController('default'),
  sessionStore: store,
  async decidePermission(permissionEvent) {
    const rule = permissionEvent.request.suggestions[0]
    if (!rule) return { type: 'allow', remember: false }
    return { type: 'allow', remember: true, rule }
  },
})) {
  shellEvents.push(event.type)
}
if (!shellEvents.includes('permission_request')) throw new Error('permission was not requested')
if (!shellEvents.includes('tool_call_finished')) throw new Error('tool was not run')

const loaded = await store.load(session.id)
if (loaded.messages.length < 2) throw new Error('session did not persist messages')

await rm(root, { recursive: true, force: true })
console.log('agent smoke ok')
