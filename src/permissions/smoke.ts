import { PermissionController } from './controller.js'
import { bashTool } from '../tools/tools/bash.js'
import { readTool } from '../tools/tools/read.js'
import type { ToolContext } from '../tools/types.js'

const context: ToolContext = {
  cwd: process.cwd(),
  signal: new AbortController().signal,
  sessionId: 'permission-smoke',
  emit() {},
}

const controller = new PermissionController()
const read = await controller.evaluate(readTool, { path: 'README.md' }, context)
if (read.type !== 'allow') throw new Error('read should be allowed')

const bash = await controller.evaluate(bashTool, { command: 'git status' }, context)
if (bash.type !== 'ask') throw new Error('bash should ask')

const rule = bash.request.suggestions[0]
if (!rule) throw new Error('missing suggestion')
controller.applyDecision(bash.request, { type: 'allow', remember: true, rule })

const remembered = await controller.evaluate(bashTool, { command: 'git status --short' }, context)
if (remembered.type !== 'allow') throw new Error('remembered bash should be allowed')

const outsideRead = await controller.evaluate(readTool, { path: '../outside.txt' }, context)
if (outsideRead.type !== 'deny') throw new Error('sandbox should deny outside path')

const dangerousCommand = await controller.evaluate(bashTool, { command: 'rm -rf /' }, context)
if (dangerousCommand.type !== 'deny') throw new Error('sandbox should deny dangerous command')

controller.setMode('plan')
const denied = await controller.evaluate(bashTool, { command: 'echo nope' }, context)
if (denied.type !== 'deny') throw new Error('plan mode should deny writes')

console.log('permissions smoke ok')
