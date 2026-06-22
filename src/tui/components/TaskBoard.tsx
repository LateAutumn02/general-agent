import React from 'react'
import { Box, Text } from 'ink'
import { theme } from '../theme.js'
import type { SwarmAgentItem, SwarmMessageItem, TaskItem, TaskStatus } from '../types.js'
import { MarkdownText } from './MarkdownText.js'

type TaskBoardProps = {
  tasks: TaskItem[]
  cwd: string
  model: string
  provider?: string
  selectedId?: string
  detailId?: string
  swarmAgents?: SwarmAgentItem[]
  swarmMessages?: SwarmMessageItem[]
}

export function TaskBoard({
  tasks,
  cwd,
  model,
  provider = 'general-agent',
  selectedId,
  detailId,
  swarmAgents = [],
  swarmMessages = [],
}: TaskBoardProps) {
  const awaiting = tasks.filter(task => task.status === 'awaiting_input')
  const running = tasks.filter(task => task.status === 'running')
  const completed = tasks.filter(task => task.status === 'completed')
  const failed = tasks.filter(task => task.status === 'failed' || task.status === 'cancelled')
  const detailTask = detailId ? tasks.find(task => task.id === detailId) : undefined

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Text color={theme.assistant} bold>general-agent tasks</Text>
      <Text>
        <Text color={theme.model}>{provider}</Text>
        <Text color={theme.muted}> · </Text>
        <Text color={theme.model}>{model}</Text>
        <Text color={theme.muted}> · </Text>
        <Text color={theme.cwd}>{cwd}</Text>
      </Text>
      <Text color={theme.muted}>
        {awaiting.length} awaiting input · {running.length} working · {completed.length} completed
      </Text>
      {detailTask ? (
        <TaskDetail task={detailTask} />
      ) : (
        <>
          <SwarmOverview agents={swarmAgents} messages={swarmMessages} />
          <TaskGroup title="Needs input" tasks={awaiting} selectedId={selectedId} />
          <TaskGroup title="Working" tasks={running} selectedId={selectedId} />
          <TaskGroup title="Completed" tasks={completed} selectedId={selectedId} />
          <TaskGroup title="Failed" tasks={failed} selectedId={selectedId} />
        </>
      )}
      <Box marginTop={1}>
        <Text color={theme.muted}>
          {detailTask
            ? 'Esc returns to tasks · C cancels task'
            : 'Up/down select · Enter opens · C cancels · Right arrow returns'}
        </Text>
      </Box>
    </Box>
  )
}

function SwarmOverview({
  agents,
  messages,
}: {
  agents: SwarmAgentItem[]
  messages: SwarmMessageItem[]
}) {
  if (agents.length === 0 && messages.length === 0) return null
  const running = agents.filter(agent => agent.status === 'starting' || agent.status === 'running')
  const completed = agents.filter(agent => agent.status === 'completed')
  const failed = agents.filter(agent => agent.status === 'failed')
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text color={theme.assistant} bold>Swarm</Text>
      <Text color={theme.muted}>
        {agents.length} agents · {running.length} running · {completed.length} completed · {failed.length} failed · {messages.length} messages
      </Text>
      {agents.length > 0 ? (
        <Box flexDirection="column" marginTop={1}>
          <Text color={theme.assistant}>Agents</Text>
          {agents.slice(0, 8).map(agent => (
            <Text key={agent.id} color={swarmStatusColor(agent.status)}>
              {agent.status === 'running' || agent.status === 'starting' ? '●' : agent.status === 'failed' ? '!' : '✓'} {agent.name}@{agent.teamName}
              <Text color={theme.muted}>  {agent.activity} · sent {agent.sent} · recv {agent.received} · tools {agent.toolUseCount} · {agent.age}</Text>
            </Text>
          ))}
        </Box>
      ) : null}
      {messages.length > 0 ? (
        <Box flexDirection="column" marginTop={1}>
          <Text color={theme.assistant}>Message Flow</Text>
          {messages.slice(-10).map(message => (
            <Text key={message.id} color={theme.accent}>
              {message.from} → {message.broadcast ? 'team' : message.to}
              <Text color={theme.muted}>  {oneLine(message.summary || message.content, 96)}</Text>
            </Text>
          ))}
        </Box>
      ) : null}
    </Box>
  )
}

function TaskGroup({
  title,
  tasks,
  selectedId,
}: {
  title: string
  tasks: TaskItem[]
  selectedId?: string
}) {
  if (tasks.length === 0) return null
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text color={theme.assistant} bold>{title}</Text>
      {tasks.map(task => (
        <Box key={task.id}>
          <Box width={2}>
            <Text color={task.id === selectedId ? theme.user : statusColor(task.status)}>
              {task.id === selectedId ? '\u203a' : '\u273b'}
            </Text>
          </Box>
          <Box flexGrow={1}>
            <Text color={statusColor(task.status)}>
              {task.title}
              <Text color={theme.muted}>  {task.activity} · {task.messages} messages · {task.age}</Text>
            </Text>
          </Box>
        </Box>
      ))}
    </Box>
  )
}

function TaskDetail({ task }: { task: TaskItem }) {
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text color={statusColor(task.status)} bold>{task.title}</Text>
      <Text color={theme.muted}>Status: {task.status} · {task.activity}</Text>
      <Text color={theme.muted}>Messages: {task.messages} · Duration {task.age}</Text>
      <Box marginTop={1} flexDirection="column">
        <Text color={theme.assistant}>Output</Text>
        {task.output
          ? <MarkdownText text={task.output} color={theme.muted} />
          : <Text color={theme.subtle}>No output recorded yet.</Text>}
      </Box>
    </Box>
  )
}

function statusColor(status: TaskStatus) {
  if (status === 'awaiting_input') return theme.model
  if (status === 'running') return theme.accent
  if (status === 'failed' || status === 'cancelled') return theme.error
  return theme.success
}

function swarmStatusColor(status: SwarmAgentItem['status']) {
  if (status === 'starting' || status === 'running') return theme.accent
  if (status === 'failed') return theme.error
  return theme.success
}

function oneLine(text: string | undefined, maxLength: number) {
  const clean = (text ?? '').replace(/\s+/g, ' ').trim()
  if (clean.length <= maxLength) return clean
  return `${clean.slice(0, Math.max(0, maxLength - 3))}...`
}
