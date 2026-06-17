import { TaskRegistry } from './registry.js'

const registry = new TaskRegistry()
const task = registry.create({ type: 'manual', title: 'Write docs', status: 'awaiting_input' })
registry.update(task.id, { status: 'completed', activity: 'Done' })
const loaded = registry.get(task.id)

if (!loaded || loaded.status !== 'completed') throw new Error('task update failed')
if (registry.counts().completed !== 1) throw new Error('task counts failed')

console.log('tasks smoke ok')
