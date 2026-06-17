# Skills 数据结构

> 最后更新：2026-06-17

## SkillManifest

```ts
type SkillManifest = {
  name: string
  description: string
  path: string
  trigger?: string[]
  allowedTools?: string[]
}
```

## SkillRuntime

```ts
type SkillRuntime = {
  manifest: SkillManifest
  prompt: string
  assets: string[]
}
```

## SkillRegistry

```ts
type SkillRegistry = {
  list(): SkillManifest[]
  get(name: string): SkillRuntime | undefined
  resolveCommand(command: string): SkillRuntime | undefined
}
```

