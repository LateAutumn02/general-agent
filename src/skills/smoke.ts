import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { loadSkills } from './loader.js'

const root = await mkdtemp(join(tmpdir(), 'general-agent-skills-'))
await mkdir(join(root, 'demo'))
await writeFile(join(root, 'demo', 'SKILL.md'), '# Demo\nA demo skill')
const skills = await loadSkills(root)
if (skills[0]?.name !== 'demo') throw new Error('skill load failed')
await rm(root, { recursive: true, force: true })

console.log('skills smoke ok')
