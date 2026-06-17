import { readdir, readFile } from 'node:fs/promises'
import { join } from 'node:path'

export type SkillManifest = {
  name: string
  description: string
  path: string
}

export async function loadSkills(root: string): Promise<SkillManifest[]> {
  let entries: string[]
  try {
    entries = await readdir(root)
  } catch {
    return []
  }
  const skills: SkillManifest[] = []
  for (const entry of entries) {
    const path = join(root, entry, 'SKILL.md')
    try {
      const text = await readFile(path, 'utf8')
      skills.push({
        name: entry,
        description: firstDescription(text) ?? entry,
        path,
      })
    } catch {
      // Ignore malformed skill folders in the preview loader.
    }
  }
  return skills
}

function firstDescription(text: string) {
  return text.split(/\r?\n/).find(line => line.trim() && !line.startsWith('#'))?.trim()
}
