import React, { useState } from 'react'
import { Box, Text, useInput } from 'ink'
import chalk from 'chalk'
import type { PermissionRequest, PermissionDecision } from '../types.js'

type PermissionPromptProps = {
  request: PermissionRequest
  denyReason: string
  collectingDenyReason: boolean
  onDecision: (decision: PermissionDecision) => void
  onDenyReasonChange: (reason: string) => void
  onDenyCancel: () => void
}

export function PermissionPrompt({
  request,
  denyReason,
  collectingDenyReason,
  onDecision,
  onDenyReasonChange,
  onDenyCancel,
}: PermissionPromptProps) {
  const [selected, setSelected] = useState(0)
  const opts = ['Allow once', 'Allow & remember', 'Deny']

  useInput((input, key) => {
    if (collectingDenyReason) {
      if (key.return) { onDecision({ type: 'deny', reason: denyReason.trim() || undefined }); return }
      if (key.escape) { onDenyCancel(); return }
      if (key.backspace || key.delete) { onDenyReasonChange(denyReason.slice(0, -1)); return }
      if (input && !key.ctrl && !key.meta) { onDenyReasonChange(denyReason + input) }
      return
    }

    const rawKey = key as Record<string, unknown>
    if (rawKey.upArrow || input === 'k') { setSelected(prev => Math.max(0, prev - 1)); return }
    if (rawKey.downArrow || input === 'j') { setSelected(prev => Math.min(2, prev + 1)); return }
    if (rawKey.return) { apply(selected); return }
    if (input === '1') { apply(0); return }
    if (input === '2') { apply(1); return }
    if (input === '3' || rawKey.escape) { apply(2); return }
  })

  function apply(index: number) {
    if (index === 0) onDecision({ type: 'allow', remember: false })
    else if (index === 1) onDecision({ type: 'allow', remember: true })
    else onDecision({ type: 'deny' })
  }

  const gold = chalk.hex('#F6D58B')
  const white = chalk.hex('#E6E6E6')
  const muted = chalk.hex('#807B6E')

  if (collectingDenyReason) {
    const lines = [
      gold.bold(`• Deny ${request.toolName}`),
      '',
      muted('Reason: ') + white(denyReason || 'type a note and press Enter'),
      '',
      muted('Enter to confirm  Esc to cancel'),
    ]
    return <Box flexDirection="column" paddingX={1} paddingY={1}><Text>{lines.join('\n')}</Text></Box>
  }

  const lines: string[] = []
  lines.push(gold.bold(`• ${request.toolName}`))
  lines.push(muted(`  ${request.reason}`))
  lines.push(gold(`  $ ${request.command}`))
  lines.push('')

  for (let i = 0; i < opts.length; i++) {
    const sel = i === selected
    const prefix = sel ? gold.bold('▶') : ' '
    const num = gold(`${i + 1}`)
    const label = sel ? white.bold(opts[i]!) : muted(opts[i]!)
    lines.push(`${prefix} ${num}. ${label}`)
  }

  lines.push('')
  lines.push(muted('↑↓ select  1/2/3 shortcut  Enter confirm'))

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Text>{lines.join('\n')}</Text>
    </Box>
  )
}
