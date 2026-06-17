import type { ChatMessage } from '../session/types.js'
import type { ModelClient, ModelRequest, ModelStreamEvent } from '../agent/types.js'
import type { ToolDefinition } from '../tools/types.js'

export type OpenAICompatibleClientOptions = {
  apiKey: string
  baseUrl: string
}

type ChatCompletionChunk = {
  choices?: Array<{
    delta?: {
      content?: string
      tool_calls?: Array<{
        index: number
        id?: string
        function?: {
          name?: string
          arguments?: string
        }
      }>
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
    const pendingToolCalls = new Map<number, PendingToolCall>()
    const response = await fetch(`${trimTrailingSlash(this.options.baseUrl)}/chat/completions`, {
      method: 'POST',
      signal,
      headers: {
        Authorization: `Bearer ${this.options.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: request.model,
        messages: toOpenAIMessages(request.messages, request.cwd, request.systemAdditions ?? []),
        tools: request.tools?.map(toOpenAITool),
        tool_choice: request.tools?.length ? 'auto' : undefined,
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
          const delta = event.choices?.[0]?.delta
          const content = delta?.content
          if (content) yield { type: 'text_delta', text: content }
          for (const toolCall of delta?.tool_calls ?? []) {
            const pending = pendingToolCalls.get(toolCall.index) ?? {
              id: toolCall.id ?? crypto.randomUUID(),
              name: '',
              argumentsText: '',
            }
            pending.id = toolCall.id ?? pending.id
            pending.name += toolCall.function?.name ?? ''
            pending.argumentsText += toolCall.function?.arguments ?? ''
            pendingToolCalls.set(toolCall.index, pending)
          }
        }
      }
    } finally {
      reader.releaseLock()
    }

    for (const pending of pendingToolCalls.values()) {
      if (!pending.name) continue
      yield {
        type: 'tool_use',
        call: {
          id: pending.id,
          name: pending.name,
          input: parseToolArguments(pending.argumentsText),
          status: 'pending',
          createdAt: Date.now(),
        },
      }
    }
    yield { type: 'message_done' }
  }
}

type PendingToolCall = {
  id: string
  name: string
  argumentsText: string
}

function toOpenAIMessages(messages: ChatMessage[], cwd: string, systemAdditions: string[]) {
  return [
    {
      role: 'system',
      content: [
        'You are general-agent, a concise coding assistant running in a terminal UI.',
        `Current working directory: ${cwd}`,
        'You may use tools when needed. Prefer read-only tools before making changes.',
        'When you say you will inspect, read, search, edit, or run something, call the matching tool in that same turn.',
        'Do not announce a numbered tool plan and then stop after only prose; either call the tool or provide the final answer.',
        'For shell commands, explain why the command is needed; the terminal UI will ask the user for permission.',
        ...systemAdditions,
      ].join('\n'),
    },
    ...messages.map(message => ({
      role: normalizeRole(message.role),
      content: message.role === 'tool' ? `Tool result:\n${message.text}` : message.text,
    })),
  ]
}

function toOpenAITool(tool: ToolDefinition) {
  return {
    type: 'function',
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.inputSchema,
    },
  }
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

function parseToolArguments(value: string) {
  if (!value.trim()) return {}
  try {
    return JSON.parse(value) as unknown
  } catch {
    return { raw: value }
  }
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '')
}
