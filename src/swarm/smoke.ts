import { createSwarmPlan, startSwarm } from './planner.js'

const plan = createSwarmPlan('Improve UI', ['researcher', 'reviewer'])
if (plan.members.length !== 2) throw new Error('swarm member count failed')
const running = startSwarm(plan)
if (running.status !== 'running') throw new Error('swarm did not start')

console.log('swarm smoke ok')
