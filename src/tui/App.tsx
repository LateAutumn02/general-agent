import React, { useMemo, useState } from 'react'
import { Box, Text, useApp, useInput } from 'ink'
import { Footer } from './components/Footer.js'
import { PermissionPrompt } from './components/PermissionPrompt.js'
import { PromptInput } from './components/PromptInput.js'
import { TaskBoard } from './components/TaskBoard.js'
import { Transcript } from './components/Transcript.js'
import { createInitialTranscript, nextAssistantReply } from './mockRuntime.js'
import type { PermissionDecision, PermissionRequest, PromptMode, TaskItem, TranscriptItem } from './types.js'

type AppProps = {
  args: string[]
  cwd: string
}

export function App({ args, cwd }: AppProps) {
  const { exit } = useApp()
  const [items, setItems] = useState<TranscriptItem[]>(() => createInitialTranscript())
  const [inputMode, setInputMode] = useState<PromptMode>('prompt')
  const [permission, setPermission] = useState<PermissionRequest | undefined>()
  const [denyReason, setDenyReason] = useState('')
  const [collectingDenyReason, setCollectingDenyReason] = useState(false)
  const [view, setView] = useState<'chat' | 'tasks'>('chat')
  const [tasks, setTasks] = useState<TaskItem[]>(() => createInitialTasks())
  const model = useMemo(() => resolveModel(args), [args])

  useInput((input, key) => {
    if (permission) {
      handlePermissionInput(input, key)
      return
    }

    if (key.leftArrow) {
      setView('tasks')
      return
    }
    if (key.rightArrow) {
      setView('chat')
      return
    }
    if (view === 'tasks' && input.toLowerCase() === 'n') {
      setTasks(prev => [
        {
          id: crypto.randomUUID(),
          status: 'awaiting_input',
          title: 'New mock task',
          activity: 'Waiting for instructions',
          age: '0s',
        },
        ...prev,
      ])
    }
  })

  function submit(text: string, mode: PromptMode) {
    const trimmed = text.trim()
    if (!trimmed) return

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

    if (mode === 'bash') {
      const request = createPermissionRequest(trimmed)
      setItems(prev => [
        ...prev,
        { type: 'user', id: crypto.randomUUID(), text: `!${trimmed}` },
        {
          type: 'tool_summary',
          id: crypto.randomUUID(),
          text: `Running ${trimmed}`,
          status: 'pending',
        },
      ])
      setPermission(request)
      return
    }

    setItems(prev => [
      ...prev,
      { type: 'user', id: crypto.randomUUID(), text: trimmed },
      nextAssistantReply(trimmed, mode),
    ])
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
    if (!permission) return
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
  }

  if (view === 'tasks') {
    return <TaskBoard tasks={tasks} cwd={cwd} model={model} />
  }

  return (
    <Box flexDirection="column" minHeight={18}>
      <Box paddingX={1} paddingY={1}>
        <Text color="cyan" bold>
          general-agent
        </Text>
        <Text color="gray">  TypeScript rewrite preview</Text>
      </Box>
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
        disabled={Boolean(permission)}
        mode={inputMode}
        onModeChange={setInputMode}
        onSubmit={submit}
      />
      <Footer cwd={cwd} model={model} mode={inputMode} />
    </Box>
  )
}

function resolveModel(args: string[]) {
  const modelIndex = args.findIndex(arg => arg === '--model')
  if (modelIndex >= 0 && args[modelIndex + 1]) {
    return args[modelIndex + 1]
  }
  return process.env.ANTHROPIC_MODEL ?? process.env.GENERAL_AGENT_MODEL ?? 'model-not-set'
}

function createPermissionRequest(command: string): PermissionRequest {
  const prefixRule = command.split(/\s+/).slice(0, 2).join(' ') || command
  return {
    id: crypto.randomUUID(),
    toolName: 'Bash',
    command,
    reason: 'This is a preview approval flow for shell commands.',
    prefixRule,
  }
}

function createInitialTasks(): TaskItem[] {
  return [
    {
      id: crypto.randomUUID(),
      status: 'awaiting_input',
      title: 'Review TUI approval flow',
      activity: 'Permission mock is waiting for input',
      age: '1m',
    },
    {
      id: crypto.randomUUID(),
      status: 'completed',
      title: 'Archive Python implementation',
      activity: 'Moved to legacy/python',
      age: 'done',
    },
  ]
}
