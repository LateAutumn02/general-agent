import { MockModelClient } from '../agent/mockModel.js'
import type { ModelClient } from '../agent/types.js'
import type { RuntimeConfig } from '../config/runtimeConfig.js'

export function createModelClient(config: RuntimeConfig): ModelClient {
  if (config.provider === 'mock') return new MockModelClient()
  return new AnthropicCompatibleModelClient(config)
}

class AnthropicCompatibleModelClient extends MockModelClient {
  constructor(private readonly config: RuntimeConfig) {
    super()
  }

  get endpoint() {
    return this.config.baseUrl ?? 'https://api.anthropic.com'
  }
}
