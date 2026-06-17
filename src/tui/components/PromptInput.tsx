import React, { useEffect, useState } from 'react'
import { Box, Text, useInput } from 'ink'
import type { PromptMode } from '../types.js'
import { theme } from '../theme.js'

type PromptInputProps = {
  mode: PromptMode
  onModeChange: (mode: PromptMode) => void
  onSubmit: (value: string, mode: PromptMode) => void
}

export function PromptInput({ mode, onModeChange, onSubmit }: PromptInputProps) {
  const [value, setValue] = useState('')

  useEffect(() => {
    if (value.startsWith('!')) {
      onModeChange('bash')
      setValue(value.slice(1))
    }
  }, [onModeChange, value])

  useInput((input, key) => {
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

  const prompt = mode === 'bash' ? '$' : '›'
  const placeholder = mode === 'bash' ? 'shell command' : 'Ask general-agent'

  return (
    <Box paddingX={1} paddingY={0}>
      <Text backgroundColor={theme.inputBackground} color={theme.inputText}>
        {prompt} {value || placeholder}
      </Text>
    </Box>
  )
}
