import { resolveProfile } from '../multi-agent/profiles.js'
import type { SwarmPlan } from './types.js'

export function createSwarmPlan(goal: string, memberNames: string[]): SwarmPlan {
  return {
    id: crypto.randomUUID(),
    goal,
    members: memberNames.map(name => ({
      id: crypto.randomUUID(),
      name,
      profile: resolveProfile(name),
      status: 'awaiting_input',
    })),
    dependencies: [],
    status: 'draft',
  }
}

export function startSwarm(plan: SwarmPlan): SwarmPlan {
  return {
    ...plan,
    status: 'running',
    members: plan.members.map(member => ({ ...member, status: 'running' })),
  }
}
