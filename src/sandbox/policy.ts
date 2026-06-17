import { resolve } from 'node:path'

export type SandboxPolicy = {
  cwd: string
  allowedDirs: string[]
  denyCommands: string[]
}

export type SandboxDecision =
  | { type: 'allow' }
  | { type: 'deny'; reason: string }

export function createDefaultSandboxPolicy(cwd: string): SandboxPolicy {
  return { cwd, allowedDirs: [cwd], denyCommands: ['rm -rf /', 'format'] }
}

export function checkPathAccess(policy: SandboxPolicy, path: string): SandboxDecision {
  const resolved = resolve(policy.cwd, path)
  const allowed = policy.allowedDirs.some(dir => resolved.startsWith(resolve(dir)))
  return allowed ? { type: 'allow' } : { type: 'deny', reason: `Path outside allowed dirs: ${path}` }
}

export function checkCommand(policy: SandboxPolicy, command: string): SandboxDecision {
  const normalized = command.trim().toLowerCase()
  const denied = policy.denyCommands.find(prefix => normalized.startsWith(prefix))
  return denied ? { type: 'deny', reason: `Command denied by sandbox: ${denied}` } : { type: 'allow' }
}
