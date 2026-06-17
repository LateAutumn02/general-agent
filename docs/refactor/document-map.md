# 文档迁移映射

> 最后更新：2026-06-17

旧 Python 文档已经归档到 `legacy/python/docs/`。TypeScript 重构版使用新的模块命名，映射如下。

| 旧文档目录 | 新文档目录 | 说明 |
|---|---|---|
| `architecture/` | `architecture/` | 保留系统架构，但改为事件驱动 TS 架构 |
| `initialization/` | `initialization/` | 保留启动流程，改为 Bun/CLI/bootstrap |
| `api/` | `api/` | 保留模型 API，改为 streaming client 抽象 |
| `agent/` | `agent/` | 保留 Agent loop，改为 RuntimeEvent 驱动 |
| `tools/` | `tools/` | 保留工具系统，改为 ToolDefinition + PermissionController |
| `bash-ui/` | `tui/` | Bash UI 扩展为完整终端 UI 文档 |
| `sandbox/` | `sandbox/` + `permissions/` | 安全边界和用户审批拆开 |
| `session-persistence/` | `session/` | 会话恢复和 JSONL 存储合并 |
| `compact/` | `compact/` | 保留上下文压缩设计 |
| `memory/` | `memory/` | 保留记忆系统，但自动写入后置 |
| `skills/` | `skills/` | 保留技能系统 |
| `mcp/` | `mcp/` | 保留 MCP，v1 只做 stdio tools |
| `multi-task/` | `tasks/` | 多任务后台看板改名为任务系统 |
| `multi-agent/` | `multi-agent/` | 保留多 Agent 设计 |
| `swarm/` | `swarm/` | 保留团队协作设计，排在后续阶段 |

新文档不是旧文档的逐字翻译，而是把旧设计意图迁移到 TypeScript/Bun/Ink 架构下。

