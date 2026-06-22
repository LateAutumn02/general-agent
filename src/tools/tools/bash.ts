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
    let timeoutId: Timer | undefined
    const proc = Bun.spawn(shell.command, {
      cwd: context.cwd,
      stdout: 'pipe',
      stderr: 'pipe',
      signal: context.signal,
    })

    // Timeout after 120s to prevent hanging forever
    const timeout = new Promise<never>((_, reject) =>
      timeoutId = setTimeout(() => {
        proc.kill()
        reject(new Error('Command timed out after 120s'))
      }, 120_000),
    )

    try {
      const [stdout, stderr, exitCode] = await Promise.race([
        Promise.all([
          new Response(proc.stdout).text(),
          new Response(proc.stderr).text(),
          proc.exited,
        ]),
        timeout,
      ])
      const ok = exitCode === 0
      return {
        callId: call.id,
        ok,
        content: ok ? stdout || '(command completed)' : stderr || stdout || `exit ${exitCode}`,
        display: { type: 'command_output', stdout, stderr, exitCode },
        error: ok ? undefined : stderr || `exit ${exitCode}`,
      }
    } catch (err) {
      return {
        callId: call.id,
        ok: false,
        content: err instanceof Error ? err.message : 'Command failed',
        error: err instanceof Error ? err.message : String(err),
      }
    } finally {
      if (timeoutId) clearTimeout(timeoutId)
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
  return {
    command: ['powershell.exe', '-NoProfile', '-Command', toPowerShellCompatible(command)],
  }
}

function toPowerShellCompatible(command: string) {
  return command.replace(/\s+&&\s+/g, '; ')
}
