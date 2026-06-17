import { loadRuntimeConfig } from './runtimeConfig.js'

const config = loadRuntimeConfig(['--model', 'test-model'], process.cwd())
if (config.model !== 'test-model') throw new Error('model arg failed')
if (!config.cwd) throw new Error('cwd missing')

const previousKey = process.env.DEEPSEEK_API_KEY
process.env.DEEPSEEK_API_KEY = 'test-key'
const deepseekConfig = loadRuntimeConfig([], process.cwd())
if (deepseekConfig.provider !== 'openai-compatible') throw new Error('deepseek provider failed')
if (deepseekConfig.model !== 'deepseek-v4-flash') throw new Error('deepseek model default failed')
if (previousKey === undefined) {
  delete process.env.DEEPSEEK_API_KEY
} else {
  process.env.DEEPSEEK_API_KEY = previousKey
}

console.log('config smoke ok')
