import type { PromptMode, TranscriptItem } from './types.js'

export function createInitialTranscript(providerLabel = 'mock', model = 'mock'): TranscriptItem[] {
  if (providerLabel === 'mock') {
    return [
      {
        type: 'error',
        id: crypto.randomUUID(),
        text: 'No model API key found. Set DEEPSEEK_API_KEY in .env or your shell environment.',
      },
    ]
  }
  return [
    {
      type: 'tool_summary',
      id: crypto.randomUUID(),
      text: `Connected to ${providerLabel} · ${model}`,
      status: 'completed',
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
