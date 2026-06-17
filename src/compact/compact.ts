import type { ChatMessage } from '../session/types.js'
import type { CompactRequest, CompactResult } from './types.js'

export function compactMessages(request: CompactRequest): CompactResult {
  const preserve = Math.max(1, request.preserveMessageCount)
  if (request.messages.length <= preserve + 1) {
    const passthroughSummary = createSummaryMessage([], request.reason)
    return {
      summaryMessage: passthroughSummary,
      messages: request.messages,
      removedMessageIds: [],
      beforeCharacters: countCharacters(request.messages),
      afterCharacters: countCharacters(request.messages),
    }
  }

  const removed = request.messages.slice(0, -preserve)
  const kept = request.messages.slice(-preserve)
  const summaryMessage = createSummaryMessage(removed, request.reason)
  const messages = [summaryMessage, ...kept]
  return {
    summaryMessage,
    messages,
    removedMessageIds: removed.map(message => message.id),
    beforeCharacters: countCharacters(request.messages),
    afterCharacters: countCharacters(messages),
  }
}

function createSummaryMessage(messages: ChatMessage[], reason: CompactRequest['reason']): ChatMessage {
  const lines = messages.slice(-12).map(message => {
    const text = message.text.trim().replace(/\s+/g, ' ')
    return `- ${message.role}: ${text.slice(0, 180)}`
  })
  return {
    id: crypto.randomUUID(),
    role: 'system',
    text: [
      `Conversation compacted (${reason}).`,
      messages.length ? 'Recent preserved facts:' : 'No older messages needed compaction.',
      ...lines,
    ].join('\n'),
    createdAt: Date.now(),
  }
}

function countCharacters(messages: ChatMessage[]) {
  return messages.reduce((total, message) => total + message.text.length, 0)
}
