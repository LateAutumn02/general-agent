# Swarm 协作数据结构

> 最后更新：2026-06-17

## SwarmPlan

```ts
type SwarmPlan = {
  id: string
  goal: string
  members: SwarmMember[]
  dependencies: SwarmDependency[]
  status: SwarmStatus
}
```

## SwarmMember

```ts
type SwarmMember = {
  id: string
  name: string
  profile: AgentProfile
  taskId?: string
  status: TaskStatus
}
```

## SwarmDependency

```ts
type SwarmDependency = {
  fromMemberId: string
  toMemberId: string
  reason: string
}
```

## SwarmStatus

```ts
type SwarmStatus = 'draft' | 'running' | 'blocked' | 'completed' | 'failed'
```

