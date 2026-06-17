import { MockModelClient } from '../agent/mockModel.js'
import type { ModelClient } from '../agent/types.js'
import type { RuntimeConfig } from '../config/runtimeConfig.js'
import { OpenAICompatibleModelClient } from './openaiCompatibleClient.js'

export function createModelClient(config: RuntimeConfig): ModelClient {
  if (config.provider === 'mock') return new MockModelClient()
  if (!config.apiKey) throw new Error('Missing API key for model provider')
  return new OpenAICompatibleModelClient({
    apiKey: config.apiKey,
    baseUrl: config.baseUrl ?? 'https://api.deepseek.com',
    timeoutMs: config.timeoutMs,
  })
}
