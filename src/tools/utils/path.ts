import { resolve } from 'node:path'

export function resolveInCwd(cwd: string, path: string) {
  return resolve(cwd, path)
}

export function toDisplayPath(cwd: string, path: string) {
  return resolve(cwd, path).replace(resolve(cwd), '.')
}
