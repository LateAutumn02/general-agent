import { compactMessages } from './compact.js'
import type { ChatMessage } from '../session/types.js'

const messages: ChatMessage[] = Array.from({ length: 8 }, (_, index) => ({
  id: `${index}`,
  role: index % 2 === 0 ? 'user' : 'assistant',
  text: `message ${index}`,
  createdAt: Date.now() + index,
}))

const result = compactMessages({ messages, reason: 'manual', preserveMessageCount: 3 })
if (result.messages.length !== 4) throw new Error('compact length mismatch')
if (result.removedMessageIds.length !== 5) throw new Error('removed ids mismatch')
if (!result.summaryMessage.text.includes('Conversation compacted')) throw new Error('summary missing')

console.log('compact smoke ok')
