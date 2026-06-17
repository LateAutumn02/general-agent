import type { ToolCall, ToolResult } from '../tools/types.js'

export type RuntimeEvent =
  | { type: 'tool_call_started'; call: ToolCall }
  | { type: 'tool_call_finished'; callId: string; result: ToolResult }
  | { type: 'error'; error: string }

export type RuntimeEventSink = (event: RuntimeEvent) => void
