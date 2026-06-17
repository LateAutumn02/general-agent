import type { ToolDefinition } from '../types.js'

type BashInput = {
  command: string
}

export const bashTool: ToolDefinition<BashInput> = {
  name: 'Bash',
  description: 'Run a shell command in the current project.',
  inputSchema: {
    type: 'object',
    required: ['command'],
    properties: { command: { type: 'string' } },
  },
  readOnly: false,
  async checkPermission(input, context) {
    return {
      type: 'ask',
      reason: `Allow shell command in ${context.cwd}?`,
      preview: { type: 'command', command: input.command, cwd: context.cwd },
    }
  },
  async execute(input, context, call) {
    const shell = await resolveShell(input.command)
    const proc = Bun.spawn(shell.command, {
      cwd: context.cwd,
      stdout: 'pipe',
      stderr: 'pipe',
      signal: context.signal,
    })
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ])
    const ok = exitCode === 0
    return {
      callId: call.id,
      ok,
      content: ok ? stdout || '(command completed)' : stderr || stdout || `exit ${exitCode}`,
      display: { type: 'command_output', stdout, stderr, exitCode },
      error: ok ? undefined : stderr || `exit ${exitCode}`,
    }
  },
  summarize(input, result) {
    if (!result) return `Running ${input.command}`
    return result.ok ? `Ran ${input.command}` : `Command failed: ${input.command}`
  },
}

async function resolveShell(command: string) {
  if (process.platform !== 'win32') {
    return { command: ['bash', '-lc', command] }
  }
  if (await commandExists('bash')) {
    return { command: ['bash', '-lc', command] }
  }
  return {
    command: ['powershell.exe', '-NoProfile', '-Command', toPowerShellCompatible(command)],
  }
}

async function commandExists(command: string) {
  const proc = Bun.spawn(['where.exe', command], {
    stdout: 'ignore',
    stderr: 'ignore',
  })
  return await proc.exited === 0
}

function toPowerShellCompatible(command: string) {
  return command.replace(/\s+&&\s+/g, '; ')
}
