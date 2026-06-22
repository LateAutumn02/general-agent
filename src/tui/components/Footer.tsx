import React from 'react'
import { Box, Text } from 'ink'
import type { PromptMode, AgentPill } from '../types.js'
import { theme } from '../theme.js'

type FooterProps = {
  cwd: string
  model: string
  provider: string
  mode: PromptMode
  agentPills?: AgentPill[]
}

export function Footer({ cwd, model, provider, mode, agentPills }: FooterProps) {
  const hasPills = agentPills && agentPills.length > 0

  return (
    <Box paddingX={1} flexDirection="column">
      <Box>
        <Text color={theme.model}>{provider}</Text>
        <Text color="gray"> · </Text>
        <Text color={theme.model}>{model}</Text>
        <Text color="gray">  </Text>
        <Text color={theme.cwd}>{cwd}</Text>
        <Text color="gray">  </Text>
        <Text color={mode === 'bash' ? theme.bash : theme.muted}>
          {mode === 'bash' ? 'shell shortcut' : '! shell shortcut'}
        </Text>
      </Box>
      {hasPills ? (
        <Box>
          {agentPills!.map(pill => {
            const pillColors: Record<AgentPill['color'], string> = {
              yellow: theme.user,
              green: theme.bash,
              cyan: theme.accent,
              magenta: theme.error,
              blue: theme.model,
              red: theme.error,
            }
            return (
              <Text key={pill.name} color={pill.isSelected ? pillColors[pill.color] : theme.muted}>
                {pill.isMain ? '[main]' : `[@${pill.name}]`}{' '}
              </Text>
            )
          })}
        </Box>
      ) : null}
    </Box>
  )
}
