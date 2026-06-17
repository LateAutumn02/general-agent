import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

export type McpServerConfig = {
  name: string
  command: string
  args: string[]
  env?: Record<string, string>
}

export async function loadMcpConfig(path: string): Promise<McpServerConfig[]> {
  const text = await readFile(path, 'utf8')
  const parsed = JSON.parse(text) as { servers?: McpServerConfig[]; mcpServers?: Record<string, Omit<McpServerConfig, 'name'>> }
  if (parsed.servers) return parsed.servers
  return Object.entries(parsed.mcpServers ?? {}).map(([name, config]) => ({ name, ...config }))
}

export async function loadDefaultMcpConfigs(cwd: string): Promise<McpServerConfig[]> {
  const paths = [
    process.env.GENERAL_AGENT_MCP_CONFIG,
    join(cwd, 'mcp.json'),
    join(cwd, '.mcp.json'),
    join(cwd, '.general-agent', 'mcp.json'),
  ].filter((path): path is string => Boolean(path))
  const loaded = await Promise.all(paths.map(async path => {
    try {
      return await loadMcpConfig(path)
    } catch {
      return []
    }
  }))
  return loaded.flat()
}
