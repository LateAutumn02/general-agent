import type { TaskState } from '../tasks/types.js'

export type AgentProfile = {
  name: string
  description: string
  systemPrompt: string
  allowedTools: string[]
}

export type AgentTask = TaskState & {
  type: 'agent'
  profile: AgentProfile
  parentSessionId: string
  prompt: string
  resultSummary?: string
}

export type AgentToolInput = {
  description: string
  prompt: string
  profile?: string
  allowedTools?: string[]
}
