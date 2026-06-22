import { join } from 'node:path'
import type { ToolDefinition } from '../types.js'
import { addTeamMember, readTeamConfig } from '../../swarm/teamConfig.js'
import { readUnreadMessages } from '../../swarm/mailbox.js'

type AgentInput = {
  description: string
  prompt: string
  subagent_type?: string
  /** Agent name for SendMessage addressing and team registration */
  name?: string
  /** Team to join (requires TeamCreate first) */
  team_name?: string
}

export const agentTool: ToolDefinition<AgentInput> = {
  name: 'Agent',
  description: `Launch a new agent to handle complex, multi-step tasks autonomously.

Available agent types and the tools they have access to:
- general-purpose: Catch-all for any task. Default when no type specified. (Tools: Bash, Read, Write, Edit, Glob, Grep)
- Explore: Read-only search agent for broad fan-out searches. (Tools: Read, Glob, Grep)

Swarm mode: provide "name" and "team_name" to spawn a teammate that can receive messages via SendMessage.
- First use TeamCreate({ team_name }) to establish the team
- Then Agent({ name: "researcher", team_name: "my-team", ... }) to spawn teammates
- Teammates communicate via SendMessage({ to: "researcher", message: "..." })

When NOT to use: reading a specific file (use Read), searching for a class (use Glob/Grep).`,
  inputSchema: {
    type: 'object',
    required: ['description', 'prompt'],
    properties: {
      description: { type: 'string', description: 'A short (3-5 word) description of the task' },
      prompt: { type: 'string', description: 'The task for the agent to perform. Include file paths, context, and expected output format.' },
      subagent_type: { type: 'string', description: 'Agent type. Omit for general-purpose.' },
      name: { type: 'string', description: 'Name for the spawned agent. Makes it addressable via SendMessage({to: name}).' },
      team_name: { type: 'string', description: 'Team name. Uses current team if omitted. Requires TeamCreate first.' },
    },
  },
  readOnly: true,
  summarize(input) {
    return `Agent: ${input.description}`
  },
  async checkPermission(input, context) {
    const label = input.name ? `Agent ${input.name}@${input.team_name ?? 'default'}` : `Agent: ${input.description}`
    return {
      type: 'ask',
      reason: `Launch ${label}?`,
      preview: { type: 'command', command: label, cwd: context.cwd },
    }
  },
  async execute(input, context, call) {
    const agentType = input.subagent_type ?? 'general-purpose'
    const agentName = input.name
    const teamName = input.team_name ?? 'default'
    const teamsDir = join(context.cwd, '.general-agent', 'teams')

    // Register in team if name provided
    if (agentName) {
      try {
        const team = await readTeamConfig(teamsDir, teamName)
        if (team) {
          await addTeamMember(teamsDir, teamName, {
            agentId: `${agentName}@${teamName}`,
            name: agentName,
            agentType,
            joinedAt: Date.now(),
            cwd: context.cwd,
          })
        }
      } catch {
        // Team doesn't exist yet — agent still runs standalone
      }

      // Check mailbox for any prior messages
      const mailboxMsgs = await readUnreadMessages(teamsDir, teamName, agentName)
      if (mailboxMsgs.length > 0) {
        context.emit({
          type: 'swarm_inbox_read',
          teamName,
          agentName,
          messages: mailboxMsgs,
          createdAt: Date.now(),
        })
        // Inject mailbox messages into the agent's context
        const msgs = mailboxMsgs.map(m => `[@${m.from}] ${m.text}`).join('\n')
        input = { ...input, prompt: `${input.prompt}\n\n<inbox>\n${msgs}\n</inbox>` }
      }
    }

    if (context.startSubAgent && agentName) {
      const started = await context.startSubAgent({
        description: input.description,
        prompt: input.prompt,
        model: 'inherit',
        agentName,
        teamName,
        agentType,
      })
      return {
        callId: call.id,
        ok: true,
        content: [
          `Agent started in background: ${started.agentKey} (${agentType})`,
          `Description: ${input.description}`,
          `Progress and messages will appear in the swarm board.`,
        ].join('\n'),
      }
    }

    // Run the sub-agent via the caller's runner
    if (context.runSubAgent) {
      try {
        const result = await context.runSubAgent({
          description: input.description,
          prompt: input.prompt,
          model: 'inherit',
          agentName,
          teamName,
          agentType,
        })

        const output = agentName
          ? `[Agent ${agentName}@${teamName} (${agentType})]\n\n${result}`
          : result

        return { callId: call.id, ok: true, content: output }
      } catch (err) {
        return {
          callId: call.id,
          ok: false,
          content: `Agent failed: ${err instanceof Error ? err.message : String(err)}`,
          error: err instanceof Error ? err.message : String(err),
        }
      }
    }

    // No runner available
    return {
      callId: call.id,
      ok: true,
      content: [
        `Agent task queued (${agentType})${agentName ? ` as "${agentName}@${teamName}"` : ''}.`,
        `Description: ${input.description}`,
        `The agent will process: ${input.prompt.slice(0, 200)}...`,
      ].join('\n'),
    }
  },
}
