import type { PromptMode, TranscriptItem } from './types.js'

export function createInitialTranscript(): TranscriptItem[] {
  return [
    {
      type: 'assistant',
      id: crypto.randomUUID(),
      text: 'Rewrite scaffold is ready. The next modules will replace this mock runtime with real tools and agent streaming.',
    },
  ]
}

export function nextAssistantReply(input: string, mode: PromptMode): TranscriptItem {
  if (mode === 'bash') {
    return {
      type: 'tool_summary',
      id: crypto.randomUUID(),
      text: `Prepared bash command: ${input}`,
      status: 'pending',
    }
  }

  if (input.startsWith('/')) {
    return {
      type: 'assistant',
      id: crypto.randomUUID(),
      text: `Command placeholder accepted: ${input}`,
    }
  }

  return {
    type: 'assistant',
    id: crypto.randomUUID(),
    text: `Mock response for: ${input}`,
  }
}
