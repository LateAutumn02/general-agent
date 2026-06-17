import React from 'react'
import { Box, Text } from 'ink'
import { theme } from '../theme.js'

type HeaderProps = {
  cwd: string
  model: string
  provider: string
}

export function Header({ cwd, model, provider }: HeaderProps) {
  return (
    <Box paddingX={1} paddingTop={1} paddingBottom={1}>
      <Box flexDirection="column" marginRight={2}>
        <Text color={theme.accent}>{'\u2590\u259b\u2588\u2588\u2588\u259c\u258c'}</Text>
        <Text color={theme.accent}>{'\u259d\u259c\u2588\u2588\u2588\u2588\u2588\u259b\u2598'}</Text>
        <Text color={theme.accent}>{'  \u2598\u2598 \u259d\u259d'}</Text>
      </Box>
      <Box flexDirection="column">
        <Text>
          <Text bold color={theme.assistant}>general-agent</Text>
          <Text color={theme.muted}> v0.1.0</Text>
        </Text>
        <Text>
          <Text color={theme.model}>{provider}</Text>
          <Text color={theme.muted}> · </Text>
          <Text color={theme.model}>{model}</Text>
          <Text color={theme.muted}> · </Text>
          <Text color={theme.cwd}>{shortenHome(cwd)}</Text>
        </Text>
      </Box>
    </Box>
  )
}

function shortenHome(path: string) {
  const home = process.env.USERPROFILE ?? process.env.HOME
  if (!home) return path
  return path.toLowerCase().startsWith(home.toLowerCase())
    ? `~${path.slice(home.length)}`
    : path
}
