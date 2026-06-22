// Team configuration: stored at .general-agent/teams/{team}/config.json

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

export type TeamMember = {
  agentId: string
  name: string
  agentType: string
  joinedAt: number
  cwd: string
}

export type TeamConfig = {
  name: string
  description?: string
  createdAt: number
  leadAgentId: string
  members: TeamMember[]
}

export function teamConfigPath(teamsDir: string, teamName: string): string {
  return join(teamsDir, teamName, 'config.json')
}

export async function readTeamConfig(teamsDir: string, teamName: string): Promise<TeamConfig | null> {
  try {
    const raw = await readFile(teamConfigPath(teamsDir, teamName), 'utf8')
    return JSON.parse(raw) as TeamConfig
  } catch {
    return null
  }
}

export async function writeTeamConfig(teamsDir: string, config: TeamConfig): Promise<void> {
  await mkdir(join(teamsDir, config.name), { recursive: true })
  await writeFile(teamConfigPath(teamsDir, config.name), JSON.stringify(config, null, 2), 'utf8')
}

export async function addTeamMember(
  teamsDir: string,
  teamName: string,
  member: TeamMember,
): Promise<void> {
  const config = await readTeamConfig(teamsDir, teamName)
  if (!config) throw new Error(`Team "${teamName}" not found`)
  if (config.members.some(m => m.name === member.name)) return // already in team
  config.members.push(member)
  await writeTeamConfig(teamsDir, config)
}
