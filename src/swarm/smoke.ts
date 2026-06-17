import { createSwarmPlan, createSwarmPlanFromGoal, startSwarm } from './planner.js'

const plan = createSwarmPlan('Improve UI', ['researcher', 'reviewer'])
if (plan.members.length !== 2) throw new Error('swarm member count failed')
if (!plan.members[0]?.prompt) throw new Error('swarm member prompt missing')
const running = startSwarm(plan)
if (running.status !== 'running') throw new Error('swarm did not start')
const auto = createSwarmPlanFromGoal('实现新功能')
if (!auto.members.some(member => member.name === 'coder')) throw new Error('auto swarm should include coder')

console.log('swarm smoke ok')
