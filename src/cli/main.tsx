import React from 'react'
import { render } from 'ink'
import { runAgentTurn } from '../agent/loop.js'
import type { AgentState } from '../agent/types.js'
import { createModelClient } from '../api/modelFactory.js'
import { loadRuntimeConfig } from '../config/runtimeConfig.js'
import { PermissionController } from '../permissions/controller.js'
import { App } from '../tui/App.js'
import { helpText, parseCliArgs } from './args.js'

const args = process.argv.slice(2)
const defaultCwd = process.env.GENERAL_AGENT_CALLER_DIR ?? process.cwd()
const cliArgs = parseCliArgs(args, defaultCwd)

if (cliArgs.help) {
  console.log(helpText())
  process.exit(0)
}

if (cliArgs.print) {
  await runPrintMode(cliArgs)
  process.exit(0)
}

let restoreTerminal: (() => void) | undefined
if (process.stdout.isTTY && process.env.GENERAL_AGENT_NO_ALT_SCREEN !== '1') {
  process.stdout.write('\x1b[?1049h\x1b[?1007h\x1b[2J\x1b[H')
  restoreTerminal = () => {
    process.stdout.write('\x1b[?1007l\x1b[?1006l\x1b[?1002l\x1b[?1000l\x1b[?1049l')
  }
  process.on('exit', restoreTerminal)
  process.on('SIGINT', () => {
    restoreTerminal?.()
    process.exit(130)
  })
}

const app = render(<App args={args} cwd={cliArgs.cwd} />)
void app.waitUntilExit().finally(() => {
  restoreTerminal?.()
})

async function runPrintMode(cliArgs: ReturnType<typeof parseCliArgs>) {
  const prompt = cliArgs.prompt
  if (!prompt) throw new Error('--print requires a prompt')
  const config = loadRuntimeConfig(args, cliArgs.cwd)
  const state: AgentState = {
    sessionId: crypto.randomUUID(),
    messages: [],
    turnCount: 0,
    cwd: cliArgs.cwd,
    model: cliArgs.model ?? config.model,
  }
  const permissionController = new PermissionController(cliArgs.permissionMode ?? config.permissionMode)
  for await (const event of runAgentTurn({
    state,
    request: {
      id: crypto.randomUUID(),
      mode: 'prompt',
      text: prompt,
      createdAt: Date.now(),
    },
    modelClient: createModelClient(config),
    permissionController,
    async decidePermission(permissionEvent) {
      return {
        type: 'deny',
        reason: `Print mode cannot approve ${permissionEvent.request.toolName}; rerun in the TUI to review it.`,
      }
    },
  })) {
    if (event.type === 'assistant_delta') process.stdout.write(event.text)
    if (event.type === 'error') process.stderr.write(`\n${event.error}\n`)
  }
  process.stdout.write('\n')
}
