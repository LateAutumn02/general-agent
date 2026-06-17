import type { ChatMessage } from '../session/types.js'
import type { ModelClient, ModelRequest, ModelStreamEvent } from '../agent/types.js'

export type OpenAICompatibleClientOptions = {
  apiKey: string
  baseUrl: string
}

type ChatCompletionChunk = {
  choices?: Array<{
    delta?: {
      content?: string
    }
    finish_reason?: string
  }>
  error?: {
    message?: string
  }
}

export class OpenAICompatibleModelClient implements ModelClient {
  constructor(private readonly options: OpenAICompatibleClientOptions) {}

  async *stream(request: ModelRequest, signal: AbortSignal): AsyncIterable<ModelStreamEvent> {
    const response = await fetch(`${trimTrailingSlash(this.options.baseUrl)}/chat/completions`, {
      method: 'POST',
      signal,
      headers: {
        Authorization: `Bearer ${this.options.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: request.model,
        messages: toOpenAIMessages(request.messages, request.cwd),
        stream: true,
      }),
    })

    if (!response.ok) {
      const detail = await response.text()
      throw new Error(`Model request failed (${response.status}): ${detail.slice(0, 500)}`)
    }
    if (!response.body) throw new Error('Model response did not include a stream body')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split(/\r?\n/)
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          const event = parseSseLine(line)
          if (!event) continue
          if (event.error?.message) throw new Error(event.error.message)
          const content = event.choices?.[0]?.delta?.content
          if (content) yield { type: 'text_delta', text: content }
        }
      }
    } finally {
      reader.releaseLock()
    }

    yield { type: 'message_done' }
  }
}

function toOpenAIMessages(messages: ChatMessage[], cwd: string) {
  return [
    {
      role: 'system',
      content: [
        'You are general-agent, a concise coding assistant running in a terminal UI.',
        `Current working directory: ${cwd}`,
        'When you need shell or file access, ask the user to use bash mode for now.',
      ].join('\n'),
    },
    ...messages.map(message => ({
      role: normalizeRole(message.role),
      content: message.role === 'tool' ? `Tool result:\n${message.text}` : message.text,
    })),
  ]
}

function normalizeRole(role: ChatMessage['role']) {
  if (role === 'assistant' || role === 'system') return role
  return 'user'
}

function parseSseLine(line: string): ChatCompletionChunk | undefined {
  const trimmed = line.trim()
  if (!trimmed.startsWith('data:')) return undefined
  const data = trimmed.slice('data:'.length).trim()
  if (!data || data === '[DONE]') return undefined
  return JSON.parse(data) as ChatCompletionChunk
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '')
}
