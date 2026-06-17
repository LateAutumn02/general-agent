import React from 'react'
import { Box, Text } from 'ink'
import { theme } from '../theme.js'
import type { TaskItem, TaskStatus } from '../types.js'

type TaskBoardProps = {
  tasks: TaskItem[]
  cwd: string
  model: string
  provider?: string
}

export function TaskBoard({ tasks, cwd, model, provider = 'general-agent' }: TaskBoardProps) {
  const awaiting = tasks.filter(task => task.status === 'awaiting_input')
  const running = tasks.filter(task => task.status === 'running')
  const completed = tasks.filter(task => task.status === 'completed')

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
      <TaskGroup title="Needs input" tasks={awaiting} />
      <TaskGroup title="Working" tasks={running} />
      <TaskGroup title="Completed" tasks={completed} />
      <Box marginTop={1}>
        <Text color={theme.muted}>Right arrow returns to chat · N creates a task placeholder</Text>
      </Box>
    </Box>
  )
}

function TaskGroup({ title, tasks }: { title: string; tasks: TaskItem[] }) {
  if (tasks.length === 0) return null
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text color={theme.assistant} bold>{title}</Text>
      {tasks.map(task => (
        <Box key={task.id}>
          <Box width={2}><Text color={statusColor(task.status)}>{'\u273b'}</Text></Box>
          <Box flexGrow={1}>
            <Text color={statusColor(task.status)}>
              {task.title}
              <Text color={theme.muted}>  {task.activity} · {task.age}</Text>
            </Text>
          </Box>
        </Box>
      ))}
    </Box>
  )
}

function statusColor(status: TaskStatus) {
  if (status === 'awaiting_input') return theme.model
  if (status === 'running') return theme.accent
  return theme.success
}
