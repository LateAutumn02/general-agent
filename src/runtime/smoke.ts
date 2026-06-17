import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { buildRuntimeSystemAdditions } from './context.js'

const root = await mkdtemp(join(tmpdir(), 'general-agent-runtime-'))
await writeFile(join(root, 'MEMORY.md'), 'Project prefers concise answers.')
await mkdir(join(root, 'skills', 'demo'), { recursive: true })
await writeFile(join(root, 'skills', 'demo', 'SKILL.md'), '# Demo\nUse demo behavior.')
await writeFile(join(root, '.mcp.json'), JSON.stringify({
  mcpServers: { demo: { command: 'node', args: ['server.js'] } },
}))

const additions = await buildRuntimeSystemAdditions(root)
const joined = additions.join('\n')
if (!joined.includes('<memory>')) throw new Error('memory context missing')
if (!joined.includes('<skills>')) throw new Error('skills context missing')
if (!joined.includes('<mcp>')) throw new Error('mcp context missing')

await rm(root, { recursive: true, force: true })
console.log('runtime smoke ok')
