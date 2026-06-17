import React, { useEffect, useMemo, useRef, useState } from 'react'
import { join } from 'node:path'
import { Box, useApp, useInput } from 'ink'
import { runAgentTurn } from '../agent/loop.js'
import type { AgentState } from '../agent/types.js'
import { createModelClient } from '../api/modelFactory.js'
import { compactMessages } from '../compact/compact.js'
import { loadRuntimeConfig } from '../config/runtimeConfig.js'
import { PermissionController } from '../permissions/controller.js'
import type {
  PermissionDecision as CorePermissionDecision,
  PermissionRequest as CorePermissionRequest,
} from '../permissions/types.js'
import type { RuntimeEvent } from '../runtime/events.js'
import { JsonlSessionStore } from '../session/store.js'
import type { ChatMessage } from '../session/types.js'
import { TaskRegistry } from '../tasks/registry.js'
import type { TaskState } from '../tasks/types.js'
import { Footer } from './components/Footer.js'
import { Header } from './components/Header.js'
import { PermissionPrompt } from './components/PermissionPrompt.js'
import { PromptInput } from './components/PromptInput.js'
import { TaskBoard } from './components/TaskBoard.js'
import { Transcript } from './components/Transcript.js'
import { createInitialTranscript } from './mockRuntime.js'
import type { PermissionDecision, PermissionRequest, PromptMode, TaskItem, TranscriptItem } from './types.js'

type AppProps = {
  args: string[]
  cwd: string
}

type PendingPermission = {
  request: CorePermissionRequest
  resolve: (decision: CorePermissionDecision) => void
}

export function App({ args, cwd }: AppProps) {
  const { exit } = useApp()
  const [inputMode, setInputMode] = useState<PromptMode>('prompt')
  const [permission, setPermission] = useState<PermissionRequest | undefined>()
  const [denyReason, setDenyReason] = useState('')
  const [collectingDenyReason, setCollectingDenyReason] = useState(false)
  const [view, setView] = useState<'chat' | 'tasks'>('chat')
  const [selectedTaskId, setSelectedTaskId] = useState<string | undefined>()
  const [detailTaskId, setDetailTaskId] = useState<string | undefined>()
  const [processing, setProcessing] = useState(false)
  const [sessionReady, setSessionReady] = useState(false)
  const taskRegistry = useMemo(() => createInitialTaskRegistry(), [])
  const [tasks, setTasks] = useState<TaskItem[]>(() => taskItemsFromRegistry(taskRegistry))
  const config = useMemo(() => loadRuntimeConfig(args, cwd), [args, cwd])
  const model = config.model
  const [items, setItems] = useState<TranscriptItem[]>(() => createInitialTranscript(config.providerLabel, model))
  const modelClient = useMemo(() => createModelClient(config), [config])
  const permissionController = useMemo(() => new PermissionController(config.permissionMode), [config.permissionMode])
  const agentState = useRef<AgentState>({
    sessionId: crypto.randomUUID(),
    messages: [],
    turnCount: 0,
    cwd,
    model,
  })
  const pendingPermission = useRef<PendingPermission | undefined>(undefined)
  const sessionStore = useMemo(() => new JsonlSessionStore(join(cwd, '.general-agent', 'sessions')), [cwd])

  useEffect(() => {
    let cancelled = false
    async function loadSession() {
      const resumeTarget = readOptionalArg(args, '--resume') ?? readOptionalArg(args, '-r')
      if (resumeTarget !== undefined) {
        const sessions = await sessionStore.list()
        const target = resumeTarget === true
          ? sessions[0]
          : sessions.find(session => session.id === resumeTarget || session.id.startsWith(resumeTarget))
        if (target) {
          const loaded = await sessionStore.load(target.id)
          if (cancelled) return
          agentState.current.sessionId = target.id
          agentState.current.messages = [...loaded.messages]
          agentState.current.turnCount = loaded.messages.filter(message => message.role === 'user').length
          setItems(transcriptFromMessages(loaded.messages))
          setSessionReady(true)
          return
        }
      }
      const session = await sessionStore.create({ cwd, model, title: 'general-agent session' })
      if (cancelled) return
      agentState.current.sessionId = session.id
      setSessionReady(true)
    }
    void loadSession()
    return () => {
      cancelled = true
    }
  }, [args, cwd, model, sessionStore, config.providerLabel])

  useInput((input, key) => {
    if (permission) {
      handlePermissionInput(input, key)
      return
    }

    if (key.leftArrow) {
      setView('tasks')
      setSelectedTaskId(prev => prev ?? taskRegistry.list()[0]?.id)
      return
    }
    if (key.rightArrow) {
      setView('chat')
      setDetailTaskId(undefined)
      return
    }

    if (view === 'tasks') {
      if (key.escape) {
        setDetailTaskId(undefined)
        return
      }
      if (key.upArrow || key.downArrow) {
        moveTaskSelection(key.downArrow ? 1 : -1)
        return
      }
      if (key.return && selectedTaskId) {
        setDetailTaskId(selectedTaskId)
        return
      }
      if (input.toLowerCase() === 'n') {
        const task = taskRegistry.create({
          type: 'manual',
          title: 'Manual task',
          activity: 'Awaiting input',
          status: 'awaiting_input',
        })
        void sessionStore.append(agentState.current.sessionId, {
          type: 'task_state',
          task: toTaskItem(task),
        })
        setSelectedTaskId(task.id)
        setTasks(taskItemsFromRegistry(taskRegistry))
        return
      }
      if (input.toLowerCase() === 'c' && selectedTaskId) {
        const updated = taskRegistry.update(selectedTaskId, {
          status: 'cancelled',
          activity: 'Cancelled by user',
        })
        if (updated) {
          void sessionStore.append(agentState.current.sessionId, {
            type: 'task_state',
            task: toTaskItem(updated),
          })
        }
        setTasks(taskItemsFromRegistry(taskRegistry))
      }
    }
  })

  function moveTaskSelection(offset: number) {
    const allTasks = taskRegistry.list()
    if (allTasks.length === 0) {
      setSelectedTaskId(undefined)
      return
    }
    const currentIndex = Math.max(0, allTasks.findIndex(task => task.id === selectedTaskId))
    const nextIndex = (currentIndex + offset + allTasks.length) % allTasks.length
    setSelectedTaskId(allTasks[nextIndex]?.id)
  }

  async function submit(text: string, mode: PromptMode) {
    const trimmed = text.trim()
    if (!trimmed || processing || !sessionReady) return

    if (trimmed === '/exit' || trimmed === '/quit') {
      exit()
      return
    }

    if (trimmed === '/help') {
      setItems(prev => [
        ...prev,
        { type: 'user', id: crypto.randomUUID(), text: trimmed },
        {
          type: 'assistant',
          id: crypto.randomUUID(),
          text: 'Available now: type normally, prefix with ! for bash mode, use /help, /exit, or /quit.',
        },
      ])
      return
    }

    if (trimmed === '/resume' || trimmed.startsWith('/resume ')) {
      await handleResumeCommand(trimmed)
      return
    }

    if (trimmed === '/compact') {
      const result = compactMessages({
        messages: agentState.current.messages,
        reason: 'manual',
        preserveMessageCount: 6,
      })
      agentState.current.messages = result.messages
      setItems([
        ...transcriptFromMessages(result.messages),
        {
          type: 'tool_summary',
          id: crypto.randomUUID(),
          text: `Compacted ${result.removedMessageIds.length} messages`,
          status: 'completed',
        },
      ])
      await sessionStore.append(agentState.current.sessionId, {
        type: 'message',
        message: result.summaryMessage,
      })
      return
    }

    setProcessing(true)
    setItems(prev => [...prev, { type: 'user', id: crypto.randomUUID(), text: trimmed }])
    try {
      for await (const event of runAgentTurn({
        state: agentState.current,
        request: {
          id: crypto.randomUUID(),
          mode: mode === 'bash' ? 'bash' : mode === 'command' ? 'command' : 'prompt',
          text: trimmed,
          createdAt: Date.now(),
        },
        modelClient,
        permissionController,
        sessionStore,
        async decidePermission(permissionEvent) {
          return await waitForPermission(permissionEvent.request)
        },
      })) {
        applyRuntimeEvent(event)
      }
    } catch (error) {
      setItems(prev => [
        ...prev,
        {
          type: 'error',
          id: crypto.randomUUID(),
          text: error instanceof Error ? error.message : String(error),
        },
      ])
    } finally {
      setProcessing(false)
    }
  }

  async function handleResumeCommand(command: string) {
    const [, target] = command.split(/\s+/, 2)
    const sessions = await sessionStore.list()
    if (!target) {
      const lines = sessions.slice(0, 8).map(session =>
        `${session.id.slice(0, 8)}  ${session.title}  (${session.messageCount} messages)`,
      )
      setItems(prev => [
        ...prev,
        { type: 'user', id: crypto.randomUUID(), text: command },
        {
          type: 'tool_summary',
          id: crypto.randomUUID(),
          text: lines.length > 0
            ? `Recent sessions:\n${lines.join('\n')}\n\nUse /resume <id> to restore one.`
            : 'No saved sessions found.',
          status: 'completed',
        },
      ])
      return
    }

    const match = sessions.find(session => session.id === target || session.id.startsWith(target))
    if (!match) {
      setItems(prev => [
        ...prev,
        { type: 'user', id: crypto.randomUUID(), text: command },
        { type: 'error', id: crypto.randomUUID(), text: `Session not found: ${target}` },
      ])
      return
    }
    const loaded = await sessionStore.load(match.id)
    agentState.current.sessionId = match.id
    agentState.current.messages = [...loaded.messages]
    agentState.current.turnCount = loaded.messages.filter(message => message.role === 'user').length
    setItems(transcriptFromMessages(loaded.messages))
  }

  function waitForPermission(request: CorePermissionRequest) {
    setPermission(toTuiPermissionRequest(request))
    return new Promise<CorePermissionDecision>(resolve => {
      pendingPermission.current = { request, resolve }
    })
  }

  function applyRuntimeEvent(event: RuntimeEvent) {
    if (event.type === 'assistant_delta') {
      appendAssistantDelta(event.messageId, event.text)
    } else if (event.type === 'tool_call_started') {
      setItems(prev => [
        ...prev,
        {
          type: 'tool_summary',
          id: crypto.randomUUID(),
          text: `Running ${event.call.name}`,
          status: 'running',
        },
      ])
    } else if (event.type === 'tool_call_finished') {
      setItems(prev => [
        ...prev,
        {
          type: event.result.ok ? 'tool_summary' : 'error',
          id: crypto.randomUUID(),
          text: event.result.ok ? summarizeToolResult(event.result.content) : event.result.error ?? event.result.content,
          status: event.result.ok ? 'completed' : undefined as never,
        },
      ])
    } else if (event.type === 'error') {
      setItems(prev => [...prev, { type: 'error', id: crypto.randomUUID(), text: event.error }])
    }
  }

  function appendAssistantDelta(messageId: string, text: string) {
    setItems(prev => {
      const existing = prev.find(item => item.type === 'assistant' && item.id === messageId)
      if (!existing) {
        return [...prev, { type: 'assistant', id: messageId, text }]
      }
      return prev.map(item =>
        item.type === 'assistant' && item.id === messageId
          ? { ...item, text: item.text + text }
          : item,
      )
    })
  }

  function handlePermissionInput(
    input: string,
    key: { return?: boolean; backspace?: boolean; delete?: boolean; escape?: boolean },
  ) {
    if (!permission) return

    if (collectingDenyReason) {
      if (key.return) {
        resolvePermission({ type: 'deny', reason: denyReason.trim() || undefined })
        return
      }
      if (key.escape) {
        setCollectingDenyReason(false)
        setDenyReason('')
        return
      }
      if (key.backspace || key.delete) {
        setDenyReason(prev => prev.slice(0, -1))
        return
      }
      if (input) {
        setDenyReason(prev => prev + input)
      }
      return
    }

    if (input === 'y' || input === '1') {
      resolvePermission({ type: 'allow', remember: false })
    } else if (input === 'p' || input === '2') {
      resolvePermission({ type: 'allow', remember: true })
    } else if (input === 'n' || input === '3' || key.escape) {
      setCollectingDenyReason(true)
    }
  }

  function resolvePermission(decision: PermissionDecision) {
    if (!permission || !pendingPermission.current) return
    const pending = pendingPermission.current
    const coreDecision = toCorePermissionDecision(decision, pending.request)
    const summary =
      decision.type === 'deny'
        ? `Denied ${permission.toolName}${decision.reason ? `: ${decision.reason}` : ''}`
        : decision.remember
          ? `Allowed ${permission.toolName}; future ${permission.prefixRule} commands will skip prompts this session`
          : `Allowed ${permission.toolName}`

    setItems(prev => [
      ...prev,
      decision.type === 'deny'
        ? { type: 'error', id: crypto.randomUUID(), text: summary }
        : { type: 'tool_summary', id: crypto.randomUUID(), text: summary, status: 'completed' },
    ])
    setPermission(undefined)
    setDenyReason('')
    setCollectingDenyReason(false)
    pendingPermission.current = undefined
    pending.resolve(coreDecision)
  }

  if (view === 'tasks') {
    return (
      <TaskBoard
        tasks={tasks}
        cwd={cwd}
        model={model}
        provider={config.providerLabel}
        selectedId={selectedTaskId}
        detailId={detailTaskId}
      />
    )
  }

  return (
    <Box flexDirection="column" minHeight={18}>
      <Header cwd={cwd} model={model} provider={config.providerLabel} />
      <Box flexDirection="column" flexGrow={1} paddingX={1}>
        <Transcript items={items} />
      </Box>
      {permission ? (
        <PermissionPrompt
          request={permission}
          denyReason={denyReason}
          collectingDenyReason={collectingDenyReason}
        />
      ) : null}
      <PromptInput
        disabled={Boolean(permission) || processing || !sessionReady}
        mode={inputMode}
        onModeChange={setInputMode}
        onSubmit={submit}
      />
      <Footer cwd={cwd} model={model} provider={config.providerLabel} mode={inputMode} />
    </Box>
  )
}

function toTuiPermissionRequest(request: CorePermissionRequest): PermissionRequest {
  const command = request.preview.type === 'command'
    ? request.preview.command
    : request.preview.type === 'file'
      ? request.preview.path
      : request.preview.pattern
  return {
    id: request.id,
    toolName: request.toolName,
    command,
    reason: request.check.type === 'ask' ? request.check.reason : 'Allow this tool call?',
    prefixRule: request.suggestions[0]?.pattern ?? command,
  }
}

function toCorePermissionDecision(
  decision: PermissionDecision,
  request: CorePermissionRequest,
): CorePermissionDecision {
  if (decision.type === 'deny') return decision
  if (!decision.remember) return { type: 'allow', remember: false }
  return {
    type: 'allow',
    remember: true,
    rule: request.suggestions[0] ?? {
      id: crypto.randomUUID(),
      scope: 'session',
      toolName: request.toolName,
      pattern: '*',
      behavior: 'allow',
    },
  }
}

function summarizeToolResult(content: string) {
  const clean = content.trim()
  if (!clean) return 'Tool completed'
  const firstLine = clean.split(/\r?\n/)[0] ?? clean
  return firstLine.length > 160 ? `${firstLine.slice(0, 157)}...` : firstLine
}

function transcriptFromMessages(messages: ChatMessage[]): TranscriptItem[] {
  if (messages.length === 0) return createInitialTranscript()
  return messages.flatMap((message): TranscriptItem[] => {
    if (message.role === 'user') {
      return [{ type: 'user' as const, id: message.id, text: message.text }]
    }
    if (message.role === 'assistant') {
      return [{ type: 'assistant' as const, id: message.id, text: message.text }]
    }
    if (message.role === 'tool') {
      return [{ type: 'tool_summary' as const, id: message.id, text: message.text, status: 'completed' as const }]
    }
    return []
  })
}

function createInitialTaskRegistry() {
  const registry = new TaskRegistry()
  registry.create({
    type: 'manual',
    title: 'Review TUI approval flow',
    activity: 'Permission flow is connected to runtime',
    status: 'awaiting_input',
  })
  const archive = registry.create({
    type: 'manual',
    title: 'Archive Python implementation',
    activity: 'Moved to legacy/python',
    status: 'running',
  })
  registry.update(archive.id, { status: 'completed' })
  return registry
}

function taskItemsFromRegistry(registry: TaskRegistry): TaskItem[] {
  return registry.list().map(toTaskItem)
}

function toTaskItem(task: TaskState): TaskItem {
  return {
    id: task.id,
    status: toTuiTaskStatus(task),
    title: task.title,
    activity: task.activity,
    messages: task.messages.length,
    output: task.output,
    age: formatAge(task.updatedAt),
  }
}

function toTuiTaskStatus(task: TaskState): TaskItem['status'] {
  if (task.status === 'awaiting_input') return 'awaiting_input'
  if (task.status === 'completed') return 'completed'
  return 'running'
}

function formatAge(timestamp: number) {
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  return `${Math.floor(minutes / 60)}h`
}

function readOptionalArg(args: string[], name: string): string | true | undefined {
  const index = args.indexOf(name)
  if (index < 0) return undefined
  const value = args[index + 1]
  return value && !value.startsWith('-') ? value : true
}
