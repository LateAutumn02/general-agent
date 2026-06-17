import { checkCommand, checkPathAccess, createDefaultSandboxPolicy } from './policy.js'

const policy = createDefaultSandboxPolicy(process.cwd())
if (checkPathAccess(policy, 'README.md').type !== 'allow') throw new Error('path allow failed')
if (checkCommand(policy, 'rm -rf /').type !== 'deny') throw new Error('command deny failed')

console.log('sandbox smoke ok')
