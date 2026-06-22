// Swarm smoke test: Mailbox + TeamCreate + SendMessage + Agent integration

import { mkdtemp, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { readMailbox, writeToMailbox, readUnreadMessages } from './mailbox.js'
import { readTeamConfig, writeTeamConfig, addTeamMember, type TeamConfig } from './teamConfig.js'

const root = await mkdtemp(join(tmpdir(), 'ga-swarm-'))

// === Mailbox ===
await writeToMailbox(root, 'test-team', 'researcher', { from: 'main', text: 'Find SAM3 specs' })
await writeToMailbox(root, 'test-team', 'researcher', { from: 'main', text: 'Also check pricing' })

const allMsgs = await readMailbox(root, 'test-team', 'researcher')
if (allMsgs.length !== 2) throw new Error('FAIL: mailbox should have 2 msgs')
if (allMsgs[0]!.read) throw new Error('FAIL: messages should be unread by default')

const unread = await readUnreadMessages(root, 'test-team', 'researcher')
if (unread.length !== 2) throw new Error('FAIL: should have 2 unread')

// After readUnreadMessages, they should be marked read
const after = await readMailbox(root, 'test-team', 'researcher')
if (after.some(m => !m.read)) throw new Error('FAIL: all should be read')
console.log('PASS [1/4] Mailbox: read/write/readUnread')

// === TeamConfig ===
const config: TeamConfig = {
  name: 'audit-team',
  description: 'Security audit',
  createdAt: Date.now(),
  leadAgentId: 'lead@audit-team',
  members: [{ agentId: 'lead@audit-team', name: 'main', agentType: 'general-purpose', joinedAt: Date.now(), cwd: process.cwd() }],
}
await writeTeamConfig(root, config)
const loaded = await readTeamConfig(root, 'audit-team')
if (!loaded || loaded.name !== 'audit-team') throw new Error('FAIL: team not loaded')
if (loaded.members.length !== 1) throw new Error('FAIL: should have 1 member')

await addTeamMember(root, 'audit-team', { agentId: 'r1', name: 'researcher', agentType: 'Explore', joinedAt: Date.now(), cwd: process.cwd() })
const updated = await readTeamConfig(root, 'audit-team')
if (updated?.members.length !== 2) throw new Error('FAIL: should have 2 members')
if (!updated?.members.some(m => m.name === 'researcher')) throw new Error('FAIL: researcher not found')
console.log('PASS [2/4] TeamConfig: create/read/addMember')

// === Inter-agent communication ===
await writeToMailbox(root, 'audit-team', 'researcher', { from: 'main', text: 'Audit auth module', summary: 'Auth audit task' })
await writeToMailbox(root, 'audit-team', 'main', { from: 'researcher', text: 'Found 3 SQL injection risks in auth.ts', summary: 'Auth findings' })

const mainInbox = await readMailbox(root, 'audit-team', 'main')
const researcherInbox = await readMailbox(root, 'audit-team', 'researcher')
if (mainInbox.length !== 1) throw new Error('FAIL: main should have 1 msg from researcher')
if (researcherInbox.length !== 1) throw new Error('FAIL: researcher should have 1 msg from main')
if (!mainInbox[0]!.text.includes('SQL injection')) throw new Error('FAIL: main should see researcher findings')
console.log('PASS [3/4] Inter-agent communication via Mailbox')

// === Tool registry includes all three ===
import { createDefaultToolRegistry } from '../tools/registry.js'
const reg = createDefaultToolRegistry()
if (!reg.get('Agent')) throw new Error('FAIL: Agent missing')
if (!reg.get('SendMessage')) throw new Error('FAIL: SendMessage missing')
if (!reg.get('TeamCreate')) throw new Error('FAIL: TeamCreate missing')
console.log('PASS [4/4] All 3 swarm tools registered')

await rm(root, { recursive: true, force: true })
console.log('swarm smoke ok')
