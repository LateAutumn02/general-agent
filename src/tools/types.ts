import type { RuntimeEventSink } from '../runtime/events.js'

export type JsonSchema = Record<string, unknown>

export type PermissionCheck =
  | { type: 'allow'; reason?: string }
  | { type: 'deny'; reason: string }
  | { type: 'ask'; reason: string; preview: ToolPreview }

export type ToolPreview =
  | { type: 'command'; command: string; cwd: string }
  | { type: 'file'; path: string; operation: 'read' | 'write' | 'edit' }
  | { type: 'search'; pattern: string; path: string }

export type ToolStatus = 'pending' | 'awaiting_permission' | 'running' | 'completed' | 'failed' | 'cancelled'

export type ToolCall = {
  id: string
  name: string
  input: unknown
  status: ToolStatus
  createdAt: number
}

export type ToolDisplay =
  | { type: 'text'; text: string }
  | { type: 'command_output'; stdout: string; stderr: string; exitCode: number }
  | { type: 'diff'; path: string; before: string; after: string }

export type ToolResult = {
  callId: string
  ok: boolean
  content: string
  display?: ToolDisplay
  error?: string
}

export type ToolContext = {
  cwd: string
  signal: AbortSignal
  sessionId: string
  emit: RuntimeEventSink
}

export type ToolDefinition<TInput = unknown> = {
  name: string
  description: string
  inputSchema: JsonSchema
  readOnly: boolean
  checkPermission(input: TInput, context: ToolContext): Promise<PermissionCheck>
  execute(input: TInput, context: ToolContext, call: ToolCall): Promise<ToolResult>
  summarize(input: TInput, result?: ToolResult): string
}
