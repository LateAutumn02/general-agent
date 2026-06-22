// End-to-end swarm test: TeamCreate → Agent spawn → SendMessage → Mailbox → Agent re-spawn with inbox

import { mkdtemp, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { readMailbox, writeToMailbox, readUnreadMessages } from './mailbox.js'
import { readTeamConfig, writeTeamConfig, addTeamMember, type TeamConfig } from './teamConfig.js'
import { agentTool } from '../tools/tools/agent.js'
import { sendMessageTool } from '../tools/tools/sendMessage.js'

const root = await mkdtemp(join(tmpdir(), 'ga-e2e-'))
const teamsDir = join(root, '.general-agent', 'teams')
const cwd = root // simulate project root

const ctx = {
  cwd,
  signal: new AbortController().signal,
  sessionId: 'main-session',
  emit: () => {},
  runSubAgent: async (opts: { description: string; prompt: string; model: string }) => {
    // Mock model response
    if (opts.prompt.includes('SAM3')) {
      if (opts.prompt.includes('inbox')) {
        return 'UPDATE: Found additional info — SAM3 also supports CAN bus and has a built-in crypto engine. Total 5 findings.'
      }
      return 'SAM3 is an ARM Cortex-M3 microcontroller by Atmel/Microchip. Key features: 96KB SRAM, 256KB flash, USB, 12-bit ADC. 3 key findings.'
    }
    if (opts.prompt.includes('review')) {
      return 'Verified SAM3 findings: all correct. Additional note: SAM3X has Ethernet MAC.'
    }
    return `Completed: ${opts.description}`
  },
}

// === Phase 1: TeamCreate ===
const team: TeamConfig = {
  name: 'sam3-research',
  description: 'Research SAM3 microcontroller',
  createdAt: Date.now(),
  leadAgentId: 'lead@sam3-research',
  members: [{ agentId: 'lead@sam3-research', name: 'main', agentType: 'general-purpose', joinedAt: Date.now(), cwd }],
}
await writeTeamConfig(teamsDir, team)
console.log('[Phase 1] Team "sam3-research" created with 1 member (main)')

// === Phase 2: Spawn researcher agent ===
const r1 = await agentTool.execute(
  { description: 'Research SAM3', prompt: 'What is SAM3? List features.', name: 'researcher', team_name: 'sam3-research' },
  ctx,
  { id: 'call-1', name: 'Agent', input: {} as never, status: 'pending', createdAt: Date.now() },
)
if (!r1.ok) throw new Error(`FAIL: Agent spawn failed: ${r1.error}`)
if (!r1.content.includes('SAM3')) throw new Error('FAIL: researcher should return SAM3 info')
if (!r1.content.includes('researcher@sam3-research')) throw new Error('FAIL: should show agent identity')
console.log('[Phase 2] Researcher spawned, result:', r1.content.split('\n')[0])

// Verify team membership
const teamAfter = await readTeamConfig(teamsDir, 'sam3-research')
if (!teamAfter?.members.some(m => m.name === 'researcher')) throw new Error('FAIL: researcher not in team')
console.log('         Team now has', teamAfter.members.length, 'members:', teamAfter.members.map(m => m.name).join(', '))

// === Phase 3: Main sends follow-up to researcher via SendMessage ===
await writeToMailbox(teamsDir, 'sam3-research', 'researcher', {
  from: 'main',
  text: 'Can you also check if SAM3 supports CAN bus and crypto?',
  summary: 'Dig deeper on SAM3',
})
console.log('[Phase 3] Main sent message to researcher mailbox')

await sendMessageTool.execute(
  {
    to: 'researcher',
    team_name: 'sam3-research',
    message: 'Also verify low-power sleep mode support.',
    summary: 'Check sleep mode',
  },
  ctx,
  { id: 'call-send-1', name: 'SendMessage', input: {} as never, status: 'pending', createdAt: Date.now() },
)

// Verify mailbox delivery
const researcherInbox = await readMailbox(teamsDir, 'sam3-research', 'researcher')
if (researcherInbox.length !== 2) throw new Error('FAIL: mailbox delivery failed')
if (!researcherInbox[0]!.text.includes('CAN bus')) throw new Error('FAIL: wrong message content')
if (!researcherInbox[1]!.text.includes('sleep mode')) throw new Error('FAIL: SendMessage should target named team')
console.log('         Researcher inbox: 2 unread messages from main')

// === Phase 4: Re-spawn researcher — it reads inbox and responds ===
const r2 = await agentTool.execute(
  { description: 'Follow up on SAM3', prompt: 'Any updates on SAM3?', name: 'researcher', team_name: 'sam3-research' },
  ctx,
  { id: 'call-2', name: 'Agent', input: {} as never, status: 'pending', createdAt: Date.now() },
)
if (!r2.ok) throw new Error(`FAIL: re-spawn failed: ${r2.error}`)
if (!r2.content.includes('CAN bus')) throw new Error('FAIL: should mention CAN bus from inbox message')
if (!r2.content.includes('crypto engine')) throw new Error('FAIL: should mention crypto from inbox')

// After re-spawn, mailbox should be marked read
const afterRead = await readMailbox(teamsDir, 'sam3-research', 'researcher')
if (afterRead.some(m => !m.read)) throw new Error('FAIL: inbox should be marked read after agent reads it')
console.log('[Phase 4] Researcher re-spawned with inbox context — found CAN bus + crypto info')
console.log('         Inbox marked as read')

// === Phase 5: Spawn second agent (reviewer) to verify researcher ===
await agentTool.execute(
  { description: 'Verify SAM3 research', prompt: 'Verify: SAM3 ARM Cortex-M3, 96KB SRAM, 256KB flash, USB, ADC, CAN bus, crypto engine.', name: 'reviewer', team_name: 'sam3-research' },
  ctx,
  { id: 'call-3', name: 'Agent', input: {} as never, status: 'pending', createdAt: Date.now() },
)

const teamFinal = await readTeamConfig(teamsDir, 'sam3-research')
if (!teamFinal?.members.some(m => m.name === 'reviewer')) throw new Error('FAIL: reviewer not in team')
if (teamFinal.members.length !== 3) throw new Error('FAIL: team should have 3 members (main, researcher, reviewer)')
console.log('[Phase 5] Reviewer spawned — team now has 3 members:', teamFinal.members.map(m => `${m.name}(${m.agentType})`).join(', '))

// === Phase 6: Cross-agent messaging ===
await writeToMailbox(teamsDir, 'sam3-research', 'reviewer', {
  from: 'researcher',
  text: 'Hey reviewer, I found 5 items. Can you double-check #3 (USB support)?',
  summary: 'Verify USB finding',
})
await writeToMailbox(teamsDir, 'sam3-research', 'main', {
  from: 'reviewer',
  text: 'USB finding verified. SAM3X datasheet confirms full-speed USB 2.0 device.',
  summary: 'USB verified',
})

const mainMsgs = await readUnreadMessages(teamsDir, 'sam3-research', 'main')
const reviewerUnread = await readUnreadMessages(teamsDir, 'sam3-research', 'reviewer')

if (mainMsgs.length !== 1 || !mainMsgs[0]!.text.includes('USB finding verified')) throw new Error('FAIL: main should get reviewer message')
if (reviewerUnread.length !== 1 || !reviewerUnread[0]!.text.includes('USB support')) throw new Error('FAIL: reviewer should get researcher message')
console.log('[Phase 6] Cross-agent messaging works:')
console.log(`         researcher → reviewer: "${reviewerUnread[0]!.summary}"`)
console.log(`         reviewer → main: "${mainMsgs[0]!.summary}"`)

await rm(root, { recursive: true, force: true })
console.log('\ne2e swarm smoke ok')
