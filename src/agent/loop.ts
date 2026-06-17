import { PermissionController } from '../permissions/controller.js'
import type { PermissionDecision } from '../permissions/types.js'
import type { JsonlSessionStore } from '../session/store.js'
import type { ChatMessage } from '../session/types.js'
import type { RuntimeEvent } from '../runtime/events.js'
import { runTool } from '../tools/runTool.js'
import { createDefaultToolRegistry, ToolRegistry } from '../tools/registry.js'
import type { ToolContext } from '../tools/types.js'
import type { AgentState, ModelClient, TurnRequest } from './types.js'

export type RunTurnOptions = {
  state: AgentState
  request: TurnRequest
  modelClient: ModelClient
  toolRegistry?: ToolRegistry
  permissionController?: PermissionController
  sessionStore?: JsonlSessionStore
  signal?: AbortSignal
  decidePermission?: (event: Extract<RuntimeEvent, { type: 'permission_request' }>) => Promise<PermissionDecision>
}

export async function* runAgentTurn(options: RunTurnOptions): AsyncIterable<RuntimeEvent> {
  const {
    state,
    request,
    modelClient,
    sessionStore,
    signal = new AbortController().signal,
  } = options
  const toolRegistry = options.toolRegistry ?? createDefaultToolRegistry()
  const permissionController = options.permissionController ?? new PermissionController()
  const userText = request.mode === 'bash' ? `!${request.text}` : request.text
  const userMessage: ChatMessage = {
    id: request.id,
    role: 'user',
    text: userText,
    createdAt: request.createdAt,
  }

  state.messages.push(userMessage)
  await sessionStore?.append(state.sessionId, { type: 'message', message: userMessage })

  let assistantText = ''
  const assistantId = crypto.randomUUID()

  for await (const event of modelClient.stream({
    model: state.model,
    messages: state.messages,
    cwd: state.cwd,
  }, signal)) {
    if (event.type === 'text_delta') {
      assistantText += event.text
      yield { type: 'assistant_delta', text: event.text, messageId: assistantId }
      continue
    }

    if (event.type === 'tool_use') {
      const tool = toolRegistry.get(event.call.name)
      if (!tool) {
        yield { type: 'error', error: `Unknown tool: ${event.call.name}` }
        continue
      }

      const context: ToolContext = {
        cwd: state.cwd,
        signal,
        sessionId: state.sessionId,
        emit: () => {},
      }
      const permission = await permissionController.evaluate(tool, event.call.input, context)
      if (permission.type === 'deny') {
        yield { type: 'error', error: permission.reason }
        continue
      }
      if (permission.type === 'ask') {
        const permissionEvent: RuntimeEvent = { type: 'permission_request', request: permission.request }
        yield permissionEvent
        const decision = options.decidePermission
          ? await options.decidePermission(permissionEvent)
          : { type: 'deny' as const, reason: 'No permission handler configured' }
        permissionController.applyDecision(permission.request, decision)
        yield { type: 'permission_resolved', requestId: permission.request.id, decision }
        await sessionStore?.append(state.sessionId, {
          type: 'permission_decision',
          requestId: permission.request.id,
          decision,
        })
        if (decision.type === 'deny') {
          yield { type: 'error', error: decision.reason ?? `Denied ${event.call.name}` }
          continue
        }
      }

      const result = await runTool(tool, event.call.input, {
        ...context,
        emit: () => {},
      }, { ...event.call, status: 'running' })
      yield { type: 'tool_call_started', call: event.call }
      yield { type: 'tool_call_finished', callId: event.call.id, result }
      await sessionStore?.append(state.sessionId, {
        type: 'runtime_event',
        event: { type: 'tool_call_finished', callId: event.call.id, result },
      })
    }
  }

  if (assistantText) {
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      text: assistantText,
      createdAt: Date.now(),
    }
    state.messages.push(assistantMessage)
    await sessionStore?.append(state.sessionId, { type: 'message', message: assistantMessage })
    yield { type: 'assistant_done', text: assistantText, messageId: assistantId }
  }
  state.turnCount += 1
}
