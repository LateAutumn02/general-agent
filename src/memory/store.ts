import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

export type MemoryState = {
  enabled: boolean
  files: { path: string; content: string }[]
  promptText: string
}

export async function loadMemory(cwd: string): Promise<MemoryState> {
  const paths = [
    join(process.env.USERPROFILE ?? process.env.HOME ?? cwd, '.general-agent', 'MEMORY.md'),
    join(cwd, 'MEMORY.md'),
    join(cwd, '.general-agent', 'MEMORY.md'),
  ]
  const files: MemoryState['files'] = []
  for (const path of paths) {
    try {
      const content = await readFile(path, 'utf8')
      files.push({ path, content })
    } catch {
      // Missing memory files are normal.
    }
  }
  return {
    enabled: true,
    files,
    promptText: files.map(file => `# ${file.path}\n${file.content}`).join('\n\n'),
  }
}
