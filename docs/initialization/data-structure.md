# 数据结构

> 程序初始化阶段创建和维护的核心数据结构。

---

## STATE 全局状态

在模块加载时创建，进程级单例，包含 250+ 字段。v1 仅需以下核心字段：

```
State:
  [v1] sessionId: str              # 会话唯一标识（UUID）
  [v1] originalCwd: str            # 会话启动时的原始工作目录
  [v1] projectRoot: str            # 项目根目录（Git 根或 cwd）
  [v1] cwd: str                    # 当前工作目录
  [v1] totalCostUSD: float         # 累计 API 费用
  [v1] totalAPIDuration: int       # 累计 API 耗时（毫秒）
  [v1] startTime: int              # 启动时间戳（毫秒）
  [v1] lastInteractionTime: int    # 最后一次用户交互时间戳
  [v1] isInteractive: bool         # 是否交互模式
  [v1] isRemoteMode: bool          # 是否远程模式
  [v1] clientType: str             # 客户端类型（'cli' | 'sdk-cli' | 'mcp'）
  [v1] settings: dict              # 全局用户设置
  [v1] mainLoopModel: str          # 主循环使用的模型
  [v1] verbose: bool               # 详细输出模式
  [v1] todos: dict                 # 待办事项状态

  # === v1 不需要的字段 ===
  registeredHooks: dict            # 已注册的 hooks
  agentColorMap: dict              # Agent 颜色映射
  agentNameRegistry: dict          # Agent 名称注册表
  invokedSkills: dict              # 已调用的 Skills
  pluginState: dict                # 插件状态
  mcpState: dict                   # MCP 连接状态
  teamContext: dict                # 团队上下文
  speculation: dict                # 推测解码状态
  remoteSessionUrl: str            # 远程会话 URL
  # ... 另有 ~200 个 v1 不需要的字段
```

## 启动前置数据

### SystemContext

在 REPL 启动前通过并行 git 命令获取：

```
SystemContext:
  gitStatus: str                   # git status --short 输出
  branch: str                      # 当前分支名
  defaultBranch: str               # 默认分支名（main/master）
  recentCommits: str               # git log --oneline -n 5
  gitUserName: str                 # git config user.name
```

### UserContext

通过目录遍历读取记忆文件和 CLAUDE.md 获取：

```
UserContext:
  claudeMd: str                    # 聚合后的 CLAUDE.md 内容
  currentDate: str                 # 当前日期字符串
```

## 配置来源

general-agent v1 简化（仅保留核心配置）：

```
Settings:
  [v1] apiKey: str                 # API 密钥（环境变量直接配置）
  [v1] model: str                  # 模型名称
  [v1] permissionMode: str         # 权限模式
  [v1] maxTokens: int              # 最大 token 数
  [v1] temperature: float          # 温度参数
  [v1] autoMemoryEnabled: bool     # 是否启用自动记忆
  [v1] maxTurns: int               # 每轮最大工具调用次数
```

## 初始化标志

控制初始化流程路径的状态变量：

```
InitFlags:
  isBareMode: bool                 # --bare 标志，跳过 TUI
  isPrintMode: bool                # -p/--print 标志，非交互输出
  isSdkMode: bool                  # SDK 模式
  customSessionId: str             # 自定义会话 ID
  recoveryMode: bool               # 本地恢复模式（LAUDE_CODE_LOCAL_RECOVERY）
```

---

## v1 简化

general-agent v1 数据结构简化：
- **STATE** — 仅保留 12 个核心字段
- **SystemContext + UserContext** — 保留
- **Settings** — 仅 API key + model + 基本参数
- **不需要** — HookState、PluginState、MCPState、TeamContext、OAuth 状态、企业配置

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/bootstrap/state.ts, src/context.ts
