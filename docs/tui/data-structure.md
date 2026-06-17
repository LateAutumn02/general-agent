# TUI 数据结构

> 最后更新：2026-06-17

## TuiState

```ts
type TuiState = {
  transcript: TranscriptItem[]
  streamingText: string
  input: PromptInputState
  footer: FooterState
  permission?: PermissionRequest
  taskBoard?: TaskBoardState
}
```

## PromptInputState

```ts
type PromptInputState = {
  value: string
  mode: 'prompt' | 'bash' | 'command' | 'file'
  cursorOffset: number
  placeholder: string
  historyIndex?: number
}
```

## TranscriptItem

```ts
type TranscriptItem =
  | { type: 'user'; text: string; messageId: string }
  | { type: 'assistant'; text: string; messageId: string }
  | { type: 'tool_summary'; callId: string; text: string; status: ToolStatus }
  | { type: 'error'; text: string }
  | { type: 'separator' }
```

## FooterState

```ts
type FooterState = {
  model: string
  cwd: string
  permissionMode: PermissionMode
  taskCounts: { awaiting: number; running: number; completed: number }
}
```

