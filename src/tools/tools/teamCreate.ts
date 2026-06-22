import { join } from 'node:path'
import type { ToolDefinition } from '../types.js'
import { writeTeamConfig, type TeamConfig } from '../../swarm/teamConfig.js'

type TeamCreateInput = {
  team_name: string
  description?: string
}

export const teamCreateTool: ToolDefinition<TeamCreateInput> = {
  name: 'TeamCreate',
  description: `Create a new team for coordinating multiple agents.

Use this when:
- The user asks to use a team, swarm, or group of agents
- A task needs parallel work by multiple agents
- Agents need to communicate with each other via SendMessage

Creates a team config file and corresponding task list.`,
  inputSchema: {
    type: 'object',
    required: ['team_name'],
    properties: {
      team_name: { type: 'string', description: 'Name for the new team' },
      description: { type: 'string', description: 'Team purpose (optional)' },
    },
  },
  readOnly: false,
  summarize(input) {
    return `TeamCreate: ${input.team_name}`
  },
  async checkPermission(input, context) {
    return {
      type: 'ask',
      reason: `Create team "${input.team_name}"?`,
      preview: { type: 'command', command: `TeamCreate: ${input.team_name}`, cwd: context.cwd },
    }
  },
  async execute(input, context) {
    const teamsDir = join(context.cwd, '.general-agent', 'teams')
    const config: TeamConfig = {
      name: input.team_name,
      description: input.description,
      createdAt: Date.now(),
      leadAgentId: `lead@${input.team_name}`,
      members: [{
        agentId: `lead@${input.team_name}`,
        name: 'main',
        agentType: 'general-purpose',
        joinedAt: Date.now(),
        cwd: context.cwd,
      }],
    }
    await writeTeamConfig(teamsDir, config)
    return {
      callId: '',
      ok: true,
      content: [
        `Team "${input.team_name}" created.`,
        `Members: 1 (main)`,
        `Now use Agent({ name, team_name }) to spawn teammates.`,
        `Teammates communicate via SendMessage({ to, message }).`,
      ].join('\n'),
    }
  },
}
