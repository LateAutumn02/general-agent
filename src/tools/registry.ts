import { agentTool } from './tools/agent.js'
import { bashTool } from './tools/bash.js'
import { editTool } from './tools/edit.js'
import { globTool } from './tools/glob.js'
import { grepTool } from './tools/grep.js'
import { powerShellTool } from './tools/powershell.js'
import { readTool } from './tools/read.js'
import { sendMessageTool } from './tools/sendMessage.js'
import { teamCreateTool } from './tools/teamCreate.js'
import { writeTool } from './tools/write.js'
import type { ToolDefinition } from './types.js'

export class ToolRegistry {
  private readonly tools = new Map<string, ToolDefinition>()

  register(tool: ToolDefinition) {
    this.tools.set(tool.name, tool)
  }

  get(name: string) {
    return this.tools.get(name)
  }

  list() {
    return [...this.tools.values()]
  }
}

export function createDefaultToolRegistry() {
  const registry = new ToolRegistry()
  const tools = [bashTool, readTool, writeTool, editTool, globTool, grepTool, agentTool, sendMessageTool, teamCreateTool]
  if (process.platform === 'win32') tools.push(powerShellTool)
  for (const tool of tools) {
    registry.register(tool)
  }
  return registry
}

export function createSubAgentToolRegistry(agentType = 'general-purpose') {
  const registry = new ToolRegistry()
  const tools = agentType === 'Explore'
    ? [readTool, globTool, grepTool, sendMessageTool]
    : [bashTool, readTool, writeTool, editTool, globTool, grepTool, sendMessageTool]
  if (process.platform === 'win32' && agentType !== 'Explore') tools.push(powerShellTool)
  for (const tool of tools) {
    registry.register(tool)
  }
  return registry
}
