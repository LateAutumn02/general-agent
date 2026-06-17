# general-agent 文档指南

> 最后更新：2026-06-17 | 适用范围：TypeScript 重构版

本目录描述新的 TypeScript-first 架构。旧 Python 实现和旧文档已经归档到 `legacy/python/`，只作为迁移参考。

## 文档结构

每个模块默认包含两份文档：

| 文件 | 用途 |
|---|---|
| `flow.md` | 描述模块从输入到输出的执行流程 |
| `data-structure.md` | 描述模块核心类型、事件、状态和接口 |

## 当前模块

| 模块 | 目录 | 状态 |
|---|---|---|
| 系统架构 | `architecture/` | 重构草案 |
| 启动初始化 | `initialization/` | 重构草案 |
| 配置与模型 API | `api/` | 重构草案 |
| Agent 核心循环 | `agent/` | 重构草案 |
| TUI | `tui/` | 重构草案 |
| 权限审批 | `permissions/` | 重构草案 |
| 工具系统 | `tools/` | 重构草案 |
| 会话持久化 | `session/` | 重构草案 |
| 上下文压缩 | `compact/` | 重构草案 |
| 记忆系统 | `memory/` | 重构草案 |
| Skills | `skills/` | 重构草案 |
| MCP | `mcp/` | 重构草案 |
| 沙箱安全 | `sandbox/` | 重构草案 |
| 后台任务 | `tasks/` | 重构草案 |
| 多 Agent | `multi-agent/` | 重构草案 |
| Swarm 协作 | `swarm/` | 重构草案 |
| 重构计划 | `refactor/` | 已创建 |

## 设计基准

新实现以 `reference/cc-haha` 作为体验参考，但不复制其源码结构。重点借鉴：

- Ink/React 风格的终端组件化渲染。
- `!` 进入 bash mode 的输入体验。
- 底部权限审批，不要求用户回滚屏幕查找确认框。
- compact transcript：工具调用折叠为摘要，长输出按需查看。
- foreground/background shell task 的任务模型。
- 会话恢复时还原完整上下文，而不是只展示一句摘要。

## 写作规则

1. 文档先行：大模块开始实现前先更新对应 `flow.md` 和 `data-structure.md`。
2. 明确 v1 范围：先写能落地的最小闭环，不把所有长期设想塞进第一版。
3. 行为优先：UI/交互文档要描述用户看到什么、按什么键、状态如何变化。
4. 类型稳定：数据结构文档优先定义跨模块事件和状态，避免实现时反复改接口。

