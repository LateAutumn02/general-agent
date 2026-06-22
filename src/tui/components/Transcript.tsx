import React from 'react'
import { Box, Text, useStdout } from 'ink'
import chalk from 'chalk'
import type { AgentProgressLine, TeammateMessageType, ToolStatus, TranscriptItem } from '../types.js'
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
  if (line.color === '#F6D58B') text = chalk.hex('#F6D58B')(text)
  else if (line.color === '#E6E6E6') text = chalk.hex('#E6E6E6')(text)
  else if (line.color === '#9FCF9B') text = chalk.hex('#9FCF9B')(text)
  else if (line.color === '#FF6B6B') text = chalk.hex('#FF6B6B')(text)
  else if (line.color === '#C3A6FF') text = chalk.hex('#C3A6FF')(text)
  else if (line.color === '#807B6E') text = chalk.hex('#807B6E')(text)
  else if (line.color === '#5F5F5F') text = chalk.hex('#5F5F5F')(text)
  else if (line.color === '#00FFFF') text = chalk.hex('#00FFFF')(text)
  else if (line.color === '#FF00FF') text = chalk.hex('#FF00FF')(text)
  else if (line.color === '#0000FF') text = chalk.hex('#0000FF')(text)
  else if (line.color === '#00FF00') text = chalk.hex('#00FF00')(text)
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
    switch (item.type) {
      case 'user':
        pushLabel(lines, 'YOU', '#F6D58B', columns)
        pushBody(lines, item.text, '#F6D58B', columns)
        break
      case 'assistant':
        pushLabel(lines, 'AGENT', '#E6E6E6', columns)
        pushBody(lines, item.text, '#E6E6E6', columns)
        break
      case 'tool_summary':
        pushToolSummary(lines, item.text, item.status, columns)
        break
      case 'error':
        pushLabel(lines, 'ERR', '#FF6B6B', columns)
        pushBody(lines, item.text, '#FF6B6B', columns)
        break
      case 'tool_group':
        pushToolGroup(lines, item.toolName, item.count, item.summary, item.status, columns)
        break
      case 'agent_progress':
        pushAgentProgress(lines, item.agents, item.status, columns)
        break
      case 'swarm_message':
        pushSwarmMessage(lines, item.teamName, item.from, item.to, item.summary, item.content, item.broadcast, columns)
        break
      case 'teammate_message':
        pushTeammateMessage(lines, item.from, item.color, item.messageType, item.summary, item.content, columns)
        break
    }
    lines.push({ text: '', color: '#5F5F5F' })
  }
  if (lines.length > 0) lines.pop()
  return lines
}

// ---- Item renderers ----

function pushLabel(lines: RenderLine[], label: string, color: string, columns: number) {
  pushWrapped(lines, label, color, columns, true)
}

function pushBody(lines: RenderLine[], text: string, color: string, columns: number) {
  const truncated = text.length > 500 && !text.startsWith('Resumed')
    ? text.slice(0, 500) + `... (${text.length} chars)`
    : text
  const bodyLines = renderMarkdownLines(truncated, { color, columns: columns - 2 })
  for (const line of bodyLines) {
    pushWrapped(lines, `  ${line.text}`, line.color ?? color, columns, line.bold)
  }
}

function pushToolGroup(lines: RenderLine[], toolName: string, count: number, summary: string, status: ToolStatus, columns: number) {
  const color = status === 'running' ? '#C3A6FF' : '#9FCF9B'
  const icon = status === 'running' ? '...' : 'TOOL'
  pushWrapped(lines, `${icon} ${toolName} x${count}`, color, columns, true)
  pushWrapped(lines, `  ${summary.slice(0, 200)}`, '#807B6E', columns)
}

function pushToolSummary(lines: RenderLine[], text: string, status: ToolStatus, columns: number) {
  const color = status === 'running' ? '#C3A6FF' : status === 'failed' ? '#FF6B6B' : '#9FCF9B'
  const label = status === 'running' ? '...' : status === 'failed' ? 'TOOL!' : 'TOOL'
  pushWrapped(lines, label, color, columns, true)
  pushWrapped(lines, `  ${text.slice(0, 300)}`, '#807B6E', columns)
}

function pushAgentProgress(lines: RenderLine[], agents: AgentProgressLine[], status: string, columns: number) {
  const isLast = (i: number) => i === agents.length - 1
  const headerColor = status === 'running' ? '#C3A6FF' : '#9FCF9B'
  const count = agents.length

  pushWrapped(lines, status === 'running' ? `Running ${count} agent${count > 1 ? 's' : ''}...` : `${count} agent${count > 1 ? 's' : ''} finished`, headerColor, columns, true)

  for (let i = 0; i < agents.length; i++) {
    const a = agents[i]!
    const tree = isLast(i) ? '└' : '├'  // └ or ├
    const color = a.status === 'completed' ? '#9FCF9B' : a.status === 'failed' ? '#FF6B6B' : a.status === 'running' ? '#C3A6FF' : '#807B6E'
    const name = a.agentType
    pushWrapped(lines, ` ${tree} ${name}  ${a.toolUseCount} tools  ${a.description.slice(0, 40)}`, color, columns)
  }
}

function pushTeammateMessage(
  lines: RenderLine[], from: string, color: string,
  messageType: TeammateMessageType, summary: string, content: string, columns: number,
) {
  const typeIcons: Record<TeammateMessageType, string> = {
    task_completed: '✓',  // ✓
    task_assignment: '#',
    shutdown_request: '✗',  // ✗
    shutdown_response: '→',  // →
    idle_notification: 'Z',
    text: '@',
  }
  const icon = typeIcons[messageType] ?? '@'
  const labelColor = messageType === 'task_completed' ? '#9FCF9B' : messageType === 'shutdown_request' ? '#FF6B6B' : '#C3A6FF'
  pushWrapped(lines, `${icon} @${from}`, labelColor, columns, true)
  pushWrapped(lines, `  ${summary || content.slice(0, 200)}`, '#807B6E', columns)
}

function pushSwarmMessage(
  lines: RenderLine[],
  teamName: string,
  from: string,
  to: string,
  summary: string | undefined,
  content: string,
  broadcast: boolean,
  columns: number,
) {
  const target = broadcast ? 'team' : to
  pushWrapped(lines, `MSG ${from} -> ${target}  [${teamName}]`, '#C3A6FF', columns, true)
  pushWrapped(lines, `  ${summary || content.slice(0, 180)}`, '#807B6E', columns)
  if (summary && content.trim() && content.trim() !== summary.trim()) {
    pushWrapped(lines, `  ${content.slice(0, 240)}`, '#E6E6E6', columns)
  }
}

// ---- Helpers ----

function pushWrapped(lines: RenderLine[], text: string, color: string, columns: number, bold = false) {
  const width = Math.max(20, columns)
  const raw = text || ''
  for (let index = 0; index < raw.length || index === 0; index += width) {
    lines.push({ text: raw.slice(index, index + width), color, bold })
    if (!raw) break
  }
}
