import React from 'react'
import { Box, Text } from 'ink'
import { theme } from '../theme.js'

type MarkdownTextProps = {
  text: string
  color: string
}

export function MarkdownText({ text, color }: MarkdownTextProps) {
  const lines = text.split(/\r?\n/)
  const nodes: React.ReactNode[] = []
  let inCodeBlock = false

  lines.forEach((line, index) => {
    if (line.trim().startsWith('```')) {
      inCodeBlock = !inCodeBlock
      return
    }

    if (inCodeBlock) {
      nodes.push(
        <Box key={index} paddingX={1} backgroundColor={theme.inputBackground}>
          <Text backgroundColor={theme.inputBackground} color={theme.cwd}>{line || ' '}</Text>
        </Box>,
      )
      return
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line)
    if (heading) {
      nodes.push(
        <Text key={index} color={theme.assistant} bold>
          {heading[2]}
        </Text>,
      )
      return
    }

    const listItem = /^\s*([-*]|\d+\.)\s+(.+)$/.exec(line)
    if (listItem) {
      nodes.push(
        <Text key={index} color={color} wrap="wrap">
          <Text color={theme.muted}>  {listItem[1]} </Text>
          {renderInline(listItem[2] ?? '', color)}
        </Text>,
      )
      return
    }

    if (!line.trim()) {
      nodes.push(<Text key={index}> </Text>)
      return
    }

    nodes.push(
      <Text key={index} color={color} wrap="wrap">
        {renderInline(line, color)}
      </Text>,
    )
  })

  return <Box flexDirection="column">{nodes}</Box>
}

function renderInline(line: string, color: string) {
  const parts = line.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <Text key={index} color={theme.cwd} backgroundColor={theme.inputBackground}>
          {part.slice(1, -1)}
        </Text>
      )
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <Text key={index} color={color} bold>
          {part.slice(2, -2)}
        </Text>
      )
    }
    return part
  })
}
