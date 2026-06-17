import { loadMemory } from './store.js'

const memory = await loadMemory(process.cwd())
if (!memory.enabled) throw new Error('memory should be enabled by default')

console.log('memory smoke ok')
