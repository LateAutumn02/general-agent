import React, { useEffect, useState } from 'react'
import { Box, Text, useInput } from 'ink'
import type { PromptMode } from '../types.js'
import { theme } from '../theme.js'
import type { SlashCommand } from '../slashCommands.js'

type PromptInputProps = {
  disabled?: boolean
  mode: PromptMode
  value: string
  slashCommands?: SlashCommand[]
  onChange: (value: string) => void
  onModeChange: (mode: PromptMode) => void
  onSubmit: (value: string, mode: PromptMode) => void
}

export function PromptInput({
  disabled = false,
  mode,
  value,
  slashCommands = [],
  onChange,
  onModeChange,
  onSubmit,
}: PromptInputProps) {
  const [selectedSuggestion, setSelectedSuggestion] = useState(0)
  const suggestions = getSlashSuggestions(value, slashCommands)
  const showingSuggestions = !disabled && mode === 'prompt' && suggestions.length > 0

  useEffect(() => {
    if (value.startsWith('!')) {
      onModeChange('bash')
      onChange(value.slice(1))
    }
  }, [onChange, onModeChange, value])

  useEffect(() => {
    setSelectedSuggestion(0)
  }, [value])

  useInput((input, key) => {
    if (disabled) return
    if (isMouseSequence(input)) return
    if (showingSuggestions && key.upArrow) {
      setSelectedSuggestion(prev => (prev - 1 + suggestions.length) % suggestions.length)
      return
    }
    if (showingSuggestions && key.downArrow) {
      setSelectedSuggestion(prev => (prev + 1) % suggestions.length)
      return
    }
    if (showingSuggestions && (key.tab || input === '\t')) {
      acceptSuggestion(suggestions[Math.min(selectedSuggestion, suggestions.length - 1)])
      return
    }
    if (showingSuggestions && key.return && !isExactCommand(value, suggestions)) {
      acceptSuggestion(suggestions[Math.min(selectedSuggestion, suggestions.length - 1)])
      return
    }
    if (key.return) {
      onSubmit(value, mode)
      onChange('')
      onModeChange('prompt')
      return
    }
    if (key.backspace || key.delete) {
      onChange(value.slice(0, -1))
      return
    }
    if (key.escape) {
      onChange('')
      onModeChange('prompt')
      return
    }
    if (input && !key.ctrl && !key.meta) {
      onChange(value + input)
    }
  })

  function acceptSuggestion(command?: SlashCommand) {
    if (!command) return
    onChange(`/${command.name} `)
  }

  const prompt = mode === 'bash' ? '$' : '\u203a'
  const placeholder = mode === 'bash' ? 'shell command' : 'Ask general-agent'
  const displayValue = disabled ? 'processing...' : value || placeholder

  return (
    <Box flexDirection="column">
      {showingSuggestions ? (
        <Box flexDirection="column" paddingX={1} borderStyle="single" borderColor={theme.separator}>
          {suggestions.slice(0, 8).map((command, index) => {
            const selected = index === selectedSuggestion
            return (
              <Text key={command.name} color={selected ? theme.user : theme.muted}>
                {selected ? '\u203a' : ' '} {command.usage} <Text color={theme.muted}>{command.description}</Text>
              </Text>
            )
          })}
        </Box>
      ) : null}
      <Box paddingX={1} backgroundColor={theme.inputBackground}>
        <Text backgroundColor={theme.inputBackground} color={mode === 'bash' ? theme.bash : theme.user}>
          {prompt}
        </Text>
        <Text backgroundColor={theme.inputBackground} color={theme.inputText}>
          {' '}{displayValue}
        </Text>
      </Box>
    </Box>
  )
}

function getSlashSuggestions(value: string, commands: SlashCommand[]) {
  if (!value.startsWith('/')) return []
  if (/\s/.test(value)) return []
  const query = value.slice(1).toLowerCase()
  return commands.filter(command => command.name.startsWith(query))
}

function isExactCommand(value: string, commands: SlashCommand[]) {
  return commands.some(command => value === `/${command.name}`)
}

function isMouseSequence(input: string) {
  return input.includes('\x1b[<')
    || input.includes('\x1b[M')
    || input.includes('[<')
    || input.includes('[M')
    || /\[<[^;]{1,12};\d+;\d+[mM]/.test(input)
    || /\x1b\[M[\s\S]{3}/.test(input)
}
