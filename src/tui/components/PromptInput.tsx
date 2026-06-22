import React, { useEffect, useState } from 'react'
import { Box, Text, useInput } from 'ink'
import type { PromptMode } from '../types.js'
import { theme } from '../theme.js'

type PromptInputProps = {
  disabled?: boolean
  mode: PromptMode
  onModeChange: (mode: PromptMode) => void
  onSubmit: (value: string, mode: PromptMode) => void
}

export function PromptInput({
  disabled = false,
  mode,
  onModeChange,
  onSubmit,
}: PromptInputProps) {
  const [value, setValue] = useState('')

  useEffect(() => {
    if (value.startsWith('!')) {
      onModeChange('bash')
      setValue(value.slice(1))
    }
  }, [onModeChange, value])

  useInput((input, key) => {
    if (disabled) return
    if (isMouseSequence(input)) return
    if (key.return) {
      onSubmit(value, mode)
      setValue('')
      onModeChange('prompt')
      return
    }
    if (key.backspace || key.delete) {
      setValue(prev => prev.slice(0, -1))
      return
    }
    if (key.escape) {
      setValue('')
      onModeChange('prompt')
      return
    }
    if (input && !key.ctrl && !key.meta) {
      setValue(prev => prev + input)
    }
  })

  const prompt = mode === 'bash' ? '$' : '\u203a'
  const placeholder = mode === 'bash' ? 'shell command' : 'Ask general-agent'
  const displayValue = disabled ? 'waiting for tool approval' : value || placeholder

  return (
    <Box paddingX={1} backgroundColor={theme.inputBackground}>
      <Text backgroundColor={theme.inputBackground} color={mode === 'bash' ? theme.bash : theme.user}>
        {prompt}
      </Text>
      <Text backgroundColor={theme.inputBackground} color={theme.inputText}>
        {' '}{displayValue}
      </Text>
    </Box>
  )
}

function isMouseSequence(input: string) {
  return input.includes('\x1b[<')
    || input.includes('\x1b[M')
    || input.includes('[<')
    || input.includes('[M')
    || /\[<[^;]{1,12};\d+;\d+[mM]/.test(input)
    || /\x1b\[M[\s\S]{3}/.test(input)
}
