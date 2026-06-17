import { relative, resolve } from 'node:path'

export type SandboxPolicy = {
  cwd: string
  allowedDirs: string[]
  denyCommands: string[]
}

export type SandboxDecision =
  | { type: 'allow' }
  | { type: 'deny'; reason: string }

export function createDefaultSandboxPolicy(cwd: string): SandboxPolicy {
  return {
    cwd,
    allowedDirs: [cwd],
    denyCommands: [
      'rm -rf /',
      'rm -rf *',
      'format',
      'format.com',
      'del /f /s /q c:\\',
      'remove-item -recurse -force c:\\',
    ],
  }
}

export function checkPathAccess(policy: SandboxPolicy, path: string): SandboxDecision {
  const resolved = resolve(policy.cwd, path)
  const allowed = policy.allowedDirs.some(dir => isInsideOrEqual(resolve(dir), resolved))
  return allowed ? { type: 'allow' } : { type: 'deny', reason: `Path outside allowed dirs: ${path}` }
}

export function checkCommand(policy: SandboxPolicy, command: string): SandboxDecision {
  const normalized = command.trim().toLowerCase().replace(/\s+/g, ' ')
  const denied = policy.denyCommands.find(prefix => normalized.startsWith(prefix))
  return denied ? { type: 'deny', reason: `Command denied by sandbox: ${denied}` } : { type: 'allow' }
}

function isInsideOrEqual(parent: string, child: string) {
  const rel = relative(parent, child)
  return rel === '' || (!rel.startsWith('..') && !rel.includes(':'))
}
