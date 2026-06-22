// Headless swarm test — runs a real agent turn and logs everything

import { runAgentTurn } from '../agent/loop.js'
import type { AgentState } from '../agent/types.js'
import { createModelClient } from '../api/modelFactory.js'
import { loadRuntimeConfig } from '../config/runtimeConfig.js'
import { PermissionController } from '../permissions/controller.js'

const prompt = [
  '帮我组建一个团队研究 SAM3 微控制器。',
  '1. 先用 TeamCreate 创建团队 "sam3"',
  '2. 派 Agent(name="a", team_name="sam3") 搜索 SAM3 的技术规格',
  '3. 用 SendMessage(to="a", team="sam3") 把结果发给它自己确认',
].join('\n')

const config = loadRuntimeConfig([], process.cwd())
process.stderr.write(`Config: provider=${config.providerLabel} model=${config.model} apiKey=${config.apiKey ? 'yes' : 'NO'}\n`)

if (!config.apiKey) {
  process.stderr.write('FATAL: No API key — set DEEPSEEK_API_KEY in .env\n')
  process.exit(1)
}

const state: AgentState = {
  sessionId: crypto.randomUUID(),
  messages: [],
  turnCount: 0,
  cwd: process.cwd(),
  model: config.model,
}

const modelClient = createModelClient(config)
const permController = new PermissionController('bypassPermissions')

let toolCount = 0
let errorCount = 0

process.stderr.write(`\n=== Starting turn ===\n`)
process.stderr.write(`Prompt (${prompt.length} chars)\n`)

try {
  for await (const event of runAgentTurn({
    state,
    request: { id: crypto.randomUUID(), mode: 'prompt', text: prompt, createdAt: Date.now() },
    modelClient,
    permissionController: permController,
  })) {
    switch (event.type) {
      case 'model_request_started':
        process.stderr.write(`[step ${event.step}] Model request ${event.afterTool ? '(after tool)' : '(initial)'}\n`)
        break
      case 'assistant_delta':
        process.stdout.write(event.text)
        break
      case 'assistant_done':
        process.stderr.write(`\n[assistant done] ${event.text.length} chars\n`)
        break
      case 'tool_call_started':
        toolCount++
        process.stderr.write(`\n[tool #${toolCount}] ${event.call.name}\n`)
        break
      case 'tool_call_finished':
        const ok = event.result.ok ? 'OK' : 'FAIL'
        process.stderr.write(`[tool result] ${ok}: ${event.result.content.slice(0, 100).replace(/\n/g, ' ')}\n`)
        if (!event.result.ok) {
          errorCount++
          process.stderr.write(`[TOOL ERROR] ${event.result.error ?? 'unknown'}\n`)
        }
        break
      case 'permission_request':
        process.stderr.write(`[permission] ${event.request.toolName}\n`)
        break
      case 'error':
        errorCount++
        process.stderr.write(`[ERROR] ${event.error}\n`)
        break
    }
  }
} catch (err) {
  process.stderr.write(`\n[FATAL] ${err instanceof Error ? err.message : String(err)}\n`)
  process.exit(1)
}

process.stderr.write(`\n=== Turn complete: ${toolCount} tools, ${errorCount} errors, ${state.messages.length} messages ===\n`)
