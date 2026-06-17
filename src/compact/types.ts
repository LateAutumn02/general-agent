import type { ChatMessage } from '../session/types.js'

export type CompactRequest = {
  messages: ChatMessage[]
  reason: 'manual' | 'token_budget' | 'recovery'
  preserveMessageCount: number
}

export type CompactResult = {
  summaryMessage: ChatMessage
  messages: ChatMessage[]
  removedMessageIds: string[]
  beforeCharacters: number
  afterCharacters: number
}
