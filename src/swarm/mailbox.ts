// File-based mailbox for inter-agent communication
// Stores messages at: .general-agent/teams/{team}/inboxes/{agent}.json

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

export type MailboxMessage = {
  from: string
  text: string
  timestamp: string
  read: boolean
  summary?: string
}

function inboxPath(teamsDir: string, teamName: string, agentName: string): string {
  return join(teamsDir, teamName, 'inboxes', `${agentName}.json`)
}

async function ensureInboxDir(teamsDir: string, teamName: string): Promise<void> {
  await mkdir(join(teamsDir, teamName, 'inboxes'), { recursive: true })
}

/** Read all messages from an agent's inbox */
export async function readMailbox(
  teamsDir: string,
  teamName: string,
  agentName: string,
): Promise<MailboxMessage[]> {
  try {
    await ensureInboxDir(teamsDir, teamName)
    const raw = await readFile(inboxPath(teamsDir, teamName, agentName), 'utf8')
    if (!raw.trim()) return []
    return JSON.parse(raw) as MailboxMessage[]
  } catch {
    return []
  }
}

/** Read only unread messages, then mark them as read */
export async function readUnreadMessages(
  teamsDir: string,
  teamName: string,
  agentName: string,
): Promise<MailboxMessage[]> {
  const msgs = await readMailbox(teamsDir, teamName, agentName)
  const unread = msgs.filter(m => !m.read)
  if (unread.length > 0) {
    for (const m of unread) m.read = true
    await ensureInboxDir(teamsDir, teamName)
    await writeFile(inboxPath(teamsDir, teamName, agentName), JSON.stringify(msgs, null, 2), 'utf8')
  }
  return unread
}

/** Write a message to an agent's inbox (append) */
export async function writeToMailbox(
  teamsDir: string,
  teamName: string,
  agentName: string,
  msg: Omit<MailboxMessage, 'read' | 'timestamp'>,
): Promise<void> {
  await ensureInboxDir(teamsDir, teamName)
  const msgs = await readMailbox(teamsDir, teamName, agentName)
  msgs.push({
    ...msg,
    timestamp: new Date().toISOString(),
    read: false,
  })
  await writeFile(inboxPath(teamsDir, teamName, agentName), JSON.stringify(msgs, null, 2), 'utf8')
}

/** Broadcast a message to all team members */
export async function broadcastToTeam(
  teamsDir: string,
  teamName: string,
  from: string,
  memberNames: string[],
  text: string,
  summary?: string,
): Promise<void> {
  for (const name of memberNames) {
    if (name === from) continue // Don't send to self
    await writeToMailbox(teamsDir, teamName, name, { from, text, summary })
  }
}
