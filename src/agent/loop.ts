import { PermissionController } from '../permissions/controller.js'
import type { PermissionDecision } from '../permissions/types.js'
import type { JsonlSessionStore } from '../session/store.js'
import type { ChatMessage } from '../session/types.js'
import type { RuntimeEvent } from '../runtime/events.js'
import { buildRuntimeSystemAdditions } from '../runtime/context.js'
import { runTool } from '../tools/runTool.js'
import { createDefaultToolRegistry, createSubAgentToolRegistry, ToolRegistry } from '../tools/registry.js'
import type { ToolContext } from '../tools/types.js'
import type { ToolCall } from '../tools/types.js'
import { validateToolInput } from '../tools/validate.js'
import type { AgentState, ModelClient, TurnRequest } from './types.js'

export type RunTurnOptions = {
  state: AgentState
  request: TurnRequest
  modelClient: ModelClient
  toolRegistry?: ToolRegistry
  permissionController?: PermissionController
  sessionStore?: JsonlSessionStore
  signal?: AbortSignal
  toolContext?: Pick<ToolContext, 'agentName' | 'teamName'>
  eventSink?: (event: RuntimeEvent) => void
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
  const systemAdditions = await buildRuntimeSystemAdditions(state.cwd)
  const userText = request.mode === 'bash' ? `!${request.text}` : request.text
  const userMessage: ChatMessage = {
    id: request.id,
    role: 'user',
    text: userText,
    createdAt: request.createdAt,
  }

  state.messages.push(userMessage)
  await sessionStore?.append(state.sessionId, { type: 'message', message: userMessage })

  if (request.mode === 'bash') {
    yield* executeToolCall({
      call: {
        id: crypto.randomUUID(),
        name: 'Bash',
        input: { command: request.text },
        status: 'pending',
        createdAt: Date.now(),
      },
      state,
      toolRegistry,
      permissionController,
      sessionStore,
      signal,
      modelClient,
      toolContext: options.toolContext,
      decidePermission: options.decidePermission,
      eventSink: options.eventSink,
    })
    state.turnCount += 1
    return
  }

  const maxModelSteps = 12
  for (let step = 0; step < maxModelSteps; step += 1) {
    let assistantText = ''
    const assistantId = crypto.randomUUID()
    const pendingToolCalls: ToolCall[] = []

    yield { type: 'model_request_started', step, afterTool: step > 0 }
    try {
      for await (const event of modelClient.stream({
        model: state.model,
        messages: state.messages,
        cwd: state.cwd,
        tools: toolRegistry.list(),
        systemAdditions,
      }, signal)) {
        if (event.type === 'text_delta') {
          assistantText += event.text
          yield { type: 'assistant_delta', text: event.text, messageId: assistantId }
        continue
      }

      if (event.type === 'tool_use') {
        pendingToolCalls.push(event.call)
      }
    }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      process.stderr.write(`\n[LOOP] Model stream error: ${msg}\n`)
      yield { type: 'error', error: msg }
      break
    }

    if (assistantText || pendingToolCalls.length > 0) {
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        text: assistantText,
        createdAt: Date.now(),
        toolCalls: pendingToolCalls.map(call => ({
          id: call.id,
          name: call.name,
          input: call.input,
        })),
      }
      state.messages.push(assistantMessage)
      await sessionStore?.append(state.sessionId, { type: 'message', message: assistantMessage })
      if (assistantText) {
        yield { type: 'assistant_done', text: assistantText, messageId: assistantId }
      }
    }

    let backgroundAgentStarted = false
    for (const call of pendingToolCalls) {
      for await (const event of executeToolCall({
        call,
        state,
        toolRegistry,
        permissionController,
        sessionStore,
        signal,
        modelClient,
        toolContext: options.toolContext,
        decidePermission: options.decidePermission,
        eventSink: options.eventSink,
      })) {
        if (
          event.type === 'tool_call_finished'
          && call.name === 'Agent'
          && event.result.ok
          && event.result.content.startsWith('Agent started in background:')
        ) {
          backgroundAgentStarted = true
        }
        yield event
      }
    }

    if (pendingToolCalls.length === 0) break
    if (backgroundAgentStarted) break
    if (step === maxModelSteps - 1) {
      yield {
        type: 'error',
        error: `Stopped after ${maxModelSteps} tool rounds to avoid an infinite loop. Please ask me to continue if more work is needed.`,
      }
    }
  }
  state.turnCount += 1
}

type ExecuteToolCallOptions = {
  call: ToolCall
  state: AgentState
  toolRegistry: ToolRegistry
  permissionController: PermissionController
  sessionStore?: JsonlSessionStore
  signal: AbortSignal
  modelClient: ModelClient
  toolContext?: Pick<ToolContext, 'agentName' | 'teamName'>
  eventSink?: (event: RuntimeEvent) => void
  decidePermission?: (event: Extract<RuntimeEvent, { type: 'permission_request' }>) => Promise<PermissionDecision>
}

async function* executeToolCall(options: ExecuteToolCallOptions): AsyncIterable<RuntimeEvent> {
  const {
    call,
    state,
    toolRegistry,
    permissionController,
    sessionStore,
    signal,
    modelClient,
    toolContext,
    eventSink,
    decidePermission,
  } = options
  const tool = toolRegistry.get(call.name)
  if (!tool) {
    const msg = `Unknown tool: ${call.name}`
    process.stderr.write(`\n[LOOP] ${msg}\n`)
    yield { type: 'error', error: msg }
    return
  }
  const validationErrors = validateToolInput(tool.inputSchema, call.input)
  if (validationErrors.length > 0) {
    yield { type: 'error', error: `Invalid ${call.name} input: ${validationErrors.join(', ')}` }
    return
  }

  const emitToolEvent = (event: RuntimeEvent) => {
    if (event.type === 'tool_call_started' || event.type === 'tool_call_finished') return
    eventSink?.(event)
    void sessionStore?.append(state.sessionId, { type: 'runtime_event', event })
  }

  const context: ToolContext = {
    cwd: state.cwd,
    signal,
    sessionId: state.sessionId,
    agentName: toolContext?.agentName,
    teamName: toolContext?.teamName,
    emit: emitToolEvent,
    async startSubAgent(opts) {
      const agentName = opts.agentName
      const teamName = opts.teamName
      const agentType = opts.agentType ?? 'general-purpose'
      const createdAt = Date.now()
      const agentKey = `${agentName}@${teamName}`
      const emit = (event: RuntimeEvent) => {
        eventSink?.(event)
        void sessionStore?.append(state.sessionId, { type: 'runtime_event', event })
      }

      emit({
        type: 'swarm_agent_status',
        teamName,
        agentName,
        agentType,
        status: 'starting',
        activity: 'Starting',
        description: opts.description,
        prompt: opts.prompt,
        toolUseCount: 0,
        createdAt,
        updatedAt: createdAt,
      })

      void (async () => {
        const subState: AgentState = {
          sessionId: `${state.sessionId}:${agentName}`,
          messages: [{
            id: crypto.randomUUID(),
            role: 'system',
            text: [
              `You are sub-agent ${agentName} in team ${teamName}.`,
              opts.description,
              'Use the available tools when needed.',
              'If asked to message another teammate, call SendMessage in this same turn.',
              'Do not merely describe a plan when a tool call is required.',
            ].join('\n'),
            createdAt,
          }],
          turnCount: 0,
          cwd: state.cwd,
          model: opts.model === 'inherit' ? state.model : opts.model,
        }
        let lastAssistant = ''
        let toolUseCount = 0
        const update = (
          status: 'running' | 'idle' | 'completed' | 'failed',
          activity: string,
          patch: Partial<Extract<RuntimeEvent, { type: 'swarm_agent_status' }>> = {},
        ) => {
          const now = Date.now()
          emit({
            type: 'swarm_agent_status',
            teamName,
            agentName,
            agentType,
            status,
            activity,
            description: opts.description,
            prompt: opts.prompt,
            output: patch.output,
            error: patch.error,
            toolUseCount,
            createdAt,
            updatedAt: now,
            completedAt: patch.completedAt,
          })
        }

        try {
          update('running', 'Thinking')
          for await (const event of runAgentTurn({
            state: subState,
            request: {
              id: crypto.randomUUID(),
              mode: 'prompt',
              text: opts.prompt,
              createdAt: Date.now(),
            },
            modelClient,
            toolRegistry: createSubAgentToolRegistry(agentType),
            permissionController: new PermissionController('bypassPermissions'),
            signal,
            toolContext: { agentName, teamName },
            eventSink: emit,
          })) {
            emit(event)
            if (event.type === 'assistant_done') {
              lastAssistant = event.text
              update('running', event.text.split(/\r?\n/, 1)[0]?.slice(0, 80) || 'Responding')
            } else if (event.type === 'tool_call_started') {
              toolUseCount += 1
              update('running', `Running ${event.call.name}`)
            } else if (event.type === 'tool_call_finished') {
              update('running', event.result.ok ? `${event.result.content.split(/\r?\n/, 1)[0]?.slice(0, 80) || 'Tool completed'}` : `Failed ${event.result.error ?? 'tool'}`)
            } else if (event.type === 'error') {
              update('failed', event.error, { error: event.error, completedAt: Date.now() })
            }
          }
          update('completed', 'Done', {
            output: lastAssistant.trim() || '(agent returned no response)',
            completedAt: Date.now(),
          })
        } catch (err) {
          update('failed', 'Failed', {
            error: err instanceof Error ? err.message : String(err),
            completedAt: Date.now(),
          })
        }
      })()

      return { agentKey }
    },
    async runSubAgent(opts) {
      const subState: AgentState = {
        sessionId: `${state.sessionId}:${opts.agentName ?? crypto.randomUUID()}`,
        messages: [{
          id: crypto.randomUUID(),
          role: 'system',
          text: [
            `You are sub-agent ${opts.agentName ?? 'worker'}${opts.teamName ? ` in team ${opts.teamName}` : ''}.`,
            opts.description,
            'Use the available tools when needed.',
            'If asked to message another teammate, call SendMessage in this same turn.',
            'Do not merely describe a plan when a tool call is required.',
          ].join('\n'),
          createdAt: Date.now(),
        }],
        turnCount: 0,
        cwd: state.cwd,
        model: opts.model === 'inherit' ? state.model : opts.model,
      }
      let lastAssistant = ''
      const toolResults: string[] = []
      for await (const event of runAgentTurn({
        state: subState,
        request: {
          id: crypto.randomUUID(),
          mode: 'prompt',
          text: opts.prompt,
          createdAt: Date.now(),
        },
        modelClient,
        toolRegistry: createSubAgentToolRegistry(opts.agentType),
        permissionController: new PermissionController('bypassPermissions'),
        signal,
        toolContext: {
          agentName: opts.agentName,
          teamName: opts.teamName,
        },
        eventSink,
      })) {
        if (event.type === 'assistant_done') {
          lastAssistant = event.text
        } else if (event.type === 'tool_call_finished') {
          toolResults.push(`${event.result.ok ? 'OK' : 'FAIL'} ${event.result.content}`)
        }
      }
      return [lastAssistant.trim(), ...toolResults].filter(Boolean).join('\n\n') || '(agent returned no response)'
    },
  }
  const permission = await permissionController.evaluate(tool, call.input, context)
  if (permission.type === 'deny') {
    yield { type: 'error', error: permission.reason }
    return
  }
  if (permission.type === 'ask') {
    const permissionEvent: RuntimeEvent = { type: 'permission_request', request: permission.request }
    yield permissionEvent
    const decision = decidePermission
      ? await decidePermission(permissionEvent)
      : { type: 'deny' as const, reason: 'No permission handler configured' }
    permissionController.applyDecision(permission.request, decision)
    yield { type: 'permission_resolved', requestId: permission.request.id, decision }
    await sessionStore?.append(state.sessionId, {
      type: 'permission_decision',
      requestId: permission.request.id,
      decision,
    })
    if (decision.type === 'deny') {
      yield { type: 'error', error: decision.reason ?? `Denied ${call.name}` }
      return
    }
  }

  yield { type: 'tool_call_started', call }
  const result = await runTool(tool, call.input, {
    ...context,
    emit: emitToolEvent,
  }, { ...call, status: 'running' })
  yield { type: 'tool_call_finished', callId: call.id, result }
  const toolMessage: ChatMessage = {
    id: crypto.randomUUID(),
    role: 'tool',
    text: `${call.name} result:\n${result.content}`,
    createdAt: Date.now(),
    toolCallId: call.id,
    toolName: call.name,
  }
  state.messages.push(toolMessage)
  await sessionStore?.append(state.sessionId, { type: 'message', message: toolMessage })
  await sessionStore?.append(state.sessionId, {
    type: 'runtime_event',
    event: { type: 'tool_call_finished', callId: call.id, result },
  })
}
