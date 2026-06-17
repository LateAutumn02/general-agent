import type { ToolContext, ToolDefinition, ToolResult } from './types.js'

export async function runTool<TInput>(
  tool: ToolDefinition<TInput>,
  input: TInput,
  context: ToolContext,
): Promise<ToolResult> {
  const call = {
    id: crypto.randomUUID(),
    name: tool.name,
    input,
    status: 'running' as const,
    createdAt: Date.now(),
  }
  context.emit({ type: 'tool_call_started', call })
  try {
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
