import React from 'react'
import { Box, Text } from 'ink'
import chalk from 'chalk'
import type { AgentPill } from '../types.js'

type FooterProps = {
  permissionMode?: string
  agentPills?: AgentPill[]
  processing?: boolean
  hasTasks?: boolean
}

export function Footer({ permissionMode = 'default', agentPills, processing, hasTasks }: FooterProps) {
  const hasPills = agentPills && agentPills.length > 0

  // Permission mode display
  const modeConfig: Record<string, { symbol: string; title: string; color: string }> = {
    default: { symbol: '', title: 'Ask', color: '#807B6E' },
    acceptEdits: { symbol: '⏵⏵', title: 'Accept Edits', color: '#9FCF9B' },
    bypassPermissions: { symbol: '⏵⏵', title: 'Bypass', color: '#FF6B6B' },
    plan: { symbol: '⏸', title: 'Plan', color: '#C3A6FF' },
  }
  const mc = modeConfig[permissionMode] ?? modeConfig.default
  const modeLabel = mc.title

  const muted = chalk.hex('#807B6E')
  const gold = chalk.hex('#F6D58B')
  const green = chalk.hex('#9FCF9B')
  const red = chalk.hex('#FF6B6B')
  const purple = chalk.hex('#C3A6FF')

  const colorFn = permissionMode === 'bypassPermissions' ? red
    : permissionMode === 'acceptEdits' ? green
    : permissionMode === 'plan' ? purple
    : muted

  // Build lines as simple strings
  const lines: string[] = []
  const parts: string[] = []

  // Permission mode
  parts.push(colorFn(`${mc.symbol} ${modeLabel}`))

  // Agent pills
  if (hasPills) {
    for (const pill of agentPills!) {
      const hex = { yellow: '#F6D58B', green: '#9FCF9B', cyan: '#00FFFF', magenta: '#FF00FF', blue: '#0000FF', red: '#FF6B6B' }[pill.color] ?? '#807B6E'
      const c = chalk.hex(hex)
      parts.push(pill.isSelected ? c.bold(`[${pill.name}]`) : c(`[${pill.name}]`))
    }
  }

  // Hints
  if (processing) {
    parts.push(muted('ctrl+c / esc to cancel'))
  } else if (hasTasks) {
    parts.push(muted('ctrl+t tasks'))
  }

  lines.push(parts.join('  '))

  return (
    <Box paddingX={1} flexDirection="column">
      <Text>{lines.join('\n')}</Text>
    </Box>
  )
}
