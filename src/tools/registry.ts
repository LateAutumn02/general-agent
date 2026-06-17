import { bashTool } from './tools/bash.js'
import { editTool } from './tools/edit.js'
import { globTool } from './tools/glob.js'
import { grepTool } from './tools/grep.js'
import { readTool } from './tools/read.js'
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
  for (const tool of [bashTool, readTool, writeTool, editTool, globTool, grepTool]) {
    registry.register(tool)
  }
  return registry
}
