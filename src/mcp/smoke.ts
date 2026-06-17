import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { loadMcpConfig } from './config.js'

const root = await mkdtemp(join(tmpdir(), 'general-agent-mcp-'))
const path = join(root, 'mcp.json')
await writeFile(path, JSON.stringify({ mcpServers: { demo: { command: 'node', args: ['server.js'] } } }))
const servers = await loadMcpConfig(path)
if (servers[0]?.name !== 'demo') throw new Error('mcp config failed')
await rm(root, { recursive: true, force: true })

console.log('mcp smoke ok')
