import React from 'react'
import { Box, Text, useStdout } from 'ink'
import chalk from 'chalk'
import type { ToolStatus, TranscriptItem } from '../types.js'
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
      <Text>{viewport.lines.map(l => colorizeLine(l)).join('\n')}</Text>
    </Box>
  )
}

function colorizeLine(line: RenderLine): string {
  let text = line.text || ' '
  if (line.color === '#F6D58B') text = chalk.hex('#F6D58B')(text)        // user (yellow)
  else if (line.color === '#E6E6E6') text = chalk.hex('#E6E6E6')(text)  // assistant (white)
  else if (line.color === '#9FCF9B') text = chalk.hex('#9FCF9B')(text)  // success/bash (green)
  else if (line.color === '#FF6B6B') text = chalk.hex('#FF6B6B')(text)  // error (red)
  else if (line.color === '#C3A6FF') text = chalk.hex('#C3A6FF')(text)  // accent (purple)
  else if (line.color === '#807B6E') text = chalk.hex('#807B6E')(text)  // muted (gray-brown)
  else if (line.color === '#5F5F5F') text = chalk.hex('#5F5F5F')(text)  // subtle (dark gray)
  if (line.bold) text = chalk.bold(text)
  return text
}

function visibleLines(lines: RenderLine[], scrollBack: number, pageSize: number) {
  const maxBack = Math.max(0, lines.length - pageSize)
  const back = Math.min(Math.max(0, scrollBack), maxBack)
  const end = Math.max(0, lines.length - back)
  const start = Math.max(0, end - pageSize)
  const visible = lines.slice(start, end)
  while (visible.length < pageSize) visible.unshift({ text: '', color: '#5F5F5F' })
  return { start, lines: visible }
}

function flattenTranscript(items: TranscriptItem[], columns: number) {
  const lines: RenderLine[] = []
  for (const item of items) {
    const style = itemStyle(item)
    pushWrapped(lines, style.label, style.labelColor, columns, true)
    // Truncate tool output to avoid freezing on huge results (e.g. grep on large repos)
    const text = item.type === 'tool_summary' && item.text.length > 500
      ? item.text.slice(0, 500) + `... (${item.text.length} chars)`
      : item.text
    const bodyLines = renderMarkdownLines(text, {
      color: style.textColor,
      columns: columns - 2,
    })
    for (const line of bodyLines) {
      pushWrapped(lines, `  ${line.text}`, line.color ?? style.textColor, columns, line.bold)
    }
    lines.push({ text: '', color: '#5F5F5F' })
  }
  if (lines.length > 0) lines.pop()
  return lines
}

function itemStyle(item: TranscriptItem) {
  if (item.type === 'user') {
    return { label: 'YOU', labelColor: '#F6D58B', textColor: '#F6D58B' }
  }
  if (item.type === 'tool_summary') {
    const color = toolStatusColor(item.status)
    return { label: toolLabel(item.status), labelColor: color, textColor: '#807B6E' }
  }
  if (item.type === 'error') {
    return { label: 'ERR', labelColor: '#FF6B6B', textColor: '#FF6B6B' }
  }
  return { label: 'AGENT', labelColor: '#E6E6E6', textColor: '#E6E6E6' }
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

function toolStatusColor(status: ToolStatus): string {
  if (status === 'running') return '#C3A6FF'
  if (status === 'failed' || status === 'cancelled') return '#FF6B6B'
  return '#9FCF9B'
}
