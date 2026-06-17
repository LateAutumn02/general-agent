export type PromptMode = 'prompt' | 'bash' | 'command' | 'file'

export type ToolStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type TranscriptItem =
  | { type: 'user'; id: string; text: string }
  | { type: 'assistant'; id: string; text: string }
  | { type: 'tool_summary'; id: string; text: string; status: ToolStatus }
  | { type: 'error'; id: string; text: string }
