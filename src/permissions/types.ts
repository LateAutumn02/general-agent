import type { PermissionCheck, ToolPreview } from '../tools/types.js'

export type PermissionMode = 'default' | 'acceptEdits' | 'plan' | 'bypassPermissions'

export type PermissionRule = {
  id: string
  scope: 'session' | 'project' | 'user'
  toolName: string
  pattern: string
  behavior: 'allow' | 'deny'
}

export type PermissionRequest = {
  id: string
  toolName: string
  check: PermissionCheck
  preview: ToolPreview
  suggestions: PermissionRule[]
  createdAt: number
}

export type PermissionDecision =
  | { type: 'allow'; remember: false }
  | { type: 'allow'; remember: true; rule: PermissionRule }
  | { type: 'deny'; reason?: string }

export type PermissionOutcome =
  | { type: 'allow' }
  | { type: 'deny'; reason: string }
  | { type: 'ask'; request: PermissionRequest }
