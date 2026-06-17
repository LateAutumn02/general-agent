import { readFile, writeFile } from 'node:fs/promises'
import { resolveInCwd } from '../utils/path.js'
import type { ToolDefinition } from '../types.js'

type EditInput = {
  path: string
  oldText: string
  newText: string
}

export const editTool: ToolDefinition<EditInput> = {
  name: 'Edit',
  description: 'Replace text in a file.',
  inputSchema: {
    type: 'object',
    required: ['path', 'oldText', 'newText'],
    properties: {
      path: { type: 'string' },
      oldText: { type: 'string' },
      newText: { type: 'string' },
    },
  },
  readOnly: false,
  async checkPermission(input) {
    return {
      type: 'ask',
      reason: `Allow editing ${input.path}?`,
      preview: { type: 'file', path: input.path, operation: 'edit' },
    }
  },
  async execute(input, context, call) {
    const path = resolveInCwd(context.cwd, input.path)
    const before = await readFile(path, 'utf8')
    if (!before.includes(input.oldText)) {
      throw new Error(`Text not found in ${input.path}`)
    }
    const after = before.replace(input.oldText, input.newText)
    await writeFile(path, after, 'utf8')
    return {
      callId: call.id,
      ok: true,
      content: `Edited ${input.path}`,
      display: { type: 'diff', path: input.path, before, after },
    }
  },
  summarize(input) {
    return `Edited ${input.path}`
  },
}
