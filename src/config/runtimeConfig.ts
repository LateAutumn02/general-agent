export type RuntimeConfig = {
  cwd: string
  model: string
  provider: 'mock' | 'anthropic-compatible'
  apiKey?: string
  baseUrl?: string
  permissionMode: 'default' | 'acceptEdits' | 'plan' | 'bypassPermissions'
}

export function loadRuntimeConfig(args: string[], cwd: string): RuntimeConfig {
  const model = readArg(args, '--model') ?? process.env.ANTHROPIC_MODEL ?? process.env.GENERAL_AGENT_MODEL ?? 'mock'
  const permissionMode = readArg(args, '--permission-mode') as RuntimeConfig['permissionMode'] | undefined
  return {
    cwd,
    model,
    provider: process.env.ANTHROPIC_AUTH_TOKEN || process.env.ANTHROPIC_API_KEY
      ? 'anthropic-compatible'
      : 'mock',
    apiKey: process.env.ANTHROPIC_AUTH_TOKEN ?? process.env.ANTHROPIC_API_KEY,
    baseUrl: process.env.ANTHROPIC_BASE_URL,
    permissionMode: permissionMode ?? 'default',
  }
}

function readArg(args: string[], name: string) {
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : undefined
}
