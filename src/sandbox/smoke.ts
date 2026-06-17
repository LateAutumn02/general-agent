import { checkCommand, checkPathAccess, createDefaultSandboxPolicy } from './policy.js'

const policy = createDefaultSandboxPolicy(process.cwd())
if (checkPathAccess(policy, 'README.md').type !== 'allow') throw new Error('path allow failed')
if (checkPathAccess(policy, '..').type !== 'deny') throw new Error('path deny failed')
if (checkCommand(policy, 'rm -rf /').type !== 'deny') throw new Error('command deny failed')
if (checkCommand(policy, 'echo ok').type !== 'allow') throw new Error('command allow failed')

console.log('sandbox smoke ok')
