import { Glob } from 'bun'
import type { ToolDefinition } from '../types.js'

type GlobInput = {
  pattern: string
}

export const globTool: ToolDefinition<GlobInput> = {
  name: 'Glob',
  description: 'Find files by glob pattern.',
  inputSchema: {
    type: 'object',
    required: ['pattern'],
    properties: { pattern: { type: 'string' } },
  },
  readOnly: true,
  async checkPermission(input) {
    return { type: 'allow', reason: `Glob ${input.pattern}` }
  },
  async execute(input, context, call) {
    const glob = new Glob(input.pattern)
    const files: string[] = []
    for await (const file of glob.scan({ cwd: context.cwd, onlyFiles: true })) {
      files.push(file)
      if (files.length >= 200) break
    }
    return {
      callId: call.id,
      ok: true,
      content: files.join('\n') || '(no matches)',
      display: { type: 'text', text: files.join('\n') },
    }
  },
  summarize(input, result) {
    if (!result) return `Glob ${input.pattern}`
    return `Glob ${input.pattern}: ${result.content.split('\n').filter(Boolean).length} matches`
  },
}
