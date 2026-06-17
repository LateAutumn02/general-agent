import { mkdtemp, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { createDefaultToolRegistry } from './registry.js'
import { runTool } from './runTool.js'
import type { ToolContext } from './types.js'

const cwd = await mkdtemp(join(tmpdir(), 'general-agent-tools-'))
const registry = createDefaultToolRegistry()
const controller = new AbortController()
const events: string[] = []
const context: ToolContext = {
  cwd,
  signal: controller.signal,
  sessionId: 'smoke',
  emit(event) {
    events.push(event.type)
  },
}

const write = registry.get('Write')
const read = registry.get('Read')
const edit = registry.get('Edit')
const glob = registry.get('Glob')
const grep = registry.get('Grep')
const bash = registry.get('Bash')
const powerShell = registry.get('PowerShell')

if (!write || !read || !edit || !glob || !grep || !bash) {
  throw new Error('missing default tools')
}

await runTool(write, { path: 'note.txt', content: 'hello world\nsecond line' }, context)
await runTool(edit, { path: 'note.txt', oldText: 'world', newText: 'agent' }, context)
const readResult = await runTool(read, { path: 'note.txt' }, context)
const globResult = await runTool(glob, { pattern: '*.txt' }, context)
const grepResult = await runTool(grep, { pattern: 'agent' }, context)
const bashResult = await runTool(bash, { command: 'echo smoke && pwd' }, context)
const invalidResult = await runTool(read, { path: 42 }, context)
const powerShellResult = powerShell
  ? await runTool(powerShell, { command: 'Write-Output smoke' }, context)
  : undefined

if (!readResult.content.includes('hello agent')) throw new Error('read/edit failed')
if (!globResult.content.includes('note.txt')) throw new Error('glob failed')
if (!grepResult.content.includes('agent')) throw new Error('grep failed')
if (!bashResult.content.toLowerCase().includes('smoke')) throw new Error('bash failed')
if (powerShellResult && !powerShellResult.content.toLowerCase().includes('smoke')) throw new Error('powershell failed')
if (invalidResult.ok) throw new Error('invalid input should fail')
if (events.length < 12) throw new Error('runtime events missing')

await rm(cwd, { recursive: true, force: true })
console.log('tools smoke ok')
