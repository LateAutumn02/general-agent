import { join } from 'node:path'
import type { ToolDefinition } from '../types.js'
import { broadcastToTeam, writeToMailbox } from '../../swarm/mailbox.js'
import { readTeamConfig } from '../../swarm/teamConfig.js'

type SendMessageInput = {
  to: string
  team_name?: string
  summary?: string
  message: string
}

export const sendMessageTool: ToolDefinition<SendMessageInput> = {
  name: 'SendMessage',
  description: `Send a message to another agent in the team.

Usage:
- SendMessage({ to: "researcher", message: "What did you find?" }) for a direct message
- SendMessage({ to: "*", message: "All done!" }) to broadcast to all teammates
- SendMessage({ to: "researcher", team_name: "my-team", message: "..." }) to target a specific team

Messages are delivered to the recipient's inbox and read on their next Agent turn.`,
  inputSchema: {
    type: 'object',
    required: ['to', 'message'],
    properties: {
      to: { type: 'string', description: 'Recipient: agent name, or "*" for broadcast' },
      team_name: { type: 'string', description: 'Team name. Defaults to the current agent team.' },
      summary: { type: 'string', description: 'Brief preview (5-10 words)' },
      message: { type: 'string', description: 'Message content' },
    },
  },
  readOnly: false,
  summarize(input) {
    return `SendMessage to ${input.to}`
  },
  async checkPermission(input, context) {
    return {
      type: 'ask',
      reason: `Send message to "${input.to}"?`,
      preview: { type: 'command', command: `SendMessage -> ${input.to}`, cwd: context.cwd },
    }
  },
  async execute(input, context, call) {
    const teamsDir = join(context.cwd, '.general-agent', 'teams')
    const teamName = input.team_name ?? context.teamName ?? 'default'
    const from = context.agentName ?? 'main'

    if (input.to === '*') {
      const team = await readTeamConfig(teamsDir, teamName)
      if (team) {
        await broadcastToTeam(
          teamsDir,
          teamName,
          from,
          team.members.map(member => member.name),
          input.message,
          input.summary,
        )
      }
      context.emit({
        type: 'swarm_message_sent',
        teamName,
        from,
        to: '*',
        summary: input.summary,
        text: input.message,
        broadcast: true,
        createdAt: Date.now(),
      })
      return {
        callId: call.id,
        ok: true,
        content: `Broadcast sent in team "${teamName}": "${input.message.slice(0, 100)}"`,
      }
    }

    await writeToMailbox(teamsDir, teamName, input.to, {
      from,
      text: input.message,
      summary: input.summary,
    })
    context.emit({
      type: 'swarm_message_sent',
      teamName,
      from,
      to: input.to,
      summary: input.summary,
      text: input.message,
      broadcast: false,
      createdAt: Date.now(),
    })

    return {
      callId: call.id,
      ok: true,
      content: `Message sent to "${input.to}" in team "${teamName}": "${input.message.slice(0, 100)}"`,
    }
  },
}
