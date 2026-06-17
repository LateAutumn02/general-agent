import { loadMemory } from '../memory/store.js'
import { loadDefaultMcpConfigs } from '../mcp/config.js'
import { loadDefaultSkills } from '../skills/loader.js'

export async function buildRuntimeSystemAdditions(cwd: string) {
  const [memory, skills, mcpServers] = await Promise.all([
    loadMemory(cwd),
    loadDefaultSkills(cwd),
    loadDefaultMcpConfigs(cwd),
  ])
  const additions: string[] = []

  if (memory.promptText.trim()) {
    additions.push(`<memory>\n${memory.promptText.trim()}\n</memory>`)
  }

  if (skills.length > 0) {
    additions.push([
      '<skills>',
      ...skills.map(skill => `- ${skill.name}: ${skill.description} (${skill.path})`),
      'Users can explicitly invoke a skill with /skill-name.',
      '</skills>',
    ].join('\n'))
  }

  if (mcpServers.length > 0) {
    additions.push([
      '<mcp>',
      ...mcpServers.map(server => `- ${server.name}: ${server.command} ${server.args.join(' ')}`.trim()),
      'MCP transport is configured but tool registration is not active yet.',
      '</mcp>',
    ].join('\n'))
  }

  return additions
}
