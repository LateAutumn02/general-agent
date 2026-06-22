# Swarm 蜂群协作流程

> 最后更新：2026-06-22 | 参考：reference/cc-haha/src/tools/AgentTool, TeamCreateTool, SendMessageTool, coordinatorMode, teammateMailbox

## 核心设计理念

**工具驱动，非用户命令。** cc-haha 没有 `/swarm` slash command。LLM 通过 Agent Tool 的 prompt 描述自主判断何时需要并行派发子 agent。用户只需用自然语言描述任务，模型自己决定 fan-out 策略。

## 启动方式

### 方式1：Agent Tool（LLM 自主调用）

用户说"审查整个项目的安全问题" → LLM 判断需要并行 → 自主调用 `Agent` tool：

```
Agent({ description: "Auth security audit", subagent_type: "Explore", prompt: "..." })
Agent({ description: "Dependency scan",    subagent_type: "Explore", prompt: "..." })
Agent({ description: "Injection check",    subagent_type: "Explore", prompt: "..." })
```

三个子 agent 并行执行，结果返回主 agent，主 agent 综合后呈现给用户。

### 方式2：TeamCreate + Agent（LLM 自主建队）

当任务更复杂且需要 agent 间通信时，LLM 先建队再 spawn：

```
TeamCreate({ team_name: "security-review" })
  → 创建团队文件 ~/.claude/teams/security-review/config.json
  → 创建任务目录 ~/.claude/tasks/security-review/
  → 设置 leader 的 teamContext

Agent({ name: "auth-checker",    team_name: "security-review", prompt: "..." })
Agent({ name: "dep-scanner",     team_name: "security-review", prompt: "..." })
Agent({ name: "injection-tester", team_name: "security-review", prompt: "..." })
```

子 agent 之间可以通过 `SendMessage({ to: "dep-scanner", message: "..." })` 直接通信。

### 方式3：Coordinator 模式（环境变量触发）

设置 `CLAUDE_CODE_COORDINATOR_MODE=1`，系统提示词切换为协调者角色。协调者拥有 `Agent`、`SendMessage`、`TaskStop` 三个核心工具。

## 整体流程

### 阶段1：建队（TeamCreate）

1. LLM 判断任务需要多 agent 协作 → 调 `TeamCreate({ team_name })`
2. 写入团队文件 `~/.claude/teams/{name}/config.json`：
   - `name`, `description`, `createdAt`
   - `leadAgentId`, `leadSessionId`
   - `members[]` — 初始只有 team-lead 自己
3. 创建对应任务列表 `~/.claude/tasks/{name}/`
4. 更新 `AppState.teamContext`，后续 Agent 调用自动继承 team_name

### 阶段2：派发（Agent spawn）

1. LLM 调 `Agent({ name, team_name?, description, prompt, subagent_type? })`
2. `resolveTeamName()` 决定是否为 teammate spawn：
   - 显式传了 `team_name` → 队友 spawn
   - `AppState.teamContext` 已有 team → 自动继承
   - 否则 → 独立子 agent（无团队通信能力）
3. `spawnTeammate()` 执行实际 spawn：
   - **tmux 模式**：创建新 pane，启动新 Claude 进程，传 agent 身份 CLI 参数
   - **in-process 模式**：同进程内用 AsyncLocalStorage 隔离上下文
   - **remote 模式**：CCR 远程环境（ant 内部）
4. 子 agent 进程获得受限工具集（不可递归调用 Agent tool）
5. 子 agent 转录写入 `<sessionDir>/subagents/agent-<agentId>.jsonl`

### 阶段3：通信（SendMessage + Mailbox）

**消息投递**：

1. 发送方调 `SendMessage({ to: "receiver-name", message: "..." })`
2. `SendMessageTool.call()` 路由消息：
   - `to: "name"` → 直接消息：写入接收方信箱
   - `to: "*"` → 广播：写入所有团队成员信箱
   - `to: "uds:<path>"` → 本地跨 session
   - `to: "bridge:<id>"` → 跨机器
3. `writeToMailbox(teamName, agentName, message)`：
   - 路径：`~/.claude/teams/{team}/inboxes/{agent}.json`
   - 带文件锁的并发写入（`lockfile` 库，最多重试 10 次）
   - 消息格式：`{ from, text, timestamp, read: false, color?, summary? }`
4. 接收方读取 `getInboxMessages()` → 标记已读 → 作为 conversation turn 注入

**结构化协议消息**（`StructuredMessage`）：

- `shutdown_request` — 请求队友优雅关闭
- `shutdown_response` — 批准/拒绝关闭
- `plan_approval_response` — plan mode 审批
- `permission_request / response` — 权限委托
- `idle_notification` — 队友进入空闲状态（turn 结束自动发送）

**消息可见性**：
- 队友发来的消息自动作为 conversation turn 注入
- 如果主 agent 正在执行中（mid-turn），消息排队等待 turn 结束后投递
- UI 以 `<teammate_message>` 标签展示，含发送者名称和颜色

### 阶段4：任务协调（Task Tools）

团队通过共享任务列表协调工作：

1. **TaskCreate** — 创建任务（含 owner、dependencies、status）
2. **TaskList** — 列出所有任务及状态
3. **TaskUpdate** — 认领/完成/阻塞任务
4. **TaskGet** — 查看任务详情

队友应：
- 定期检查 TaskList，优先认领 ID 最小的未分配任务
- 完成任务后立即更新状态，然后检查下一个可做任务
- 被阻塞时通知 team-lead

### 阶段5：收敛（结果收集 + 关闭）

1. 主 agent 收集各子 agent 结果（通过转录文件或消息）
2. 综合所有发现，呈现统一报告给用户
3. 发送关闭请求：`SendMessage({ to: "*", message: { type: "shutdown_request" } })`
4. 队友收到后回复 `shutdown_response`（批准/拒绝）
5. `TeamDelete` 清理团队文件和任务目录

## 空闲状态机制

- 每个 turn 结束后，队友自动变为 idle，发送 `idle_notification`
- idle ≠ 停止 — 队友在等待输入，仍可接收消息
- 收到消息后自动唤醒，处理消息内容
- 主 agent 不要对 idle 状态做过度反应

## 工具权限矩阵

| 角色 | 可用工具 |
|------|---------|
| **Leader / Coordinator** | Agent, SendMessage, TaskStop, 全部基础工具 |
| **Teammate (tmux)** | Bash, Read, Edit, Write, Grep, Glob, WebSearch, WebFetch, TodoWrite, Skill, TaskCreate, TaskGet, TaskList, TaskUpdate, SendMessage |
| **Teammate (in-process)** | 同上 + cron 工具 |
| **所有子 agent 禁止** | Agent（防止递归）、AskUserQuestion、EnterPlanMode、ExitPlanMode |

## 生命周期

```
TeamCreate → Agent×N → [SendMessage ↔ Mailbox] → TaskUpdate → Shutdown → TeamDelete
```

## v1 实现范围

1. ✅ Agent Tool 定义和 prompt（LLM 可自主调用）
2. ✅ TeamCreate / TeamDelete 工具
3. ✅ 基于文件的 Mailbox（写消息到信箱文件）
4. ✅ SendMessage 工具（点对点 + 广播）
5. ✅ Agent spawn（子进程，有限工具集）
6. ✅ 空闲通知（turn 结束后自动发送）
7. ❌ tmux/iTerm2 分屏后端（v1 只用 in-process）
8. ❌ Coordinator 模式（后续通过 env var 启用）
9. ❌ 结构化协议消息（shutdown/plan_approval）
10. ❌ 权限委托
11. ❌ 跨机器 Bridge 通信

## 可视化架构

cc-haha 的蜂群可视化为 8 层渐进展开系统：

### 第1层：Spinner 状态树（始终可见）

```
⠋ Analyzing...                              ← leader 当前动词
  ╞═ @researcher  Searching: src/auth.ts    ← teammate 实时状态
  ├─ @reviewer    Idle for 5s
  └─ @tester      Running tests...  8 tools · 45K tokens
```

每个 teammate 一行：名称（带颜色）+ 当前活动 + tool 计数 + token 计数。空闲队友显示 "Idle for Xs"，选中的显示更多统计。

### 第2层：Agent 结果摘要（transcript 内）

```
└─ Agent @researcher  3 tools · 12.5K tokens
   ⎿  Done
├─ Agent @reviewer    5 tools · 8K tokens
│  ⎿  Reading: src/config.ts…
```

子 agent 执行完毕后，在 transcript 中显示一行树形摘要。

### 第3层：工具调用进度（agent 执行中）

```
Running 3 agents... [ctrl+o to expand]
  Initializing...                          ← 未开始
  Searching: 5 searches, 3 file reads      ← 同类操作折叠
  Editing: src/config.ts                   ← 最新活动
  +5 more tool uses [ctrl+o to expand]     ← 折叠历史
```

连续同类搜索/读取操作自动折叠为统计行（如 "Searching: 5 searches"）。

### 第4层：队友消息渲染（聊天内）

```xml
<teammate-message teammate="alice" color="red" summary="Auth audit done">
  [✓] Completed task #123 (Auth module security audit)
</teammate-message>
```

消息类型：task_completed（绿色 ✓）、task_assignment（青色框）、shutdown_request、idle_notification（隐藏）、纯文本。

### 第5层：任务面板

```
12 tasks (5 done, 3 in progress, 4 open)
[✓] Auth module audit         @researcher   done
[■] API review                @reviewer     Reading: api.ts
[ ] Dependency scan           (unassigned)
[ ] Write report              blocked by #3
```

优先级排序，显示 owner / activity / 阻塞关系。

### 第6层：Footer Agent Pills

```
[main]  [@researcher]  [@reviewer]  [@tester]  [↓ to view]
```

水平滚动的 agent 标签，选中高亮。

### 第7层：Coordinator 底部面板

```
--> ● main
    ▶ @researcher  Auth audit         ▶ 12K  2m30s
    ■ @reviewer    API review          ■ 8K   5m10s
```

可选择的 background agent 列表，显示运行时间、token、消息数。

### 第8层：Prompt Banner

```
@team-lead> ▌                    ← 当前输入身份
```

按 Ctrl+B 切换输入上下文。

---

## 与当前 /swarm 命令的差异

| | 当前实现 | cc-haha 方式 |
|---|---|---|
| 触发 | `/swarm <goal>` 用户命令 | LLM 自主调 `Agent` tool |
| 团队 | 临时创建 plan → members | TeamCreate 建立持久团队文件 |
| 通信 | 无 | SendMessage + Mailbox 信箱 |
| 协调 | 共享 plan 状态 | Task Tools 任务列表 |
| 生命周期 | 一次性执行 | 建队 → 派发 → 通信 → 关闭 → 清理 |
