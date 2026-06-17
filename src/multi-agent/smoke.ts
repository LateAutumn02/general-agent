import { TaskRegistry } from '../tasks/registry.js'
import { MultiAgentManager } from './manager.js'

const manager = new MultiAgentManager(new TaskRegistry())
const task = manager.createAgentTask({
  description: 'Review docs',
  prompt: 'Find missing docs',
  profile: 'reviewer',
}, 'parent')

if (task.profile.name !== 'reviewer') throw new Error('profile resolution failed')
if (task.status !== 'awaiting_input') throw new Error('agent task status failed')

console.log('multi-agent smoke ok')
