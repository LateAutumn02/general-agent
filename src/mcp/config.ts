import { readFile } from 'node:fs/promises'

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
