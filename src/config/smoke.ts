import { loadRuntimeConfig } from './runtimeConfig.js'

const config = loadRuntimeConfig(['--model', 'test-model'], process.cwd())
if (config.model !== 'test-model') throw new Error('model arg failed')
if (!config.cwd) throw new Error('cwd missing')

console.log('config smoke ok')
