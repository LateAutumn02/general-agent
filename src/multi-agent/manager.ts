import { TaskRegistry } from '../tasks/registry.js'
import type { AgentTask, AgentToolInput } from './types.js'
import { resolveProfile } from './profiles.js'

export class MultiAgentManager {
  constructor(private readonly taskRegistry: TaskRegistry) {}

  createAgentTask(input: AgentToolInput, parentSessionId: string): AgentTask {
    const profile = resolveProfile(input.profile)
    const task = this.taskRegistry.create({
      type: 'agent',
      title: input.description,
      activity: 'Queued agent task',
      status: 'awaiting_input',
    })
    return {
      ...task,
      type: 'agent',
      profile: {
        ...profile,
        allowedTools: input.allowedTools ?? profile.allowedTools,
      },
      parentSessionId,
      prompt: input.prompt,
    }
  }
}
