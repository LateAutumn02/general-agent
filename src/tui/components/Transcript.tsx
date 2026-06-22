import React from 'react'
import { Box, Text, useStdout } from 'ink'
import type { ToolStatus, TranscriptItem } from '../types.js'
import { theme } from '../theme.js'
import { renderMarkdownLines, type MarkdownRenderLine } from '../markdown/blocks.js'

type TranscriptProps = {
  items: TranscriptItem[]
  scrollBack?: number
}

type RenderLine = MarkdownRenderLine

export function Transcript({ items, scrollBack = 0 }: TranscriptProps) {
  const { stdout } = useStdout()
  const rows = Math.max(8, (stdout.rows ?? 30) - 8)
  const columns = Math.max(40, (stdout.columns ?? 100) - 4)
  const lines = flattenTranscript(items, columns)
  const viewport = visibleLines(lines, scrollBack, rows)

  return (
    <Box flexDirection="column" height={rows} overflow="hidden">
      {viewport.lines.map((line, index) => (
        <Text key={`${viewport.start}-${index}`} color={line.color} bold={line.bold} wrap="truncate">
          {line.text || ' '}
        </Text>
      ))}
    </Box>
  )
}

function visibleLines(lines: RenderLine[], scrollBack: number, pageSize: number) {
  const maxBack = Math.max(0, lines.length - pageSize)
  const back = Math.min(Math.max(0, scrollBack), maxBack)
  const end = Math.max(0, lines.length - back)
  const start = Math.max(0, end - pageSize)
  const visible = lines.slice(start, end)
  while (visible.length < pageSize) visible.unshift({ text: '', color: theme.subtle })
  return { start, lines: visible }
}

function flattenTranscript(items: TranscriptItem[], columns: number) {
  const lines: RenderLine[] = []
  for (const item of items) {
    const style = itemStyle(item)
    pushWrapped(lines, style.label, style.labelColor, columns, true)
    const bodyLines = renderMarkdownLines(item.text, {
      color: style.textColor,
      columns: columns - 2,
    })
    for (const line of bodyLines) {
      pushWrapped(lines, `  ${line.text}`, line.color ?? style.textColor, columns, line.bold)
    }
    lines.push({ text: '', color: theme.subtle })
  }
  if (lines.length > 0) lines.pop()
  return lines
}

function itemStyle(item: TranscriptItem) {
  if (item.type === 'user') {
    return { label: 'YOU', labelColor: theme.user, textColor: theme.user }
  }
  if (item.type === 'tool_summary') {
    const color = toolStatusColor(item.status)
    return { label: toolLabel(item.status), labelColor: color, textColor: theme.muted }
  }
  if (item.type === 'error') {
    return { label: 'ERR', labelColor: theme.error, textColor: theme.error }
  }
  return { label: 'AGENT', labelColor: theme.assistant, textColor: theme.assistant }
}

function pushWrapped(lines: RenderLine[], text: string, color: string, columns: number, bold = false) {
  const width = Math.max(20, columns)
  const raw = text || ''
  for (let index = 0; index < raw.length || index === 0; index += width) {
    lines.push({ text: raw.slice(index, index + width), color, bold })
    if (!raw) break
  }
}

function toolLabel(status: ToolStatus) {
  if (status === 'running') return 'TOOL...'
  if (status === 'failed') return 'TOOL!'
  if (status === 'cancelled') return 'TOOL-X'
  return 'TOOL'
}

function toolStatusColor(status: ToolStatus) {
  if (status === 'running') return theme.accent
  if (status === 'failed' || status === 'cancelled') return theme.error
  return theme.bash
}
