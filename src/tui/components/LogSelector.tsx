import React, { useEffect, useState } from 'react'
import { Box, Text, useInput } from 'ink'
import chalk from 'chalk'
import type { SessionRecord } from '../../session/types.js'
import { Spinner } from './Spinner.js'

export type LogSelectorProps = {
  logs: SessionRecord[]
  loading: boolean
  onSelect: (log: SessionRecord) => void
  onCancel: () => void
}

export function LogSelector({ logs, loading, onSelect, onCancel }: LogSelectorProps) {
  const [selectedIndex, setSelectedIndex] = useState(0)

  useEffect(() => {
    setSelectedIndex(0)
  }, [logs])

  useInput((input, key) => {
    if (loading || logs.length === 0) return
    const rawKey = key as Record<string, unknown>
    const isUp = rawKey.upArrow || input === 'k' || (typeof input === 'string' && input.includes('\x1b[A')) || rawKey.wheelUp
    const isDown = rawKey.downArrow || input === 'j' || (typeof input === 'string' && input.includes('\x1b[B')) || rawKey.wheelDown
    if (isUp) { setSelectedIndex(prev => Math.max(0, prev - 1)); return }
    if (isDown) { setSelectedIndex(prev => Math.min(logs.length - 1, prev + 1)); return }
    if (rawKey.return) { const s = logs[Math.min(selectedIndex, logs.length - 1)]; if (s) onSelect(s); return }
    if (rawKey.escape) { onCancel(); return }
  })

  if (loading) {
    return (
      <Box paddingX={1} paddingY={1}>
        <Spinner />
        <Text> Loading conversations…</Text>
      </Box>
    )
  }

  if (logs.length === 0) {
    return <Text>No conversations found to resume. Press Esc to go back.</Text>
  }

  const visible = logs.slice(0, 20)
  const lines: string[] = []

  lines.push(chalk.hex('#F6D58B').bold('Recent conversations') + '  (arrows/jk navigate, Enter select, Esc cancel)')
  lines.push('')

  const gold = chalk.hex('#F6D58B')
  const white = chalk.hex('#E6E6E6')

  for (let i = 0; i < visible.length; i++) {
    const log = visible[i]!
    const selected = i === selectedIndex
    const marker = selected ? gold.bold('▶') : ' '
    const id = (log.id ?? '').slice(0, 8)
    const count = log.messageCount ?? 0
    const time = formatDate(log.updatedAt ?? Date.now())
    const title = log.firstPrompt || log.title || 'Untitled session'

    const meta = `${id}  ${count}m  ${time}`
    const metaColored = selected ? gold(meta) : meta
    const titleColored = selected ? white(`  ${title}`) : `  ${title}`

    lines.push(`${marker} ${metaColored}`)
    lines.push(titleColored)
  }

  if (logs.length > 20) {
    lines.push('')
    lines.push(`...and ${logs.length - 20} more sessions`)
  }

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Text>{lines.join('\n')}</Text>
    </Box>
  )
}

function formatDate(ts: number): string {
  const d = Math.floor((Date.now() - ts) / 1000)
  if (d < 60) return 'just now'
  if (d < 3600) return `${Math.floor(d / 60)}m ago`
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`
  if (d < 604800) return `${Math.floor(d / 86400)}d ago`
  const dt = new Date(ts)
  return `${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
}
