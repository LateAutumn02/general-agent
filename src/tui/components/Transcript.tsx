import React from 'react'
import { Box, Text } from 'ink'
import type { TranscriptItem } from '../types.js'
import { theme } from '../theme.js'

type TranscriptProps = {
  items: TranscriptItem[]
}

export function Transcript({ items }: TranscriptProps) {
  return (
    <Box flexDirection="column">
      {items.map((item, index) => (
        <React.Fragment key={item.id}>
          <TranscriptRow item={item} />
          {index < items.length - 1 ? (
            <Text color={theme.separator}>{'\u2500'.repeat(37)}</Text>
          ) : null}
        </React.Fragment>
      ))}
    </Box>
  )
}

function TranscriptRow({ item }: { item: TranscriptItem }) {
  if (item.type === 'user') {
    return <Text color={theme.user}>{'\u203a'} {item.text}</Text>
  }

  if (item.type === 'tool_summary') {
    return <Text color={theme.muted}>{'\u2022'} {item.text}</Text>
  }

  if (item.type === 'error') {
    return <Text color={theme.error}>{'\u2022'} {item.text}</Text>
  }

  return <Text color={theme.assistant}>{'\u2022'} {item.text}</Text>
}
