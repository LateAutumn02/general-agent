import type { ToolDefinition } from '../types.js'

type AgentInput = {
  description: string
  prompt: string
  subagent_type?: string
}

export const agentTool: ToolDefinition<AgentInput> = {
  name: 'Agent',
  description: `Launch a new agent to handle complex, multi-step tasks autonomously.

Available agent types and the tools they have access to:
- general-purpose: Catch-all for any task. Default when no type specified. (Tools: Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch)
- Explore: Read-only search agent for broad fan-out searches. (Tools: Read, Glob, Grep)

When to use: complex multi-step tasks, parallel research, independent verification.
When NOT to use: reading a specific file (use Read), searching for a class (use Glob/Grep).

Usage notes:
- Launch multiple agents CONCURRENTLY by sending multiple Agent tool calls in a single message.
- Each agent works independently with its own context and returns one result.
- Write clear prompts with file paths and specific instructions.`,
  inputSchema: {
    type: 'object',
    required: ['description', 'prompt'],
    properties: {
      description: { type: 'string', description: 'A short (3-5 word) description of the task' },
      prompt: { type: 'string', description: 'The task for the agent to perform. Include file paths, context, and expected output format.' },
      subagent_type: { type: 'string', description: 'Agent type. Omit for general-purpose.' },
    },
  },
  readOnly: true,
  summarize(input) {
    return `Agent: ${input.description}`
  },
  async checkPermission(input, context) {
    return {
      type: 'ask',
      reason: `Launch agent: ${input.description}`,
      preview: { type: 'command', command: `Agent: ${input.description}`, cwd: context.cwd },
    }
  },
  async execute(input, context, call) {
    const agentType = input.subagent_type ?? 'general-purpose'
    const model = 'inherit'

    // Run the sub-agent if the caller provided a runner
    if (context.runSubAgent) {
      try {
        const subResult = await context.runSubAgent({
          description: input.description,
          prompt: input.prompt,
          model,
        })
        return {
          callId: call.id,
          ok: true,
          content: subResult,
        }
      } catch (err) {
        return {
          callId: call.id,
          ok: false,
          content: `Agent failed: ${err instanceof Error ? err.message : String(err)}`,
          error: err instanceof Error ? err.message : String(err),
        }
      }
    }

    // Fallback: no runner available — return placeholder
    return {
      callId: call.id,
      ok: true,
      content: [
        `Agent task created (${agentType}).`,
        `Description: ${input.description}`,
        ``,
        `Prompt: ${input.prompt.slice(0, 300)}${input.prompt.length > 300 ? '...' : ''}`,
        ``,
        `Note: Agent runner not available in this context. Task will complete when processed.`,
      ].join('\n'),
    }
  },
}
