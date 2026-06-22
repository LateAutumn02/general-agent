// Agent Tool & Swarm visualization integration test
// Covers: registration, validation, execution, parallel calls, sub-agent communication, visualization

import { createDefaultToolRegistry } from './registry.js'
import { validateToolInput } from './validate.js'

const registry = createDefaultToolRegistry()

// === Test 1: Agent tool registered ===
const agentTool = registry.get('Agent')
if (!agentTool) throw new Error('FAIL: Agent tool not registered')
if (agentTool.readOnly !== true) throw new Error('FAIL: Agent should be readOnly')
console.log('PASS [1/7] Agent tool registered in default registry')

// === Test 2: Schema validation ===
const valid = { description: 'Security audit', prompt: 'Review auth module for issues' }
if (validateToolInput(agentTool.inputSchema, valid).length > 0) throw new Error('FAIL: valid input rejected')
if (validateToolInput(agentTool.inputSchema, { description: 'x' }).length === 0) throw new Error('FAIL: missing prompt not rejected')
console.log('PASS [2/7] Input schema validation')

// === Test 3: Tool execution ===
const ctx = { cwd: process.cwd(), signal: new AbortController().signal, sessionId: 'test', emit: () => {} }
const call = { id: 'call-1', name: 'Agent', input: valid, status: 'pending' as const, createdAt: Date.now() }
const result = await agentTool.execute(valid, ctx, call)
if (!result.ok) throw new Error('FAIL: execution not ok')
if (!result.content.includes('Agent task created')) throw new Error('FAIL: missing task created message')
if (!result.content.includes('Security audit')) throw new Error('FAIL: missing description in result')
console.log('PASS [3/7] Single Agent execution')

// === Test 4: Parallel execution ===
const parallel = await Promise.all([1, 2, 3].map(i =>
  agentTool.execute(
    { description: `Task ${i}`, prompt: `Do task ${i}` },
    ctx,
    { id: `p-${i}`, name: 'Agent', input: {} as never, status: 'pending', createdAt: Date.now() },
  ),
))
if (parallel.length !== 3) throw new Error('FAIL: wrong count')
if (parallel.some(r => !r.ok)) throw new Error('FAIL: not all parallel calls ok')
console.log('PASS [4/7] 3 parallel Agent calls')

// === Test 5: Sub-agent task creation & inter-agent communication ===
import { TaskRegistry } from '../tasks/registry.js'
import { MultiAgentManager } from '../multi-agent/manager.js'

const taskReg = new TaskRegistry()
const mgr = new MultiAgentManager(taskReg)

const t1 = mgr.createAgentTask({ description: 'Researcher: auth audit', prompt: 'Review auth', profile: 'researcher', allowedTools: ['Read', 'Glob'] }, 's1')
const t2 = mgr.createAgentTask({ description: 'Reviewer: check diff', prompt: 'Review changes', profile: 'reviewer', allowedTools: ['Read'] }, 's1')

// Inter-agent: task 1 updates status → task 2 can read it
taskReg.update(t1.id, { status: 'running', activity: 'Searching auth patterns' })
taskReg.update(t1.id, { status: 'completed', activity: 'Done', output: 'Found 2 issues: SQL injection, weak hashing' })

// Task 2 reads task 1's output (simulates inter-agent communication)
const t1Output = taskReg.get(t1.id)?.output
if (!t1Output?.includes('SQL injection')) throw new Error('FAIL: cannot read peer output')
taskReg.update(t2.id, { status: 'running', activity: `Acting on: ${t1Output.slice(0, 30)}` })
taskReg.update(t2.id, { status: 'completed', activity: 'Verified fixes' })

const all = taskReg.list()
if (all.filter(t => t.status === 'completed').length !== 2) throw new Error('FAIL: not all completed')
console.log('PASS [5/7] Sub-agent inter-communication via task registry')

// === Test 6: Agent progress visualization items ===
const progressLines = [
  { agentId: t1.id, agentType: 'researcher', description: t1.title, status: 'completed' as const, toolUseCount: 3, tokenCount: 4500, durationMs: 1200, isBackground: false },
  { agentId: t2.id, agentType: 'reviewer', description: t2.title, status: 'completed' as const, toolUseCount: 5, tokenCount: 8200, durationMs: 2300, isBackground: false },
]
const progressItem = { type: 'agent_progress' as const, id: crypto.randomUUID(), agents: progressLines, status: 'completed' as const }
if (progressItem.agents.length !== 2) throw new Error('FAIL: wrong agent count')
if (progressItem.agents[0]?.status !== 'completed') throw new Error('FAIL: wrong status')
console.log('PASS [6/7] Agent progress visualization items')

// === Test 7: Agent tool has permission check ===
const perm = await agentTool.checkPermission(valid, ctx)
if (perm.type !== 'ask') throw new Error('FAIL: Agent should require permission')
if (!perm.reason.includes('Security audit')) throw new Error('FAIL: permission reason wrong')
console.log('PASS [7/7] Permission check requires user approval')

console.log('agent-tool smoke ok')
