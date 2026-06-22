import React, { useState } from 'react'
import { Box, Text, useInput } from 'ink'
import chalk from 'chalk'

type PermissionMode = 'default' | 'acceptEdits' | 'bypassPermissions'

type Props = {
  currentMode: string
  onSelect: (mode: PermissionMode) => void
  onCancel: () => void
}

const MODES: { mode: PermissionMode; label: string; desc: string }[] = [
  { mode: 'default', label: 'default', desc: 'Ask for every tool (normal behavior)' },
  { mode: 'acceptEdits', label: 'acceptEdits', desc: 'Auto-approve Edit/Write, ask for others' },
  { mode: 'bypassPermissions', label: 'bypassPermissions', desc: 'Skip all permission prompts' },
]

export function PermissionSelector({ currentMode, onSelect, onCancel }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0)

  useInput((input, key) => {
    const rawKey = key as Record<string, unknown>
    const isUp = rawKey.upArrow || input === 'k' || (typeof input === 'string' && input.includes('\x1b[A')) || rawKey.wheelUp
    const isDown = rawKey.downArrow || input === 'j' || (typeof input === 'string' && input.includes('\x1b[B')) || rawKey.wheelDown

    if (isUp) { setSelectedIndex(prev => Math.max(0, prev - 1)); return }
    if (isDown) { setSelectedIndex(prev => Math.min(MODES.length - 1, prev + 1)); return }
    if (rawKey.return) { onSelect(MODES[Math.min(selectedIndex, MODES.length - 1)]!.mode); return }
    if (rawKey.escape) { onCancel(); return }
  })

  const gold = chalk.hex('#F6D58B')
  const muted = chalk.hex('#807B6E')

  const lines: string[] = []
  lines.push(gold.bold('Select permission mode') + muted(` (current: ${currentMode})`))
  lines.push('')

  for (let i = 0; i < MODES.length; i++) {
    const m = MODES[i]!
    const sel = i === selectedIndex
    const prefix = sel ? gold.bold('▶') : ' '
    const label = sel ? gold.bold(m.label) : m.label
    const desc = sel ? gold(`  ${m.desc}`) : muted(`  ${m.desc}`)
    lines.push(`${prefix} ${label}`)
    lines.push(desc)
  }

  lines.push('')
  lines.push(muted('↑↓ navigate  Enter select  Esc cancel'))

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Text>{lines.join('\n')}</Text>
    </Box>
  )
}
