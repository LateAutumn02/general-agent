export type SlashCommand = {
  name: string
  usage: string
  description: string
}

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    name: 'model',
    usage: '/model <model-name>',
    description: 'Switch the model for this session.',
  },
  {
    name: 'memory',
    usage: '/memory',
    description: 'Show loaded project memory files.',
  },
  {
    name: 'skills',
    usage: '/skills',
    description: 'List local skills.',
  },
  {
    name: 'resume',
    usage: '/resume [session-id]',
    description: 'List or restore saved sessions.',
  },
  {
    name: 'continue',
    usage: '/continue',
    description: 'Resume the most recent session.',
  },
  {
    name: 'compact',
    usage: '/compact',
    description: 'Compact old conversation history.',
  },
  {
    name: 'swarm',
    usage: '/swarm <goal>',
    description: 'Create background agent tasks.',
  },
  {
    name: 'help',
    usage: '/help',
    description: 'Show available slash commands.',
  },
  {
    name: 'exit',
    usage: '/exit',
    description: 'Exit the app.',
  },
  {
    name: 'quit',
    usage: '/quit',
    description: 'Exit the app.',
  },
]

export function formatSlashCommandHelp(commands = SLASH_COMMANDS) {
  return commands.map(command => `${command.usage} - ${command.description}`).join('\n')
}
