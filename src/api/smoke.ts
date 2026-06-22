import { createModelClient } from './modelFactory.js'
import { toOpenAICompatibleMessages } from './openaiCompatibleClient.js'
import { loadRuntimeConfig } from '../config/runtimeConfig.js'

const config = loadRuntimeConfig([], process.cwd())
const client = createModelClient({ ...config, provider: 'mock', model: 'mock', apiKey: undefined })
const events = []
for await (const event of client.stream({
  model: 'mock',
  cwd: process.cwd(),
  messages: [{ id: '1', role: 'user', text: 'hello', createdAt: Date.now() }],
}, new AbortController().signal)) {
  events.push(event.type)
}
if (!events.includes('message_done')) throw new Error('model client failed')

const protocolMessages = toOpenAICompatibleMessages([
  {
    id: 'assistant-tool',
    role: 'assistant',
    text: '',
    createdAt: Date.now(),
    toolCalls: [{ id: 'call-1', name: 'Read', input: { path: 'src/swarm/mailbox.ts' } }],
  },
  {
    id: 'tool-result',
    role: 'tool',
    text: 'Read result:\nexport const value = 1',
    createdAt: Date.now(),
    toolCallId: 'call-1',
    toolName: 'Read',
  },
], process.cwd(), [])
if (!protocolMessages.some(message => message.role === 'assistant' && 'tool_calls' in message)) {
  throw new Error('assistant tool_calls were not preserved')
}
if (!protocolMessages.some(message => message.role === 'tool' && message.tool_call_id === 'call-1')) {
  throw new Error('tool result was not encoded as role=tool')
}

console.log('api smoke ok')
