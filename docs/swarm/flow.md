# Swarm 协作流程

> 最后更新：2026-06-22
> 代码依据：`src/tools/tools/teamCreate.ts`、`src/tools/tools/agent.ts`、`src/tools/tools/sendMessage.ts`、`src/swarm/*`、`src/agent/loop.ts`、`src/tui/App.tsx`

## 当前定位

Swarm 现在不是独立命令系统，也不是后台进程池。它的主入口是模型主动调用工具：

1. `TeamCreate` 创建团队文件。
2. `Agent` 启动一个命名子 agent。
3. `SendMessage` 把消息写入其他 agent 的信箱。
4. 下一次同名 `Agent` 被启动时，会读取未读信箱消息，并注入到它的 prompt。

当前实现更接近“主 agent 通过工具调度 in-process 子 agent，并用文件信箱续接上下文”。后续规划中的后台 teammate、coordinator、任务队列、权限委托、tmux/iTerm 分屏等能力还没有完全实现。

## 已实现流程

### 1. 建队：TeamCreate

模型在判断需要多 agent 协作时调用：

```ts
TeamCreate({
  team_name: "swarm-test-1",
  description: "Verify inter-agent messaging"
})
```

执行结果：

- 创建 `.general-agent/teams/{team}/config.json`
- 初始成员只有 `main`
- `leadAgentId` 为 `lead@{team}`
- 后续命名 `Agent` 会注册到该团队

当前不会创建共享任务列表，也不会创建独立队友进程。

### 2. 派发：Agent

模型调用：

```ts
Agent({
  name: "agent-a",
  team_name: "swarm-test-1",
  description: "choose word",
  prompt: "Choose a word and send it to agent-b.",
  subagent_type: "general-purpose"
})
```

执行逻辑：

1. `team_name` 省略时默认为 `default`。
2. 如果传入 `name`，会尝试把成员写入 `.general-agent/teams/{team}/config.json`。
3. 如果存在 `.general-agent/teams/{team}/inboxes/{name}.json`，读取未读消息。
4. 未读消息会被标记为已读，并以以下格式追加到子 agent prompt：

```xml
<inbox>
[@main] message text
[@agent-b] message text
</inbox>
```

5. 当前 CLI/TUI 下通过 `context.runSubAgent` 同步运行子 agent。
6. 子 agent 的返回会作为 `Agent` 工具结果回到主 agent 上下文。

注意：当前 `Agent` 工具调用不是后台常驻任务。它跑完一轮就结束；下次需要继续处理时，要再次调用同名 `Agent`，由信箱补上下文。

### 3. 子 agent 执行

子 agent 复用主循环 `runAgentTurn`，但使用专门的工具注册表：

| agent 类型 | 可用工具 |
| --- | --- |
| `Explore` | `Read`、`Glob`、`Grep`、`SendMessage` |
| `general-purpose` / 默认 | `Bash`、`Read`、`Write`、`Edit`、`Glob`、`Grep`、`SendMessage`，Windows 下还有 `PowerShell` |

子 agent 明确不能使用：

- `Agent`
- `TeamCreate`

这样可以避免子 agent 递归创建更多 agent。

当前子 agent 权限模式为 `bypassPermissions`，也就是说子 agent 工具调用不会再弹主 UI 审批。这是为了先保证蜂群链路能跑通；更细粒度的权限委托还没有实现。

### 4. 通信：SendMessage + Mailbox

子 agent 或主 agent 调用：

```ts
SendMessage({
  to: "agent-b",
  team_name: "swarm-test-1",
  summary: "word chosen",
  message: "bridge"
})
```

执行逻辑：

- `team_name` 省略时优先使用当前 agent 上下文里的 `teamName`，再退回 `default`。
- `from` 优先使用当前 agent 名称，没有则为 `main`。
- 普通消息写入 `.general-agent/teams/{team}/inboxes/{to}.json`。
- `to: "*"` 会读取团队成员列表，并广播给除自己以外的成员。

信箱消息不是实时推送。接收方要等下一次同名 `Agent` 启动时才会读取。

### 5. 主循环工具协议

当前 OpenAI-compatible 工具协议已按标准流程处理：

1. assistant message 里保留 `tool_calls`
2. 工具执行结果作为 `role: "tool"` 消息回传
3. 模型收到工具结果后继续下一轮生成

这点对 DeepSeek / OpenAI-compatible 模型很关键，否则模型容易在一次工具调用后停止继续调用后续工具。

### 6. TUI 展示

TUI 左侧 tasks 页面目前会捕获顶层 `Agent` 工具调用：

- `tool_call_started` 时创建一个 `agent` task
- task 标题为 `{name}@{team}` 或 description
- 初始消息记录为该 Agent prompt
- `tool_call_finished` 时追加 Agent 返回结果
- 完成后写入 `completedAt`，所以计时器不再继续增长
- messages 数量来自 task 内保存的 prompt/result 消息

当前展示是“顶层 Agent 工具调用的状态”，不是完整子 agent 运行面板。

## 典型链路

让三个 agent 验证消息链路：

```text
用户：创建 swarm-test-1，启动 agent-a、agent-b、agent-c。
agent-a 发送单词 bridge 给 agent-b。
agent-b 收到后反转为 egdirb，再发给 agent-c。
agent-c 收到后广播最终结果。
```

预期工具链路：

```text
TeamCreate(swarm-test-1)
Agent(agent-a@swarm-test-1)
  SendMessage(to=agent-b, message=bridge)
Agent(agent-b@swarm-test-1)
  读取 inbox: bridge
  SendMessage(to=agent-c, message=egdirb)
Agent(agent-c@swarm-test-1)
  读取 inbox: egdirb
  SendMessage(to=*, message=final result)
```

## 当前测试覆盖

| 文件 | 覆盖内容 |
| --- | --- |
| `src/swarm/swarm-smoke.ts` | mailbox、TeamCreate、SendMessage、Agent 工具注册 |
| `src/swarm/e2e-smoke.ts` | 建队、注册成员、写信箱、同名 Agent 读取未读消息 |
| `src/swarm/subagent-tools-smoke.ts` | 子 agent 工具集包含 SendMessage，且不包含 Agent |
| `src/api/smoke.ts` | OpenAI-compatible tool call / tool result 协议 |

## 未完成部分

这些能力在后续规划里存在，或在当前文档/讨论中提过，但本项目当前代码还没完整实现：

| 能力 | 当前状态 |
| --- | --- |
| 后台常驻 teammate | 未实现。当前 `Agent` 是同步 in-process 单轮执行 |
| 子 agent 独立 session / resume | 未实现。子 agent 没有独立可恢复 transcript |
| 子 agent 实时工具进度 | 部分实现。TUI 只展示顶层 Agent 开始/结束，不展示子 agent 内部 Read/Bash/SendMessage 流程 |
| 并行执行多个 Agent | 未实现。主循环按工具调用顺序执行 |
| TeamDelete / shutdown 协议 | 未实现 |
| TaskCreate / TaskUpdate / 共享任务队列 | 未实现 |
| TaskStop | 未实现 |
| coordinator mode | 未实现 |
| tmux / iTerm / remote backend | 未实现 |
| 权限委托给主 agent 审批 | 未实现。当前子 agent 是 `bypassPermissions` |
| 结构化消息协议 | 未实现。当前 `message` 是字符串 |
| UDS / bridge 跨进程通信 | 未实现 |
| WebSearch / WebFetch / TodoWrite / Skill 工具 | 未接入当前工具注册表 |

## 当前设计边界

现阶段 swarm 的可靠边界是：

- 适合让主 agent 临时派发几个子 agent 做搜索、读写、验证、消息传递。
- 适合验证 agent 间通过文件信箱传话。
- 不适合依赖后台持续运行、实时协同编辑、复杂任务队列、长期团队状态恢复。

后续如果要继续完善 swarm 体验，需要优先补：

1. 子 agent 独立 session 存储和恢复。
2. TaskBoard 读取子 agent 内部 runtime events。
3. 后台 agent 生命周期管理。
4. 权限请求从子 agent 桥接到主 UI。
5. TeamDelete / shutdown / TaskStop。
