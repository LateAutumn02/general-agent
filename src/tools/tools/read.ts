import { readFile } from 'node:fs/promises'
import { resolveInCwd } from '../utils/path.js'
import type { ToolDefinition } from '../types.js'

type ReadInput = {
  path: string
}

export const readTool: ToolDefinition<ReadInput> = {
  name: 'Read',
  description: 'Read a text file.',
  inputSchema: {
    type: 'object',
    required: ['path'],
    properties: { path: { type: 'string' } },
  },
  readOnly: true,
  async checkPermission(input) {
    return { type: 'allow', reason: `Read ${input.path}` }
  },
  async execute(input, context, call) {
    const path = resolveInCwd(context.cwd, input.path)
    const text = await readFile(path, 'utf8')
    return {
      callId: call.id,
      ok: true,
      content: text,
      display: { type: 'text', text },
    }
  },
  summarize(input) {
    return `Read ${input.path}`
  },
}
