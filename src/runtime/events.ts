import type { ToolCall, ToolResult } from '../tools/types.js'
import type { PermissionDecision, PermissionRequest } from '../permissions/types.js'
import type { MailboxMessage } from '../swarm/mailbox.js'

export type SwarmAgentStatus = 'starting' | 'running' | 'idle' | 'completed' | 'failed'

export type RuntimeEvent =
  | { type: 'model_request_started'; step: number; afterTool: boolean }
  | { type: 'assistant_delta'; text: string; messageId: string }
  | { type: 'assistant_done'; text: string; messageId: string }
  | { type: 'tool_call_started'; call: ToolCall }
  | { type: 'tool_call_finished'; callId: string; result: ToolResult }
  | { type: 'permission_request'; request: PermissionRequest }
  | { type: 'permission_resolved'; requestId: string; decision: PermissionDecision }
  | {
    type: 'swarm_agent_status'
    teamName: string
    agentName: string
    agentType: string
    status: SwarmAgentStatus
    activity: string
    description?: string
    prompt?: string
    output?: string
    error?: string
    toolUseCount: number
    createdAt: number
    updatedAt: number
    completedAt?: number
  }
  | {
    type: 'swarm_message_sent'
    teamName: string
    from: string
    to: string
    summary?: string
    text: string
    broadcast: boolean
    createdAt: number
  }
  | {
    type: 'swarm_inbox_read'
    teamName: string
    agentName: string
    messages: MailboxMessage[]
    createdAt: number
  }
  | { type: 'error'; error: string }

export type RuntimeEventSink = (event: RuntimeEvent) => void
