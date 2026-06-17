import type { AgentProfile } from './types.js'

export const builtInProfiles: AgentProfile[] = [
  {
    name: 'researcher',
    description: 'Searches and summarizes technical context.',
    systemPrompt: 'You are a focused research agent. Prefer concise evidence and source notes.',
    allowedTools: ['Read', 'Grep', 'Glob', 'Bash'],
  },
  {
    name: 'reviewer',
    description: 'Reviews changes for bugs, regressions, and missing tests.',
    systemPrompt: 'You are a senior code reviewer. Lead with concrete findings.',
    allowedTools: ['Read', 'Grep', 'Glob'],
  },
  {
    name: 'coder',
    description: 'Implements scoped code changes.',
    systemPrompt: 'You are a careful implementation agent. Keep changes small and verified.',
    allowedTools: ['Read', 'Grep', 'Glob', 'Edit', 'Write', 'Bash'],
  },
]

export function resolveProfile(name?: string) {
  return builtInProfiles.find(profile => profile.name === name) ?? builtInProfiles[0]!
}
