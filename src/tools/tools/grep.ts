import { readdir, readFile, stat } from 'node:fs/promises'
import { join } from 'node:path'
import type { ToolDefinition } from '../types.js'

type GrepInput = {
  pattern: string
  path?: string
}

export const grepTool: ToolDefinition<GrepInput> = {
  name: 'Grep',
  description: 'Search text files for a pattern.',
  inputSchema: {
    type: 'object',
    required: ['pattern'],
    properties: { pattern: { type: 'string' }, path: { type: 'string' } },
  },
  readOnly: true,
  async checkPermission(input, context) {
    return {
      type: 'allow',
      reason: `Search ${input.path ?? context.cwd} for ${input.pattern}`,
    }
  },
  async execute(input, context, call) {
    const root = join(context.cwd, input.path ?? '.')
    const regex = new RegExp(input.pattern, 'i')
    const matches: string[] = []
    await scan(root, context.cwd, regex, matches)
    return {
      callId: call.id,
      ok: true,
      content: matches.join('\n') || '(no matches)',
      display: { type: 'text', text: matches.join('\n') },
    }
  },
  summarize(input, result) {
    if (!result) return `Searching for ${input.pattern}`
    return `Searched for ${input.pattern}: ${result.content.split('\n').filter(Boolean).length} matches`
  },
}

async function scan(path: string, cwd: string, regex: RegExp, matches: string[]) {
  if (matches.length >= 200) return
  let info
  try {
    info = await stat(path)
  } catch {
    return
  }

  if (info.isDirectory()) {
    if (path.includes('node_modules') || path.includes('.git')) return
    const entries = await readdir(path)
    for (const entry of entries) {
      await scan(join(path, entry), cwd, regex, matches)
      if (matches.length >= 200) return
    }
    return
  }

  if (!info.isFile() || info.size > 1024 * 1024) return
  try {
    const text = await readFile(path, 'utf8')
    const lines = text.split(/\r?\n/)
    for (let index = 0; index < lines.length; index += 1) {
      if (regex.test(lines[index] ?? '')) {
        matches.push(`${path.replace(cwd, '.')}:${index + 1}: ${lines[index]}`)
        if (matches.length >= 200) return
      }
    }
  } catch {
    // Binary or unreadable files are ignored in this preview.
  }
}
