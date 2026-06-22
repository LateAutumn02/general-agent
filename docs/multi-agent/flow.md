# 多 Agent 流程

> 最后更新：2026-06-22 | 参考：reference/cc-haha/src/tools/AgentTool, spawnMultiAgent, coordinatorMode

## 核心设计

多 Agent 和 Swarm 的关系：**Agent Tool 是统一入口，加了 TeamCreate 就升级为蜂群**。

| 模式 | 触发 | 通信 | 适用 |
|------|------|------|------|
| **子 Agent**（Sub-agent） | LLM 调 `Agent({ description, prompt })` | 无 — 独立执行，结果返回主 agent | 搜索、审计、单次任务 |
| **Fork Agent** | LLM 调 `Agent({ name, prompt })`（无 subagent_type） | 无 — 继承主 agent 全部上下文 | 不要中间工具输出污染上下文 |
| **蜂群 Teammate** | TeamCreate 后调 `Agent({ name, team_name })` | SendMessage + Mailbox | 复杂协作，需要 agent 间直接通信 |

## 阶段1：子 Agent 创建

1. **LLM 判断需要委托** — 根据 Agent Tool 的 prompt 描述自主决定。
2. **构造 prompt** — 包含上下文、文件路径、期望结果。prompt 必须是自包含的（子 agent 看不到主 agent 的对话历史）。
3. **选择 agent 类型**：
   - 省略 `subagent_type` → fork 自身（继承上下文）
   - `"Explore"` → 只读搜索
   - `"Plan"` → 架构设计
   - `"general-purpose"` → 通用（含文件编辑）

## 阶段2：执行模式

| 模式 | 说明 |
|------|------|
| **前台**（默认） | 主 agent 等待子 agent 完成后继续 |
| **后台** `run_in_background: true` | 主 agent 继续其他工作，完成后自动通知 |
| **worktree 隔离** `isolation: "worktree"` | 子 agent 在临时 git worktree 中工作，避免文件冲突 |

## 阶段3：并行派发

LLM 可以**在同一消息中发起多个 Agent tool call** 实现并行：

```
assistant: 我来并行审计三个模块。

Agent({ description: "Auth audit", subagent_type: "Explore", prompt: "..." })
Agent({ description: "API audit",  subagent_type: "Explore", prompt: "..." })
Agent({ description: "DB audit",   subagent_type: "Explore", prompt: "..." })
```

三个子 agent 同时执行，结果返回后主 agent 综合。

## 阶段4：结果处理

1. **前台 agent** — 结果直接注入主 agent 上下文作为 tool_result
2. **后台 agent** — 完成后以 `<task-notification>` 用户消息形式通知
3. **Fork agent** — 转录写入 `output_file`，主 agent 收到完成通知（不读转录内容）

## 阶段5：继续已有 Agent

用 `SendMessage` 续接之前 spawned 的 agent（保留其完整上下文）：

```
SendMessage({ to: "researcher", message: "深入分析你之前找到的那个漏洞" })
```

## Tool 权限

子 agent 不能递归生成 agent（`Agent` tool 在子 agent 中禁用）。其他工具根据 agent 类型白名单控制：

| Agent 类型 | 可用工具 |
|-----------|---------|
| Explore | Read, Glob, Grep, WebSearch, WebFetch |
| Plan | Read, Glob, Grep, WebSearch, WebFetch |
| general-purpose | Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch, TodoWrite, Skill |
| Fork（无 subagent_type） | 继承父 agent 全部工具（除 Agent/AskUserQuestion） |

## v1 实现范围

1. ✅ 子 Agent spawn（同步，in-process）
2. ✅ Fork Agent（继承上下文）
3. ✅ 并行派发（同一消息多个 Agent call）
4. ❌ 后台执行（run_in_background）
5. ❌ worktree 隔离
6. ❌ SendMessage 续接（需要 Mailbox 系统）
