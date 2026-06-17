import React from 'react'
import { Box, Text } from 'ink'
import type { PromptMode } from '../types.js'
import { theme } from '../theme.js'

type FooterProps = {
  cwd: string
  model: string
  provider: string
  mode: PromptMode
}

export function Footer({ cwd, model, provider, mode }: FooterProps) {
  return (
    <Box paddingX={1} backgroundColor={theme.inputBackground}>
      <Text color={theme.model}>{provider}</Text>
      <Text color="gray"> · </Text>
      <Text color={theme.model}>{model}</Text>
      <Text color="gray">  </Text>
      <Text color={theme.cwd}>{cwd}</Text>
      <Text color="gray">  </Text>
      <Text color={mode === 'bash' ? theme.bash : theme.muted}>
        {mode === 'bash' ? '! bash mode' : '! for bash mode'}
      </Text>
    </Box>
  )
}
