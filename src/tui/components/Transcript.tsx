import React from 'react'
import { Box, Text } from 'ink'
import type { TranscriptItem } from '../types.js'
import { theme } from '../theme.js'
import { MarkdownText } from './MarkdownText.js'

type TranscriptProps = {
  items: TranscriptItem[]
}

export function Transcript({ items }: TranscriptProps) {
  return (
    <Box flexDirection="column" paddingBottom={1}>
      {items.map(item => (
        <Box key={item.id} marginBottom={1}>
          <TranscriptRow item={item} />
        </Box>
      ))}
    </Box>
  )
}

function TranscriptRow({ item }: { item: TranscriptItem }) {
  if (item.type === 'user') {
    return (
      <Box>
        <Box width={2}><Text color={theme.user}>{'\u203a'}</Text></Box>
        <Box flexGrow={1}><Text color={theme.user} wrap="wrap">{item.text}</Text></Box>
      </Box>
    )
  }

  if (item.type === 'tool_summary') {
    return <MessageRow bulletColor={theme.muted} textColor={theme.muted} text={item.text} />
  }

  if (item.type === 'error') {
    return <MessageRow bulletColor={theme.error} textColor={theme.error} text={item.text} />
  }

  return <MessageRow bulletColor={theme.assistant} textColor={theme.assistant} text={item.text} />
}

function MessageRow({
  bulletColor,
  textColor,
  text,
}: {
  bulletColor: string
  textColor: string
  text: string
}) {
  return (
    <Box>
      <Box width={2}><Text color={bulletColor}>{'\u2022'}</Text></Box>
      <Box flexGrow={1}><MarkdownText text={text} color={textColor} /></Box>
    </Box>
  )
}
