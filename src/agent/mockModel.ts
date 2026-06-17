import type { ModelClient, ModelRequest, ModelStreamEvent } from './types.js'

export class MockModelClient implements ModelClient {
  async *stream(request: ModelRequest, _signal: AbortSignal): AsyncIterable<ModelStreamEvent> {
    const last = request.messages.at(-1)
    const text = last?.text ?? ''

    if (text.startsWith('!')) {
      yield {
        type: 'tool_use',
        call: {
          id: crypto.randomUUID(),
          name: 'Bash',
          input: { command: text.slice(1).trim() },
          status: 'pending',
          createdAt: Date.now(),
        },
      }
      yield { type: 'message_done' }
      return
    }

    const response = `I heard: ${text}`
    for (const chunk of chunkText(response)) {
      yield { type: 'text_delta', text: chunk }
      await Bun.sleep(5)
    }
    yield { type: 'message_done' }
  }
}

function chunkText(text: string) {
  const chunks: string[] = []
  for (let index = 0; index < text.length; index += 8) {
    chunks.push(text.slice(index, index + 8))
  }
  return chunks
}
