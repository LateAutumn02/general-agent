import { createModelClient } from './modelFactory.js'
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

console.log('api smoke ok')
