import React from 'react'
import { Box, Text } from 'ink'
import { theme } from '../theme.js'
import type { TaskItem, TaskStatus } from '../types.js'

type TaskBoardProps = {
  tasks: TaskItem[]
  cwd: string
  model: string
}

export function TaskBoard({ tasks, cwd, model }: TaskBoardProps) {
  const awaiting = tasks.filter(task => task.status === 'awaiting_input')
  const running = tasks.filter(task => task.status === 'running')
  const completed = tasks.filter(task => task.status === 'completed')

  return (
    <Box flexDirection="column" paddingX={1}>
      <Text color="cyan" bold>
        general-agent
      </Text>
      <Text>
        <Text color={theme.model}>{model}</Text>
        <Text color="gray"> · </Text>
        <Text color={theme.cwd}>{cwd}</Text>
      </Text>
      <Text color={theme.muted}>
        {awaiting.length} awaiting input · {running.length} working · {completed.length} completed
      </Text>
      <TaskGroup title="Needs input" tasks={awaiting} />
      <TaskGroup title="Working" tasks={running} />
      <TaskGroup title="Completed" tasks={completed} />
      <Text color={theme.muted}>Left/right arrow returns to chat. N creates a mock task.</Text>
    </Box>
  )
}

function TaskGroup({ title, tasks }: { title: string; tasks: TaskItem[] }) {
  if (tasks.length === 0) return null
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text color="white" bold>{title}</Text>
      {tasks.map(task => (
        <Text key={task.id} color={statusColor(task.status)}>
          * {task.title}  {task.activity} · {task.age}
        </Text>
      ))}
    </Box>
  )
}

function statusColor(status: TaskStatus) {
  if (status === 'awaiting_input') return 'yellow'
  if (status === 'running') return 'cyan'
  return 'green'
}
