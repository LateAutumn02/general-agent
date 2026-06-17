import type { ToolDefinition } from '../tools/types.js'
import { checkCommand, checkPathAccess, createDefaultSandboxPolicy } from '../sandbox/policy.js'
import type {
  PermissionDecision,
  PermissionMode,
  PermissionOutcome,
  PermissionRequest,
  PermissionRule,
} from './types.js'

export class PermissionController {
  private readonly rules: PermissionRule[] = []

  constructor(private mode: PermissionMode = 'default') {}

  setMode(mode: PermissionMode) {
    this.mode = mode
  }

  getMode() {
    return this.mode
  }

  listRules() {
    return [...this.rules]
  }

  async evaluate<TInput>(
    tool: ToolDefinition<TInput>,
    input: TInput,
    context: Parameters<ToolDefinition<TInput>['checkPermission']>[1],
  ): Promise<PermissionOutcome> {
    const sandboxDecision = checkInputSandbox(context.cwd, input)
    if (sandboxDecision.type === 'deny') return sandboxDecision

    if (this.mode === 'bypassPermissions') return { type: 'allow' }
    if (this.mode === 'plan' && !tool.readOnly) {
      return { type: 'deny', reason: `${tool.name} is disabled in plan mode` }
    }
    if (this.mode === 'acceptEdits' && ['Edit', 'Write'].includes(tool.name)) {
      return { type: 'allow' }
    }

    const check = await tool.checkPermission(input, context)
    if (check.type === 'allow') return { type: 'allow' }
    if (check.type === 'deny') return { type: 'deny', reason: check.reason }

    const rule = this.matchRule(tool.name, input)
    if (rule?.behavior === 'allow') return { type: 'allow' }
    if (rule?.behavior === 'deny') return { type: 'deny', reason: `Denied by ${rule.scope} rule` }

    return {
      type: 'ask',
      request: {
        id: crypto.randomUUID(),
        toolName: tool.name,
        check,
        preview: check.preview,
        suggestions: [createSuggestion(tool.name, input)],
        createdAt: Date.now(),
      },
    }
  }

  applyDecision(request: PermissionRequest, decision: PermissionDecision) {
    if (decision.type === 'allow' && decision.remember) {
      this.rules.push(decision.rule)
    }
    if (decision.type === 'deny' && decision.reason) {
      return decision.reason
    }
    return undefined
  }

  private matchRule(toolName: string, input: unknown) {
    const text = inputToRuleText(input)
    return this.rules.find(rule =>
      rule.toolName === toolName &&
      (text === rule.pattern || text.startsWith(`${rule.pattern} `) || rule.pattern === '*'),
    )
  }
}

function checkInputSandbox(cwd: string, input: unknown) {
  const policy = createDefaultSandboxPolicy(cwd)
  if (typeof input === 'object' && input !== null && 'command' in input) {
    return checkCommand(policy, String((input as { command: unknown }).command))
  }
  if (typeof input === 'object' && input !== null && 'path' in input) {
    return checkPathAccess(policy, String((input as { path: unknown }).path))
  }
  return { type: 'allow' as const }
}

export function createSuggestion(toolName: string, input: unknown): PermissionRule {
  return {
    id: crypto.randomUUID(),
    scope: 'session',
    toolName,
    pattern: inputToRuleText(input),
    behavior: 'allow',
  }
}

function inputToRuleText(input: unknown) {
  if (typeof input === 'object' && input !== null && 'command' in input) {
    const command = String((input as { command: unknown }).command)
    return command.split(/\s+/).slice(0, 2).join(' ')
  }
  if (typeof input === 'object' && input !== null && 'path' in input) {
    return String((input as { path: unknown }).path)
  }
  return '*'
}
