import React, { useMemo, useState } from 'react'
import { Box, Text, useApp } from 'ink'
import { Footer } from './components/Footer.js'
import { PromptInput } from './components/PromptInput.js'
import { Transcript } from './components/Transcript.js'
import { createInitialTranscript, nextAssistantReply } from './mockRuntime.js'
import type { PromptMode, TranscriptItem } from './types.js'

type AppProps = {
  args: string[]
  cwd: string
}

export function App({ args, cwd }: AppProps) {
  const { exit } = useApp()
  const [items, setItems] = useState<TranscriptItem[]>(() => createInitialTranscript())
  const [inputMode, setInputMode] = useState<PromptMode>('prompt')
  const model = useMemo(() => resolveModel(args), [args])

  function submit(text: string, mode: PromptMode) {
    const trimmed = text.trim()
    if (!trimmed) return

    if (trimmed === '/exit' || trimmed === '/quit') {
      exit()
      return
    }

    if (trimmed === '/help') {
      setItems(prev => [
        ...prev,
        { type: 'user', id: crypto.randomUUID(), text: trimmed },
        {
          type: 'assistant',
          id: crypto.randomUUID(),
          text: 'Available now: type normally, prefix with ! for bash mode, use /help, /exit, or /quit.',
        },
      ])
      return
    }

    const displayText = mode === 'bash' ? `!${trimmed}` : trimmed
    setItems(prev => [
      ...prev,
      { type: 'user', id: crypto.randomUUID(), text: displayText },
      nextAssistantReply(trimmed, mode),
    ])
  }

  return (
    <Box flexDirection="column" minHeight={18}>
      <Box paddingX={1} paddingY={1}>
        <Text color="cyan" bold>
          general-agent
        </Text>
        <Text color="gray">  TypeScript rewrite preview</Text>
      </Box>
      <Box flexDirection="column" flexGrow={1} paddingX={1}>
        <Transcript items={items} />
      </Box>
      <PromptInput mode={inputMode} onModeChange={setInputMode} onSubmit={submit} />
      <Footer cwd={cwd} model={model} mode={inputMode} />
    </Box>
  )
}

function resolveModel(args: string[]) {
  const modelIndex = args.findIndex(arg => arg === '--model')
  if (modelIndex >= 0 && args[modelIndex + 1]) {
    return args[modelIndex + 1]
  }
  return process.env.ANTHROPIC_MODEL ?? process.env.GENERAL_AGENT_MODEL ?? 'model-not-set'
}
