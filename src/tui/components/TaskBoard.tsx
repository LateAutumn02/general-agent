import React from 'react'
import { Box, Text } from 'ink'
import { theme } from '../theme.js'
import type { TaskItem, TaskStatus } from '../types.js'

type TaskBoardProps = {
  tasks: TaskItem[]
  cwd: string
  model: string
  provider?: string
  selectedId?: string
  detailId?: string
}

export function TaskBoard({
  tasks,
  cwd,
  model,
  provider = 'general-agent',
  selectedId,
  detailId,
}: TaskBoardProps) {
  const awaiting = tasks.filter(task => task.status === 'awaiting_input')
  const running = tasks.filter(task => task.status === 'running')
  const completed = tasks.filter(task => task.status === 'completed')
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
          <TaskGroup title="Needs input" tasks={awaiting} selectedId={selectedId} />
          <TaskGroup title="Working" tasks={running} selectedId={selectedId} />
          <TaskGroup title="Completed" tasks={completed} selectedId={selectedId} />
        </>
      )}
      <Box marginTop={1}>
        <Text color={theme.muted}>
          {detailTask
            ? 'Esc returns to tasks · C cancels task'
            : 'Up/down select · Enter opens · N creates · C cancels · Right arrow returns'}
        </Text>
      </Box>
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
      <Text color={theme.muted}>Messages: {task.messages} · Updated {task.age}</Text>
      <Box marginTop={1} flexDirection="column">
        <Text color={theme.assistant}>Output</Text>
        <Text color={task.output ? theme.muted : theme.subtle}>
          {task.output || 'No output recorded yet.'}
        </Text>
      </Box>
    </Box>
  )
}

function statusColor(status: TaskStatus) {
  if (status === 'awaiting_input') return theme.model
  if (status === 'running') return theme.accent
  return theme.success
}
