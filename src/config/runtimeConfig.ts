export type RuntimeConfig = {
  cwd: string
  model: string
  provider: 'mock' | 'openai-compatible'
  apiKey?: string
  baseUrl?: string
  permissionMode: 'default' | 'acceptEdits' | 'plan' | 'bypassPermissions'
}

export function loadRuntimeConfig(args: string[], cwd: string): RuntimeConfig {
  const apiKey = process.env.DEEPSEEK_API_KEY
    ?? process.env.OPENAI_API_KEY
    ?? process.env.ANTHROPIC_AUTH_TOKEN
    ?? process.env.ANTHROPIC_API_KEY
  const baseUrl = process.env.DEEPSEEK_BASE_URL
    ?? process.env.OPENAI_BASE_URL
    ?? process.env.ANTHROPIC_BASE_URL
  const provider = apiKey ? 'openai-compatible' : 'mock'
  const model = readArg(args, '--model')
    ?? process.env.DEEPSEEK_MODEL
    ?? process.env.OPENAI_MODEL
    ?? process.env.ANTHROPIC_MODEL
    ?? process.env.GENERAL_AGENT_MODEL
    ?? (provider === 'openai-compatible' ? 'deepseek-v4-flash' : 'mock')
  const permissionMode = readArg(args, '--permission-mode') as RuntimeConfig['permissionMode'] | undefined
  return {
    cwd,
    model,
    provider,
    apiKey,
    baseUrl,
    permissionMode: permissionMode ?? 'default',
  }
}

function readArg(args: string[], name: string) {
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : undefined
}
