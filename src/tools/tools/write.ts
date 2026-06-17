import { mkdir, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { resolveInCwd } from '../utils/path.js'
import type { ToolDefinition } from '../types.js'

type WriteInput = {
  path: string
  content: string
}

export const writeTool: ToolDefinition<WriteInput> = {
  name: 'Write',
  description: 'Write a full file.',
  inputSchema: {
    type: 'object',
    required: ['path', 'content'],
    properties: { path: { type: 'string' }, content: { type: 'string' } },
  },
  readOnly: false,
  async checkPermission(input) {
    return {
      type: 'ask',
      reason: `Allow writing ${input.path}?`,
      preview: { type: 'file', path: input.path, operation: 'write' },
    }
  },
  async execute(input, context, call) {
    const path = resolveInCwd(context.cwd, input.path)
    await mkdir(dirname(path), { recursive: true })
    await writeFile(path, input.content, 'utf8')
    return {
      callId: call.id,
      ok: true,
      content: `Wrote ${input.path}`,
      display: { type: 'text', text: input.content },
    }
  },
  summarize(input) {
    return `Wrote ${input.path}`
  },
}
