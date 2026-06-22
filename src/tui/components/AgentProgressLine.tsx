import React from 'react'
import { Box, Text } from 'ink'
import chalk from 'chalk'
import type { AgentProgressLine as AgentProgressLineType } from '../types.js'

type Props = {
  agents: AgentProgressLineType[]
  status: 'running' | 'completed'
}

/**
 * Agent 执行进度树形展示。
 * 对应 cc-haha 的 AgentProgressLine 组件。
 */
export function AgentProgressLineView({ agents, status }: Props) {
  const gold = chalk.hex('#F6D58B')
  const green = chalk.hex('#9FCF9B')
  const purple = chalk.hex('#C3A6FF')
  const muted = chalk.hex('#807B6E')
  const count = agents.length
  const headerColor = status === 'running' ? purple : green

  const lines: string[] = []
  lines.push(headerColor(`Running ${count} agent${count > 1 ? 's' : ''}...`))

  for (let i = 0; i < agents.length; i++) {
    const a = agents[i]!
    const isLast = i === agents.length - 1
    const tree = isLast ? '└' : '├'
    const lineColor = a.status === 'completed' ? green : a.status === 'running' ? purple : muted
    const line = ` ${tree} ${a.agentType}  ${a.toolUseCount} tools  ${a.description.slice(0, 50)}`
    lines.push(lineColor(line))
  }

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Text>{lines.join('\n')}</Text>
    </Box>
  )
}
