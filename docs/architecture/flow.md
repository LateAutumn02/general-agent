# 系统架构流程

> 最后更新：2026-06-17

## 阶段1：进程启动

1. **解析 CLI 参数** - 读取交互模式、无头模式、模型、权限模式、工作目录和恢复参数。
2. **加载配置** - 合并环境变量、用户配置、项目配置和命令行覆盖值。
3. **创建 AppContext** - 组装模型客户端、工具注册表、会话仓库、权限控制器和任务注册表。

## 阶段2：进入运行模式

1. **TUI 模式** - 启动 Ink 应用，渲染 transcript、输入框、footer、权限面板和任务视图。
2. **Print 模式** - 不启动 TUI，直接处理单次 prompt 并输出 text/json/stream-json。
3. **Recovery 模式** - 在 TUI 不可用时使用简单 readline 循环，保留核心工具能力。

## 阶段3：Agent 事件流

1. **用户输入变为 TurnRequest** - TUI 将普通输入、bash mode、slash command 和恢复操作统一发给 runtime。
2. **Agent 产生 RuntimeEvent** - agent loop 流式输出 assistant delta、tool call、permission request、task update 等事件。
3. **UI 消费 RuntimeEvent** - TUI 不直接调用工具，只根据事件更新可见状态。

## 阶段4：持久化和恢复

1. **会话追加写入** - 每个用户消息、助手消息、工具调用和工具结果都写入 JSONL。
2. **状态快照更新** - 任务、权限偏好、模型信息和 cwd 等元数据写入 session index。
3. **恢复时重放上下文** - `/resume` 读取完整消息历史，并重新构造 transcript 视图和 agent state。

## v1 简化流程

1. 先实现 Bun CLI + Ink TUI。
2. 先支持单主会话，不做桌面端和远程通道。
3. 工具系统先覆盖 Bash、Read、Write、Edit、Grep、Glob。
4. 会话存储使用本地 JSONL。
5. 后台任务只做用户手动创建和查看。

## 差异说明

- Python 版把 agent、工具和 Textual UI 紧耦合在一个进程内；TS 版改成事件驱动，UI 只消费事件。
- 后续桌面端、IM、远程通道等能力不在本项目 v1 范围内；本项目 v1 只做终端体验。

