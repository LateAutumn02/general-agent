import React from 'react'
import { Box, Text } from 'ink'
import { renderMarkdownLines } from '../markdown/blocks.js'

type MarkdownTextProps = {
  text: string
  color: string
  columns?: number
}

export function MarkdownText({ text, color, columns = 88 }: MarkdownTextProps) {
  const lines = renderMarkdownLines(text, { color, columns })
  return (
    <Box flexDirection="column">
      {lines.map((line, index) => (
        <Text key={index} color={line.color} bold={line.bold} wrap="truncate">
          {line.text || ' '}
        </Text>
      ))}
    </Box>
  )
}
