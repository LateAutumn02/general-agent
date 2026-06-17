import { existsSync, readFileSync } from 'node:fs'
import { isAbsolute, join, resolve } from 'node:path'

export type RuntimeConfig = {
  cwd: string
  model: string
  provider: 'mock' | 'openai-compatible'
  apiKey?: string
  baseUrl?: string
  providerLabel: string
  timeoutMs: number
  turnTimeoutMs: number
  permissionMode: 'default' | 'acceptEdits' | 'plan' | 'bypassPermissions'
}

export function loadRuntimeConfig(args: string[], cwd: string): RuntimeConfig {
  const env = loadEnv(cwd, readArg(args, '--env-file'))
  const apiKey = readEnv(env, 'DEEPSEEK_API_KEY')
    ?? readEnv(env, 'OPENAI_API_KEY')
    ?? readEnv(env, 'ANTHROPIC_AUTH_TOKEN')
    ?? readEnv(env, 'ANTHROPIC_API_KEY')
  const baseUrl = readEnv(env, 'DEEPSEEK_BASE_URL')
    ?? readEnv(env, 'OPENAI_BASE_URL')
    ?? readEnv(env, 'ANTHROPIC_BASE_URL')
  const provider = apiKey ? 'openai-compatible' : 'mock'
  const providerLabel = apiKey
    ? readEnv(env, 'GENERAL_AGENT_PROVIDER') ?? inferProviderLabel(baseUrl)
    : 'mock'
  const model = readArg(args, '--model')
    ?? readEnv(env, 'DEEPSEEK_MODEL')
    ?? readEnv(env, 'OPENAI_MODEL')
    ?? readEnv(env, 'ANTHROPIC_MODEL')
    ?? readEnv(env, 'GENERAL_AGENT_MODEL')
    ?? (provider === 'openai-compatible' ? 'deepseek-v4-flash' : 'mock')
  const permissionMode = readArg(args, '--permission-mode') as RuntimeConfig['permissionMode'] | undefined
  const timeoutMs = Number(readArg(args, '--timeout-ms') ?? readEnv(env, 'GENERAL_AGENT_TIMEOUT_MS') ?? 45_000)
  const turnTimeoutMs = Number(
    readArg(args, '--turn-timeout-ms') ?? readEnv(env, 'GENERAL_AGENT_TURN_TIMEOUT_MS') ?? 90_000,
  )
  return {
    cwd,
    model,
    provider,
    apiKey,
    baseUrl,
    providerLabel,
    timeoutMs: Number.isFinite(timeoutMs) ? timeoutMs : 45_000,
    turnTimeoutMs: Number.isFinite(turnTimeoutMs) ? turnTimeoutMs : 90_000,
    permissionMode: permissionMode ?? 'default',
  }
}

function readArg(args: string[], name: string) {
  const index = args.indexOf(name)
  return index >= 0 ? args[index + 1] : undefined
}

function loadEnv(cwd: string, envFile?: string) {
  const env = { ...process.env }
  const paths = [
    join(cwd, '.env.local'),
    join(cwd, '.env'),
    envFile ? isAbsolute(envFile) ? envFile : resolve(cwd, envFile) : undefined,
  ].filter((path): path is string => Boolean(path))
  for (const path of paths) {
    if (!existsSync(path)) continue
    for (const [key, value] of Object.entries(parseEnv(readFileSync(path, 'utf8')))) {
      env[key] = value
    }
  }
  return env
}

function parseEnv(content: string) {
  const values: Record<string, string> = {}
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const equalsIndex = line.indexOf('=')
    if (equalsIndex < 1) continue
    const key = line.slice(0, equalsIndex).trim()
    const value = line.slice(equalsIndex + 1).trim().replace(/^["']|["']$/g, '')
    values[key] = value
  }
  return values
}

function readEnv(env: NodeJS.ProcessEnv, name: string) {
  const value = env[name]
  return value && value.trim() ? value.trim() : undefined
}

function inferProviderLabel(baseUrl?: string) {
  if (baseUrl?.includes('deepseek')) return 'deepseek'
  return 'openai-compatible'
}
