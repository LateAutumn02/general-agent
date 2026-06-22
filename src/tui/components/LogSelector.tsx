import React, { useEffect, useState } from 'react'
import { Box, Text, useInput, useStdout } from 'ink'
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
  const [scrollOffset, setScrollOffset] = useState(0)
  const { stdout } = useStdout()
  // Each item takes 2 lines (id + title), plus header = 3 lines, minus padding
  const viewportRows = Math.max(5, (stdout?.rows ?? 30) - 6)
  const visibleCount = Math.floor(viewportRows / 2)

  useEffect(() => {
    setSelectedIndex(0)
    setScrollOffset(0)
  }, [logs])

  // Auto-scroll: keep selected item visible (only on selectedIndex change)
  useEffect(() => {
    setScrollOffset(prev => {
      if (selectedIndex < prev) return selectedIndex
      if (selectedIndex >= prev + visibleCount) return selectedIndex - visibleCount + 1
      return prev
    })
  }, [selectedIndex, visibleCount])

  useInput((input, key) => {
    if (loading || logs.length === 0) return
    const rawKey = key as Record<string, unknown>

    // Arrow keys + j/k = move selection
    const isUp = rawKey.upArrow || input === 'k' || (typeof input === 'string' && input.includes('\x1b[A'))
    const isDown = rawKey.downArrow || input === 'j' || (typeof input === 'string' && input.includes('\x1b[B'))

    if (isUp) { setSelectedIndex(prev => Math.max(0, prev - 1)); return }
    if (isDown) { setSelectedIndex(prev => Math.min(logs.length - 1, prev + 1)); return }

    // Wheel = scroll (not select)
    if (rawKey.wheelUp || (typeof input === 'string' && input.includes('\x1b[M'))) {
      const wheelDir = getWheelDirection(input, rawKey)
      if (wheelDir === 'up') setScrollOffset(prev => Math.max(0, prev - 3))
      if (wheelDir === 'down') setScrollOffset(prev => Math.min(Math.max(0, logs.length - visibleCount), prev + 3))
      return
    }

    if (rawKey.return) { const s = logs[Math.min(selectedIndex, logs.length - 1)]; if (s) onSelect(s); return }
    if (rawKey.escape) { onCancel(); return }
  })

  if (loading) {
    return <Box paddingX={1} paddingY={1}><Spinner /><Text> Loading conversations…</Text></Box>
  }

  if (logs.length === 0) {
    return <Text>No conversations found to resume. Press Esc to go back.</Text>
  }

  const maxOffset = Math.max(0, logs.length - visibleCount)
  const safeOffset = Math.min(scrollOffset, maxOffset)
  const visible = logs.slice(safeOffset, safeOffset + visibleCount)

  const gold = chalk.hex('#F6D58B')
  const white = chalk.hex('#E6E6E6')
  const muted = chalk.hex('#807B6E')

  const lines: string[] = []
  lines.push(gold.bold('Recent conversations') + muted(`  (↑↓ select  wheel scroll  Enter open  Esc cancel)`))
  if (safeOffset > 0) lines.push(muted(`  ... ${safeOffset} more above`))

  for (let i = 0; i < visible.length; i++) {
    const log = visible[i]!
    const actualIndex = safeOffset + i
    const selected = actualIndex === selectedIndex
    const marker = selected ? gold.bold('▶') : ' '
    const id = (log.id ?? '').slice(0, 8)
    const count = log.messageCount ?? 0
    const time = formatDate(log.updatedAt ?? Date.now())
    const rawTitle = (log.firstPrompt || log.title || 'Untitled session').replace(/\s+/g, ' ').trim()
    const title = rawTitle.length > 70 ? rawTitle.slice(0, 67) + '…' : rawTitle

    lines.push(selected ? gold(`${marker} ${id}  ${count}m  ${time}`) : `  ${id}  ${count}m  ${time}`)
    lines.push(selected ? white(`  ${title}`) : muted(`  ${title}`))
  }

  if (safeOffset + visibleCount < logs.length) {
    lines.push(muted(`  ... ${logs.length - safeOffset - visibleCount} more below`))
  }

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Text>{lines.join('\n')}</Text>
    </Box>
  )
}

function getWheelDirection(input: string, key: Record<string, unknown>): 'up' | 'down' | undefined {
  if (key.wheelUp === true) return 'up'
  if (key.wheelDown === true) return 'down'
  if (typeof input !== 'string') return undefined
  // Parse mouse wheel escape sequences: \x1b[<64;...M (up) or \x1b[<65;...M (down)
  const match = input.matchAll(/\x1b\[<(\d+);\d+;\d+[mM]/g)
  for (const m of match) {
    const code = Number(m[1])
    if ((code & 64) === 64) return (code & 1) === 1 ? 'down' : 'up'
  }
  return undefined
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
