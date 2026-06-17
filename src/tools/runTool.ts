import type { ToolCall, ToolContext, ToolDefinition, ToolResult } from './types.js'
import { validateToolInput } from './validate.js'

export async function runTool<TInput>(
  tool: ToolDefinition<TInput>,
  input: TInput,
  context: ToolContext,
  existingCall?: ToolCall,
): Promise<ToolResult> {
  const call = existingCall ?? {
    id: crypto.randomUUID(),
    name: tool.name,
    input,
    status: 'running' as const,
    createdAt: Date.now(),
  }
  context.emit({ type: 'tool_call_started', call })
  try {
    const validationErrors = validateToolInput(tool.inputSchema, input)
    if (validationErrors.length > 0) {
      throw new Error(`Invalid ${tool.name} input: ${validationErrors.join(', ')}`)
    }
    const result = await tool.execute(input, context, call)
    context.emit({ type: 'tool_call_finished', callId: call.id, result })
    return result
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    const result: ToolResult = {
      callId: call.id,
      ok: false,
      content: message,
      error: message,
    }
    context.emit({ type: 'tool_call_finished', callId: call.id, result })
    return result
  }
}
