import type { ToolCall, ToolResult } from '../tools/types.js'
import type { PermissionDecision, PermissionRequest } from '../permissions/types.js'

export type RuntimeEvent =
  | { type: 'model_request_started'; step: number; afterTool: boolean }
  | { type: 'assistant_delta'; text: string; messageId: string }
  | { type: 'assistant_done'; text: string; messageId: string }
  | { type: 'tool_call_started'; call: ToolCall }
  | { type: 'tool_call_finished'; callId: string; result: ToolResult }
  | { type: 'permission_request'; request: PermissionRequest }
  | { type: 'permission_resolved'; requestId: string; decision: PermissionDecision }
  | { type: 'error'; error: string }

export type RuntimeEventSink = (event: RuntimeEvent) => void
