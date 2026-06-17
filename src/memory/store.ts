import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

export type MemoryState = {
  enabled: boolean
  files: { path: string; content: string }[]
  promptText: string
}

export async function loadMemory(cwd: string): Promise<MemoryState> {
  const path = join(cwd, 'MEMORY.md')
  try {
    const content = await readFile(path, 'utf8')
    return { enabled: true, files: [{ path, content }], promptText: content }
  } catch {
    return { enabled: true, files: [], promptText: '' }
  }
}
