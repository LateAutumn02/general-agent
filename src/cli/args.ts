import { resolve } from 'node:path'
import type { RuntimeConfig } from '../config/runtimeConfig.js'

export type CliArgs = {
  prompt?: string
  print: boolean
  resume?: string | true
  model?: string
  cwd: string
  permissionMode?: RuntimeConfig['permissionMode']
  envFile?: string
  help: boolean
  raw: string[]
}

export function parseCliArgs(args: string[], defaultCwd: string): CliArgs {
  const parsed: CliArgs = {
    print: false,
    cwd: defaultCwd,
    help: false,
    raw: args,
  }
  const positionals: string[] = []

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index]
    if (!arg) continue

    if (arg === '--help' || arg === '-h') {
      parsed.help = true
    } else if (arg === '--print' || arg === '-p') {
      parsed.print = true
    } else if (arg === '--prompt') {
      parsed.prompt = readValue(args, index, arg)
      index += 1
    } else if (arg.startsWith('--prompt=')) {
      parsed.prompt = arg.slice('--prompt='.length)
    } else if (arg === '--resume' || arg === '-r') {
      const next = args[index + 1]
      if (next && !next.startsWith('-')) {
        parsed.resume = next
        index += 1
      } else {
        parsed.resume = true
      }
    } else if (arg === '--model') {
      parsed.model = readValue(args, index, arg)
      index += 1
    } else if (arg.startsWith('--model=')) {
      parsed.model = arg.slice('--model='.length)
    } else if (arg === '--cwd') {
      parsed.cwd = resolve(readValue(args, index, arg))
      index += 1
    } else if (arg.startsWith('--cwd=')) {
      parsed.cwd = resolve(arg.slice('--cwd='.length))
    } else if (arg === '--permission-mode') {
      parsed.permissionMode = readValue(args, index, arg) as RuntimeConfig['permissionMode']
      index += 1
    } else if (arg.startsWith('--permission-mode=')) {
      parsed.permissionMode = arg.slice('--permission-mode='.length) as RuntimeConfig['permissionMode']
    } else if (arg === '--env-file') {
      parsed.envFile = readValue(args, index, arg)
      index += 1
    } else if (arg.startsWith('--env-file=')) {
      parsed.envFile = arg.slice('--env-file='.length)
    } else {
      positionals.push(arg)
    }
  }

  if (!parsed.prompt && positionals.length > 0) {
    parsed.prompt = positionals.join(' ')
  }
  return parsed
}

export function helpText() {
  return [
    'general-agent',
    '',
    'Usage:',
    '  general-agent [prompt]',
    '  general-agent --print "summarize this repo"',
    '  general-agent --resume [session-id]',
    '',
    'Options:',
    '  --model <name>             Override model',
    '  --cwd <path>               Working directory',
    '  --env-file <path>          Load an additional env file',
    '  --permission-mode <mode>   default | acceptEdits | plan | bypassPermissions',
    '  --print, -p                Run without TUI and print the response',
    '  --resume, -r [id]          Resume latest session or a specific session',
    '  --help, -h                 Show this help',
  ].join('\n')
}

function readValue(args: string[], index: number, name: string) {
  const value = args[index + 1]
  if (!value) throw new Error(`${name} requires a value`)
  return value
}
