# 启动初始化数据结构

> 最后更新：2026-06-17

## CliArgs

```ts
type CliArgs = {
  prompt?: string
  print: boolean
  resume?: string | true
  model?: string
  cwd: string
  permissionMode: PermissionMode
  allowedTools: string[]
  disallowedTools: string[]
  envFile?: string
}
```

## RuntimeConfig

```ts
type RuntimeConfig = {
  provider: ModelProvider
  model: string
  apiKey?: string
  baseUrl?: string
  timeoutMs: number
  cwd: string
  theme: ThemeConfig
  permissionMode: PermissionMode
}
```

## BootstrapResult

```ts
type BootstrapResult = {
  mode: RuntimeMode
  context: AppContext
  initialPrompt?: string
}
```

