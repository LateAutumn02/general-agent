import type { ChatMessage } from '../session/types.js'
import type { ToolCall } from '../tools/types.js'

export type AgentState = {
  sessionId: string
  messages: ChatMessage[]
  turnCount: number
  cwd: string
  model: string
}

export type TurnRequest = {
  id: string
  mode: 'prompt' | 'bash' | 'command'
  text: string
  createdAt: number
}

export type ModelRequest = {
  model: string
  messages: ChatMessage[]
  cwd: string
}

export type ModelStreamEvent =
  | { type: 'text_delta'; text: string }
  | { type: 'tool_use'; call: ToolCall }
  | { type: 'message_done' }

export type ModelClient = {
  stream(request: ModelRequest, signal: AbortSignal): AsyncIterable<ModelStreamEvent>
}
