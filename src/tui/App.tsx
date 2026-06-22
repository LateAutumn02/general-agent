import React, { useEffect, useMemo, useRef, useState } from 'react'
import { join } from 'node:path'
import chalk from 'chalk'
import { Box, Text, useApp, useInput } from 'ink'
import { runAgentTurn } from '../agent/loop.js'
import type { AgentState } from '../agent/types.js'
import { createModelClient } from '../api/modelFactory.js'
import { compactMessages } from '../compact/compact.js'
import { loadRuntimeConfig } from '../config/runtimeConfig.js'
import { PermissionController } from '../permissions/controller.js'
import { loadMemory } from '../memory/store.js'
import type {
  PermissionDecision as CorePermissionDecision,
  PermissionRequest as CorePermissionRequest,
} from '../permissions/types.js'
import type { RuntimeEvent } from '../runtime/events.js'
import { JsonlSessionStore } from '../session/store.js'
import type { ChatMessage, SessionRecord } from '../session/types.js'
import { loadDefaultSkills } from '../skills/loader.js'
import { MultiAgentManager } from '../multi-agent/manager.js'
import { createSwarmPlanFromGoal } from '../swarm/planner.js'
import { TaskRegistry } from '../tasks/registry.js'
import type { TaskState } from '../tasks/types.js'
import { Footer } from './components/Footer.js'
import { Header } from './components/Header.js'
import { LogSelector } from './components/LogSelector.js'
import { PermissionPrompt } from './components/PermissionPrompt.js'
import { PromptInput } from './components/PromptInput.js'
import { Spinner } from './components/Spinner.js'
import { TaskBoard } from './components/TaskBoard.js'
import { Transcript } from './components/Transcript.js'
import { createInitialTranscript } from './mockRuntime.js'
import { SLASH_COMMANDS, formatSlashCommandHelp } from './slashCommands.js'
import type { PermissionDecision, PermissionRequest, PromptMode, TaskItem, TranscriptItem } from './types.js'

type AppProps = {
  args: string[]
  cwd: string
}

type PendingPermission = {
  request: CorePermissionRequest
  resolve: (decision: CorePermissionDecision) => void
}

/** /resume 命令的 UI 状态 */
type ResumeView =
  | null
  | { type: 'loading' }
  | { type: 'resuming'; sessionId: string }
  | { type: 'picker'; logs: SessionRecord[]; loading: boolean }

export function App({ args, cwd }: AppProps) {
  const { exit } = useApp()
  const [inputMode, setInputMode] = useState<PromptMode>('prompt')
  const [permission, setPermission] = useState<PermissionRequest | undefined>()
  const [denyReason, setDenyReason] = useState('')
  const [collectingDenyReason, setCollectingDenyReason] = useState(false)
  const [view, setView] = useState<'chat' | 'tasks'>('chat')
  const [chatScrollBack, setChatScrollBack] = useState(0)
  const [selectedTaskId, setSelectedTaskId] = useState<string | undefined>()
  const [detailTaskId, setDetailTaskId] = useState<string | undefined>()
  const [processing, setProcessing] = useState(false)
  const [sessionReady, setSessionReady] = useState(false)
  const [promptValue, setPromptValue] = useState('')
  const [resumeView, setResumeView] = useState<ResumeView>(null)
  const resumeViewRef = useRef<ResumeView>(null)
  resumeViewRef.current = resumeView
  const taskRegistry = useMemo(() => createInitialTaskRegistry(), [])
  const [tasks, setTasks] = useState<TaskItem[]>(() => taskItemsFromRegistry(taskRegistry))
  const config = useMemo(() => loadRuntimeConfig(args, cwd), [args, cwd])
  const [currentModel, setCurrentModel] = useState(config.model)
  const [items, setItems] = useState<TranscriptItem[]>(() => createInitialTranscript(config.providerLabel, config.model))
  const modelClient = useMemo(() => createModelClient(config), [config])
  const permissionController = useMemo(() => new PermissionController(config.permissionMode), [config.permissionMode])
  const agentState = useRef<AgentState>({
    sessionId: crypto.randomUUID(),
    messages: [],
    turnCount: 0,
    cwd,
    model: currentModel,
  })
  const pendingPermission = useRef<PendingPermission | undefined>(undefined)
  const activeTurnController = useRef<AbortController | undefined>(undefined)
  const sessionStore = useMemo(() => new JsonlSessionStore(join(cwd, '.general-agent', 'sessions')), [cwd])

  // ---- Session initialization (--resume / --continue) ----

  useEffect(() => {
    let cancelled = false
    async function loadSession() {
      const resumeTarget = readOptionalArg(args, '--resume') ?? readOptionalArg(args, '-r')
      const continueFlag = hasFlag(args, '--continue')

      // --continue: resume most recent session
      if (continueFlag) {
        const sessions = await sessionStore.list({ limit: 1 })
        if (sessions.length > 0) {
          const loaded = await sessionStore.load(sessions[0]!.id)
          if (cancelled) return
          applyResumedSession(loaded.record, loaded.messages)
          setSessionReady(true)
          return
        }
      }

      // --resume <uuid>
      if (resumeTarget !== undefined) {
        if (resumeTarget === true) {
          // --resume without arg: pick most recent
          const sessions = await sessionStore.list({ limit: 1 })
          if (sessions.length > 0) {
            const loaded = await sessionStore.load(sessions[0]!.id)
            if (cancelled) return
            applyResumedSession(loaded.record, loaded.messages)
            setSessionReady(true)
            return
          }
        } else {
          // --resume <id>
          let record: SessionRecord | null
          let messages: ChatMessage[]

          if (JsonlSessionStore.isValidUuid(resumeTarget)) {
            // Try full load first
            try {
              const loaded = await sessionStore.load(resumeTarget)
              record = loaded.record
              messages = loaded.messages
            } catch {
              // Fallback: try lite lookup
              record = await sessionStore.getLastSessionLog(resumeTarget)
              if (record) {
                const loaded = await sessionStore.load(record.id)
                messages = loaded.messages
              } else {
                record = null
                messages = []
              }
            }
          } else {
            // Prefix match
            const sessions = await sessionStore.list()
            const found = sessions.find(s => s.id.startsWith(resumeTarget))
            if (found) {
              const loaded = await sessionStore.load(found.id)
              record = loaded.record
              messages = loaded.messages
            } else {
              record = null
              messages = []
            }
          }

          if (record && !cancelled) {
            applyResumedSession(record, messages)
            setSessionReady(true)
            return
          }
        }
      }

      // Normal startup: create new session
      const session = await sessionStore.create({ cwd, model: agentState.current.model, title: 'general-agent session' })
      if (cancelled) return
      agentState.current.sessionId = session.id
      setSessionReady(true)
    }
    void loadSession()
    return () => {
      cancelled = true
    }
  }, [args, cwd, sessionStore, config.providerLabel])

  function applyResumedSession(record: SessionRecord, messages: ChatMessage[]) {
    agentState.current.sessionId = record.id
    agentState.current.messages = [...messages]
    agentState.current.turnCount = messages.filter(m => m.role === 'user').length
    agentState.current.model = record.model
    setCurrentModel(record.model)
    setItems(transcriptFromMessages(messages))
  }

  // ---- Global input handling ----

  useInput((input, key) => {
    // Resume view active — block all chat input (picker handles its own useInput)
    if (resumeViewRef.current) {
      return
    }

    if (permission) {
      handlePermissionInput(input, key)
      return
    }

    if (key.ctrl && input === 'c' && activeTurnController.current) {
      activeTurnController.current.abort('cancelled by user')
      setItems(prev => [...prev, { type: 'error', id: crypto.randomUUID(), text: 'Cancelled current turn' }])
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

    if (view === 'chat' && !promptValue.startsWith('/')) {
      const wheel = getWheelDirection(input, key)
      if (key.pageUp) {
        setChatScrollBack(prev => prev + 12)
        return
      }
      if (key.pageDown) {
        setChatScrollBack(prev => Math.max(0, prev - 12))
        return
      }
      if (key.upArrow || input.toLowerCase() === 'k' || wheel === 'up') {
        setChatScrollBack(prev => prev + 3)
        return
      }
      if (key.downArrow || input.toLowerCase() === 'j' || wheel === 'down') {
        setChatScrollBack(prev => Math.max(0, prev - 3))
        return
      }
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

  // ---- Submit handler ----

  async function submit(text: string, mode: PromptMode) {
    const trimmed = text.trim()
    if (!trimmed || processing || !sessionReady) return

    if (trimmed === '/exit' || trimmed === '/quit') {
      await sessionStore.flush(agentState.current.sessionId)
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
          text: `Available commands:\n${formatSlashCommandHelp()}\n\nPrefix ! to run a shell shortcut.`,
        },
      ])
      return
    }

    if (trimmed === '/model' || trimmed.startsWith('/model ')) {
      await handleModelCommand(trimmed)
      return
    }

    if (trimmed === '/memory' || trimmed.startsWith('/memory ')) {
      await handleMemoryCommand(trimmed)
      return
    }

    if (trimmed === '/skills') {
      await handleSkillsCommand(trimmed)
      return
    }

    if (trimmed.startsWith('/') && await maybeHandleSkillCommand(trimmed)) {
      return
    }

    if (trimmed === '/resume' || trimmed.startsWith('/resume ')) {
      await handleResumeCommand(trimmed)
      return
    }

    if (trimmed === '/continue') {
      setItems(prev => [...prev, { type: 'user', id: crypto.randomUUID(), text: trimmed }])
      const sessions = await sessionStore.list({ limit: 1 })
      if (sessions.length === 0) {
        setItems(prev => [
          ...prev,
          { type: 'error', id: crypto.randomUUID(), text: 'No conversations found to resume.' },
        ])
        return
      }
      const loaded = await sessionStore.load(sessions[0]!.id)
      applyResumedSession(loaded.record, loaded.messages)
      setItems(prev => [
        ...prev,
        {
          type: 'tool_summary',
          id: crypto.randomUUID(),
          text: `Resumed session ${loaded.record.id.slice(0, 8)}`,
          status: 'completed',
        },
      ])
      return
    }

    if (trimmed.startsWith('/swarm ')) {
      await handleSwarmCommand(trimmed)
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
          text: `Compacted ${result.removedMessageIds.length} messages · ${result.beforeCharacters} -> ${result.afterCharacters} chars`,
          status: 'completed',
        },
      ])
      await sessionStore.append(agentState.current.sessionId, {
        type: 'message',
        message: result.summaryMessage,
      })
      return
    }

    if (trimmed.startsWith('/')) {
      setItems(prev => [
        ...prev,
        { type: 'user', id: crypto.randomUUID(), text: trimmed },
        {
          type: 'error',
          id: crypto.randomUUID(),
          text: `Unknown command: ${trimmed.split(/\s+/, 1)[0]}. Use /help to see available commands.`,
        },
      ])
      return
    }

    setProcessing(true)
    agentState.current.model = currentModel
    setItems(prev => [...prev, { type: 'user', id: crypto.randomUUID(), text: trimmed }])
    const turnController = new AbortController()
    activeTurnController.current = turnController
    let watchdog = createTurnWatchdog(turnController, config.turnTimeoutMs)
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
        signal: turnController.signal,
        async decidePermission(permissionEvent) {
          return await waitForPermission(permissionEvent.request)
        },
      })) {
        watchdog.refresh()
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
      watchdog.clear()
      if (activeTurnController.current === turnController) activeTurnController.current = undefined
      setProcessing(false)
    }
  }

  // ---- Slash command handlers ----

  async function handleModelCommand(command: string) {
    const nextModel = command.slice('/model'.length).trim()
    if (!nextModel) {
      setItems(prev => [
        ...prev,
        { type: 'user', id: crypto.randomUUID(), text: command },
        {
          type: 'tool_summary',
          id: crypto.randomUUID(),
          text: `Current model: ${currentModel}\nUse /model <model-name> to switch, for example /model deepseek-v4-flash or /model qwen-plus.`,
          status: 'completed',
        },
      ])
      return
    }

    setCurrentModel(nextModel)
    agentState.current.model = nextModel
    await sessionStore.append(agentState.current.sessionId, {
      type: 'metadata',
      patch: { model: nextModel },
    })
    setItems(prev => [
      ...prev,
      { type: 'user', id: crypto.randomUUID(), text: command },
      {
        type: 'tool_summary',
        id: crypto.randomUUID(),
        text: `Switched model to ${nextModel}`,
        status: 'completed',
      },
    ])
  }

  async function handleSwarmCommand(command: string) {
    const goal = command.slice('/swarm '.length).trim()
    if (!goal) return
    const plan = createSwarmPlanFromGoal(goal)
    const manager = new MultiAgentManager(taskRegistry)
    const agentTasks = plan.members.map(member => manager.createAgentTask({
      description: `${member.profile.name}: ${goal}`,
      prompt: member.prompt,
      profile: member.profile.name,
      allowedTools: member.profile.allowedTools,
    }, agentState.current.sessionId))
    for (const task of agentTasks) {
      await sessionStore.append(agentState.current.sessionId, {
        type: 'task_state',
        task: toTaskItem(task),
      })
    }
    setSelectedTaskId(agentTasks[0]?.id)
    setTasks(taskItemsFromRegistry(taskRegistry))
    setItems(prev => [
      ...prev,
      { type: 'user', id: crypto.randomUUID(), text: command },
      {
        type: 'tool_summary',
        id: crypto.randomUUID(),
        text: `Created swarm plan for "${goal}":\n${agentTasks.map(task => `- ${task.profile.name}: ${task.prompt}`).join('\n')}`,
        status: 'completed',
      },
    ])
  }

  async function handleMemoryCommand(command: string) {
    const memory = await loadMemory(cwd)
    const files = memory.files.map(file => `- ${file.path} (${file.content.length} chars)`)
    setItems(prev => [
      ...prev,
      { type: 'user', id: crypto.randomUUID(), text: command },
      {
        type: 'tool_summary',
        id: crypto.randomUUID(),
        text: files.length > 0
          ? `Loaded memory files:\n${files.join('\n')}`
          : 'No memory files found. Create MEMORY.md or .general-agent/MEMORY.md to add project memory.',
        status: 'completed',
      },
    ])
  }

  async function handleSkillsCommand(command: string) {
    const skills = await loadDefaultSkills(cwd)
    setItems(prev => [
      ...prev,
      { type: 'user', id: crypto.randomUUID(), text: command },
      {
        type: 'tool_summary',
        id: crypto.randomUUID(),
        text: skills.length > 0
          ? `Available skills:\n${skills.map(skill => `- /${skill.name}: ${skill.description}`).join('\n')}`
          : 'No skills found under skills/ or .general-agent/skills/.',
        status: 'completed',
      },
    ])
  }

  async function maybeHandleSkillCommand(command: string) {
    const name = command.slice(1).split(/\s+/, 1)[0]
    if (!name) return false
    const skills = await loadDefaultSkills(cwd)
    const skill = skills.find(candidate => candidate.name === name)
    if (!skill) return false
    const message: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'system',
      text: `Skill activated: ${skill.name}\n${skill.content}`,
      createdAt: Date.now(),
    }
    agentState.current.messages.push(message)
    await sessionStore.append(agentState.current.sessionId, { type: 'message', message })
    setItems(prev => [
      ...prev,
      { type: 'user', id: crypto.randomUUID(), text: command },
      {
        type: 'tool_summary',
        id: crypto.randomUUID(),
        text: `Activated skill ${skill.name}: ${skill.description}`,
        status: 'completed',
      },
    ])
    return true
  }

  // ---- /resume command (3 dispatch paths) ----

  async function handleResumeCommand(command: string) {
    const arg = command.slice('/resume'.length).trim()

    // Path A: no argument — show interactive picker
    if (!arg) {
      setResumeView({ type: 'picker', logs: [], loading: true })
      setItems(prev => [...prev, { type: 'user', id: crypto.randomUUID(), text: command }])
      try {
        const sessions = await sessionStore.list()
        const filtered = sessions.filter(s => s.id !== agentState.current.sessionId && s.messageCount > 0)
        if (filtered.length === 0) {
          setItems(prev => [
            ...prev,
            { type: 'error', id: crypto.randomUUID(), text: 'No conversations found to resume.' },
          ])
          setResumeView(null)
          return
        }
        setResumeView({ type: 'picker', logs: filtered, loading: false })
      } catch {
        setItems(prev => [
          ...prev,
          { type: 'error', id: crypto.randomUUID(), text: 'Failed to load conversations.' },
        ])
        setResumeView(null)
      }
      return
    }

    // Path B: UUID lookup
    if (JsonlSessionStore.isValidUuid(arg)) {
      setItems(prev => [...prev, { type: 'user', id: crypto.randomUUID(), text: command }])

      // Try enriched list first
      const sessions = await sessionStore.list()
      const match = sessions
        .filter(s => s.id === arg)
        .sort((a, b) => b.updatedAt - a.updatedAt)[0]

      let record: SessionRecord | null = match ?? null

      // Fallback: direct file lookup for sessions dropped by enrich
      if (!record) {
        record = await sessionStore.getLastSessionLog(arg)
      }

      if (record) {
        const loaded = await sessionStore.load(record.id)
        applyResumedSession(loaded.record, loaded.messages)
        setItems(prev => [
          ...prev,
          {
            type: 'tool_summary',
            id: crypto.randomUUID(),
            text: `Resumed session ${arg.slice(0, 8)}`,
            status: 'completed',
          },
        ])
        return
      }

      setItems(prev => [
        ...prev,
        { type: 'error', id: crypto.randomUUID(), text: `Session ${arg} was not found.` },
      ])
      return
    }

    // Path C: title match (exact customTitle)
    setItems(prev => [...prev, { type: 'user', id: crypto.randomUUID(), text: command }])
    const sessions = await sessionStore.list()
    const titleMatches = sessions.filter(
      s => s.customTitle === arg || s.firstPrompt === arg,
    )

    if (titleMatches.length === 1) {
      const loaded = await sessionStore.load(titleMatches[0]!.id)
      applyResumedSession(loaded.record, loaded.messages)
      setItems(prev => [
        ...prev,
        {
          type: 'tool_summary',
          id: crypto.randomUUID(),
          text: `Resumed session "${arg}"`,
          status: 'completed',
        },
      ])
      return
    }

    if (titleMatches.length > 1) {
      setItems(prev => [
        ...prev,
        {
          type: 'error',
          id: crypto.randomUUID(),
          text: `Found ${titleMatches.length} sessions matching "${arg}". Please use /resume to pick a specific session.`,
        },
      ])
      return
    }

    // No match at all
    setItems(prev => [
      ...prev,
      { type: 'error', id: crypto.randomUUID(), text: `Session ${arg} was not found.` },
    ])
  }

  // ---- LogSelector callbacks ----

  function handleLogSelect(log: SessionRecord) {
    setResumeView({ type: 'resuming', sessionId: log.id })
    // Defer load out of the useInput event chain to avoid React state deadlock
    const id = log.id
    setTimeout(() => {
      void (async () => {
        try {
          const loaded = await sessionStore.load(id)
          if (!loaded || loaded.messages.length === 0) {
            throw new Error('Session has no messages to restore')
          }
          agentState.current.sessionId = loaded.record.id
          agentState.current.messages = [...loaded.messages]
          agentState.current.turnCount = loaded.messages.filter(m => m.role === 'user').length
          agentState.current.model = loaded.record.model
          setCurrentModel(loaded.record.model)
          const transcriptItems: TranscriptItem[] = []
          for (const m of loaded.messages) {
            if (m.role === 'user') transcriptItems.push({ type: 'user', id: m.id, text: m.text })
            else if (m.role === 'assistant') transcriptItems.push({ type: 'assistant', id: m.id, text: m.text })
            else if (m.role === 'tool') {
              const short = m.text.length > 300 ? m.text.slice(0, 300) + `... (${m.text.length} chars)` : m.text
              transcriptItems.push({ type: 'tool_summary', id: m.id, text: short, status: 'completed' })
            }
          }
          setResumeView(null)
          setItems([
            ...transcriptItems,
            { type: 'tool_summary' as const, id: crypto.randomUUID(), text: `Resumed ${loaded.record.firstPrompt?.slice(0, 40) || loaded.record.title}`, status: 'completed' as const },
          ])
        } catch (error) {
          setResumeView(null)
          setItems(prev => [...prev, { type: 'error', id: crypto.randomUUID(), text: `Failed to resume: ${error instanceof Error ? error.message : String(error)}` }])
        }
      })()
    }, 0)
  }

  function handleLogCancel() {
    setItems(prev => [
      ...prev,
      { type: 'tool_summary', id: crypto.randomUUID(), text: 'Resume cancelled', status: 'completed' },
    ])
    setResumeView(null)
  }

  // ---- Permission handling ----

  function waitForPermission(request: CorePermissionRequest) {
    setPermission(toTuiPermissionRequest(request))
    return new Promise<CorePermissionDecision>(resolve => {
      pendingPermission.current = { request, resolve }
    })
  }

  function applyRuntimeEvent(event: RuntimeEvent) {
    if (event.type === 'model_request_started') {
      if (event.afterTool) {
        setItems(prev => [
          ...prev,
          {
            type: 'tool_summary',
            id: crypto.randomUUID(),
            text: 'Continuing after tool result',
            status: 'running',
          },
        ])
      }
    } else if (event.type === 'assistant_delta') {
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

  // ---- Render ----

  if (view === 'tasks') {
    return (
      <TaskBoard
        tasks={tasks}
        cwd={cwd}
        model={currentModel}
        provider={config.providerLabel}
        selectedId={selectedTaskId}
        detailId={detailTaskId}
      />
    )
  }

  return (
    <Box flexDirection="column" minHeight={18}>
      <Header cwd={cwd} model={currentModel} provider={config.providerLabel} />
      <Box flexDirection="column" flexGrow={1} paddingX={1}>
        {resumeView ? (
          <ResumeViewDisplay
            resumeView={resumeView}
            onSelect={handleLogSelect}
            onCancel={handleLogCancel}
          />
        ) : (
          <Transcript items={items} scrollBack={chatScrollBack} />
        )}
      </Box>
      {permission ? (
        <PermissionPrompt
          request={permission}
          denyReason={denyReason}
          collectingDenyReason={collectingDenyReason}
        />
      ) : null}
      {resumeView ? null : (
        <PromptInput
          disabled={Boolean(permission) || processing || !sessionReady}
          mode={inputMode}
          value={promptValue}
          slashCommands={SLASH_COMMANDS}
          onChange={setPromptValue}
          onModeChange={setInputMode}
          onSubmit={submit}
        />
      )}
      <Footer cwd={cwd} model={currentModel} provider={config.providerLabel} mode={inputMode} />
    </Box>
  )

}

// ---------------------------------------------------------------------------
// ResumeViewDisplay — renders the /resume UI state (pure display, no useInput)
// ---------------------------------------------------------------------------

function ResumeViewDisplay({
  resumeView,
  onSelect,
  onCancel,
}: {
  resumeView: ResumeView & {}
  onSelect: (log: SessionRecord) => void
  onCancel: () => void
}) {
  if (resumeView.type === 'loading' || resumeView.type === 'picker') {
    return (
      <LogSelector
        logs={resumeView.type === 'picker' ? resumeView.logs : []}
        loading={resumeView.type === 'loading' || resumeView.loading}
        onSelect={onSelect}
        onCancel={onCancel}
      />
    )
  }

  if (resumeView.type === 'resuming') {
    return (
      <Box paddingX={1} paddingY={1}>
        <Spinner />
        <Text>{chalk.hex('#F6D58B')(' Resuming conversation…')}</Text>
      </Box>
    )
  }

  return null
}

// ---------------------------------------------------------------------------
// Helper functions (unchanged from original)
// ---------------------------------------------------------------------------

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
    if (message.role === 'system') {
      return []
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

function getWheelDirection(
  input: string,
  key: { [name: string]: unknown },
): 'up' | 'down' | undefined {
  if (key.wheelUp === true) return 'up'
  if (key.wheelDown === true) return 'down'
  return parseMouseWheel(input)
}

function parseMouseWheel(input: string): 'up' | 'down' | undefined {
  for (const match of input.matchAll(/\x1b\[<(\d+);\d+;\d+[mM]/g)) {
    const code = Number(match[1])
    if ((code & 64) === 64) return (code & 1) === 1 ? 'down' : 'up'
  }
  for (const match of input.matchAll(/\x1b\[M([\s\S])([\s\S])([\s\S])/g)) {
    const button = (match[1]?.charCodeAt(0) ?? 32) - 32
    if ((button & 64) === 64) return (button & 1) === 1 ? 'down' : 'up'
  }
  return undefined
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

function hasFlag(args: string[], name: string): boolean {
  return args.includes(name)
}

function createTurnWatchdog(controller: AbortController, timeoutMs: number) {
  let timer: Timer | undefined
  const refresh = () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      controller.abort(`No runtime event for ${Math.max(1, Math.ceil(timeoutMs / 1000))}s`)
    }, timeoutMs)
  }
  refresh()
  return {
    refresh,
    clear() {
      if (timer) clearTimeout(timer)
    },
  }
}

