import { mkdtemp, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { runAgentTurn } from '../agent/loop.js'
import type { AgentState, ModelClient, ModelRequest, ModelStreamEvent } from '../agent/types.js'
import { PermissionController } from '../permissions/controller.js'
import type { RuntimeEvent } from '../runtime/events.js'
import type { ToolCall } from '../tools/types.js'
import { readMailbox } from './mailbox.js'

class SwarmMockModelClient implements ModelClient {
  requests = 0
  mainRequests = 0

  async *stream(request: ModelRequest): AsyncIterable<ModelStreamEvent> {
    this.requests += 1
    const hasAgentTool = request.tools?.some(tool => tool.name === 'Agent')
    if (hasAgentTool) this.mainRequests += 1
    const hasSendMessageTool = request.tools?.some(tool => tool.name === 'SendMessage')
    const hasAgentResult = request.messages.some(message => message.text.includes('Agent result'))
    const hasSendMessageResult = request.messages.some(message => message.text.includes('SendMessage result'))

    if (hasSendMessageResult && !hasAgentTool) {
      yield { type: 'text_delta', text: 'Sent.' }
      return
    }
    if (hasSendMessageTool && !hasAgentTool) {
      yield { type: 'text_delta', text: 'Sending to teammate.' }
      yield {
        type: 'tool_use',
        call: makeToolCall('SendMessage', {
          to: 'b',
          message: 'bridge',
          summary: 'word chosen',
        }),
      }
      return
    }

    if (hasAgentResult) {
      yield { type: 'text_delta', text: 'Done.' }
      return
    }

    yield {
      type: 'tool_use',
      call: makeToolCall('TeamCreate', {
        team_name: 'mock-team',
      }),
    }
    yield {
      type: 'tool_use',
      call: makeToolCall('Agent', {
        name: 'a',
        team_name: 'mock-team',
        description: 'choose word',
        prompt: 'Choose a word and SendMessage it to b.',
      }),
    }
  }
}

function makeToolCall(name: string, input: unknown): ToolCall {
  return {
    id: crypto.randomUUID(),
    name,
    input,
    status: 'pending',
    createdAt: Date.now(),
  }
}

const root = await mkdtemp(join(tmpdir(), 'ga-subagent-tools-'))
const state: AgentState = {
  sessionId: crypto.randomUUID(),
  messages: [],
  turnCount: 0,
  cwd: root,
  model: 'mock',
}
const events: RuntimeEvent[] = []
const model = new SwarmMockModelClient()

for await (const event of runAgentTurn({
  state,
  request: {
    id: crypto.randomUUID(),
    mode: 'prompt',
    text: 'Create a team and have agent a message agent b.',
    createdAt: Date.now(),
  },
  modelClient: model,
  permissionController: new PermissionController('bypassPermissions'),
  eventSink: event => events.push(event),
})) {
  if (event.type === 'error') throw new Error(event.error)
}

const deadline = Date.now() + 2000
while (Date.now() < deadline) {
  if (events.some(event => event.type === 'swarm_agent_status' && event.agentName === 'a' && event.status === 'completed')) {
    break
  }
  await Bun.sleep(20)
}

const inbox = await readMailbox(join(root, '.general-agent', 'teams'), 'mock-team', 'b')
if (inbox.length !== 1) throw new Error('sub-agent SendMessage did not write to teammate inbox')
if (inbox[0]?.from !== 'a') throw new Error('sub-agent message should use agent identity')
if (inbox[0]?.text !== 'bridge') throw new Error('sub-agent message content mismatch')
if (!events.some(event => event.type === 'swarm_message_sent' && event.from === 'a' && event.to === 'b')) {
  throw new Error('sub-agent SendMessage should emit swarm_message_sent')
}
if (!events.some(event => event.type === 'swarm_agent_status' && event.agentName === 'a' && event.status === 'running')) {
  throw new Error('background agent should emit running status')
}
if (model.mainRequests !== 1) {
  throw new Error(`main turn should stop after starting background agent; got ${model.mainRequests} main model requests`)
}

await rm(root, { recursive: true, force: true })
console.log('subagent tools smoke ok')
