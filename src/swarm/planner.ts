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
      prompt: defaultPromptFor(name, goal),
      status: 'awaiting_input',
    })),
    dependencies: [],
    status: 'draft',
  }
}

export function createSwarmPlanFromGoal(goal: string): SwarmPlan {
  const members = goalNeedsImplementation(goal)
    ? ['researcher', 'coder', 'reviewer']
    : ['researcher', 'reviewer']
  return createSwarmPlan(goal, members)
}

export function startSwarm(plan: SwarmPlan): SwarmPlan {
  return {
    ...plan,
    status: 'running',
    members: plan.members.map(member => ({ ...member, status: 'running' })),
  }
}

function defaultPromptFor(name: string, goal: string) {
  if (name === 'researcher') return `Research context for: ${goal}`
  if (name === 'coder') return `Implement a scoped solution for: ${goal}`
  if (name === 'reviewer') return `Review risks, regressions, and missing tests for: ${goal}`
  return goal
}

function goalNeedsImplementation(goal: string) {
  return /\b(add|build|implement|fix|change|refactor)\b/i.test(goal) ||
    /(开发|实现|修复|修改|改造|重构)/.test(goal)
}
