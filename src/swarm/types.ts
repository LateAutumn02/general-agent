import type { AgentProfile } from '../multi-agent/types.js'
import type { TaskStatus } from '../tasks/types.js'

export type SwarmStatus = 'draft' | 'running' | 'blocked' | 'completed' | 'failed'

export type SwarmMember = {
  id: string
  name: string
  profile: AgentProfile
  prompt: string
  taskId?: string
  status: TaskStatus
}

export type SwarmDependency = {
  fromMemberId: string
  toMemberId: string
  reason: string
}

export type SwarmPlan = {
  id: string
  goal: string
  members: SwarmMember[]
  dependencies: SwarmDependency[]
  status: SwarmStatus
}
