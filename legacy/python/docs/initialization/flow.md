# 流程

> general-agent 启动到进入主循环的完整初始化流程。从进程入口到 REPL 就绪。

---

## 概览

Claude Code 的启动流程跨越约 13 个阶段，从模块加载的副作用开始，经过配置系统初始化、服务注册、CLI 参数解析，最终启动 REPL。general-agent v1 大幅精简，跳过 TUI、插件、hook、远程等子系统。

---

## 阶段1：CLI 入口

**入口文件** `src/entrypoints/cli.tsx`

1. **设置环境变量** — `COREPACK_ENABLE_AUTO_PIN = '0'`（避免 corepack 自动 pin）
2. **消融基线检查** — 如果设置了 `CLAUDE_CODE_ABLATION_BASELINE`，激活 SIMPLE/DISABLE 系列环境变量
3. **快速路径分发** — 对 `--version`、`--dump-system-prompt` 等直接处理并退出
4. **`--bare` 标志** — 提前设置 `CLAUDE_CODE_SIMPLE = '1'`
5. **捕获早期输入** — `startCapturingEarlyInput()` 启动原始模式 stdin 捕获
6. **动态导入** — `import('../main.js')` 触发 `main.tsx` 所有模块加载

## 阶段2：全局状态创建（模块加载副作用）

**文件** `src/bootstrap/state.ts`

1. **创建 STATE 单例** — 包含 250+ 字段的会话全局可变对象：
   - `sessionId` — 随机 UUID
   - `originalCwd`、`projectRoot`、`cwd` — 通过 `realpathSync` 解析
   - `totalCostUSD: 0`、`totalAPIDuration: 0`、`startTime: Date.now()`
   - `isInteractive: false`、`isRemoteMode: false`、`clientType: 'cli'`
   - `registeredHooks: null`（后续填充）
   - 空 Map：`agentColorMap`、`planSlugCache`、`invokedSkills`

2. **并行预取启动**（`main.tsx` 导入时）：
   - `startMdmRawRead()` — MDM 子进程并行
   - `startKeychainPrefetch()` — macOS keychain 并行

## 阶段3：`main()` 入口

1. **安全设置** — Windows `NoDefaultCurrentDirectoryInExePath = '1'`
2. **信号处理器注册** — exit（重置光标）、SIGINT（退出）
3. **URL 解析** — `cc://` / `cc+unix://` 深度链接
4. **检测交互模式** — 检查 `-p`/`--print`、`--sdk-url`、`process.stdout.isTTY`
5. **设置客户端类型** — 确定 `CLAUDE_CODE_ENTRYPOINT`（cli / sdk-cli / mcp 等）
6. **预加载 settings** — `eagerLoadSettings()` 在 `init()` 前解析 `--settings` 和 `--setting-sources`
7. **调用 `run()`** — 进入 Commander CLI 设置

## 阶段4：Commander 设置

**函数 `run()`**

1. **创建 Commander 程序** — 排序帮助、位置选项
2. **`preAction` 钩子**（所有命令都执行）：
   - 等待 `ensureMdmSettingsLoaded()` + `ensureKeychainPrefetchCompleted()`
   - **调用 `init()`** — 关键初始化（见阶段5）
   - `process.title = 'claude'`
   - `initSinks()` — 错误日志 + 分析接收器
   - 处理 `--plugin-dir`
   - `runMigrations()` — 11 步配置迁移
   - `loadRemoteManagedSettings()` + `loadPolicyLimits()` — fire-and-forget
3. **定义所有 CLI 选项** — `--debug`、`--print`、`--bare`、`--model`、`--permission-mode`、`--resume`、`--continue`、`--settings`、`--mcp-config`、`--agents`、`--plugin-dir`、`--thinking` 等

## 阶段5：`init()` 函数

**文件** `src/entrypoints/init.ts`（memoized，只执行一次）

1. **`enableConfigs()`** — 验证和启用配置系统，从所有来源读取 settings
2. **`applySafeConfigEnvironmentVariables()`** — 仅应用安全环境变量
3. **`applyExtraCACertsFromConfig()`** — 设置 `NODE_EXTRA_CA_CERTS`
4. **`setupGracefulShutdown()`** — 注册退出/错误处理器
5. **后台 fire-and-forget 任务**：
   - OTel 日志初始化
   - OAuth 账户信息填充
   - IDE 检测（JetBrains）
   - GitHub 仓库检测
   - 远程托管 settings / policy limits 加载 promise
6. **`recordFirstStartTime()`** — 记录首次启动时间戳
7. **`configureGlobalMTLS()`** — 设置 mTLS
8. **`configureGlobalAgents()`** — 配置 HTTP 代理
9. **`preconnectAnthropicApi()`** — fire-and-forget TCP+TLS 预连接
10. **Windows shell 设置** — `setShellIfWindows()` 设置 git-bash
11. **清理注册** — LSP 管理器关闭、团队清理

## 阶段6：并行加载

在 Commander action handler 中并行启动：

```
├── initBuiltinPlugins()          # 内置插件注册（当前为骨架）
├── initBundledSkills()           # 10+ 内置 Skill 注册
├── setupPromise: setup()         # ← 阶段7
├── commandsPromise: getCommands() # ← 阶段8
└── agentDefsPromise: getAgentDefinitionsWithOverrides()  # Agent 定义加载
```

## 阶段7：`setup()` 函数

**文件** `src/setup.ts`

1. **Node.js 版本检查** — 要求 v18+
2. **会话 ID 设置** — 自定义 sessionId 则调用 `switchSession()`
3. **UDS 消息服务器** — 启动 Unix Domain Socket（Mac/Linux，非 bare 模式）
4. **目录设置**：
   - `setCwd(cwd)` — shell 工作目录
   - `setOriginalCwd(cwd)` — 会话原始目录
   - `setProjectRoot(cwd)` — 项目根目录
5. **`captureHooksConfigSnapshot()`** `[v1置空]` — 从所有 settings 来源读取 hooks 配置
6. **`initializeFileChangedWatcher(cwd)`** `[v1置空]` — 设置 FileChanged hook 监听器
7. **Worktree 处理**（如果 `--worktree`）— 创建 git worktree + 可选 tmux
8. **后台注册**：
   - `initSessionMemory()` `[v1置空]` — 注册 auto-memory hook
   - `initContextCollapse()` `[v1置空]` — 注册上下文折叠监听器
9. **`lockCurrentVersion()`** — 防止被其他进程删除
10. **prefetch 并发启动**（fire-and-forget）：
    - `getCommands(getProjectRoot())` — 预加载所有命令
    - `loadPluginHooks()` `[v1置空]`
    - `setupPluginHookHotReload()` `[v1置空]`
11. **`initSinks()`** — 错误日志 + 分析事件处理器
12. **`logEvent('tengu_started')`** — 会话启动信标
13. **`prefetchApiKeyFromApiKeyHelperIfSafe()`** `[v1置空]`
14. **`--dangerously-skip-permissions` 安全检查** — 验证沙盒环境

## 阶段8：命令加载 `getCommands()`

**文件** `src/commands.ts`

1. **`loadAllCommands(cwd)`** — memoized by cwd，并行加载：
   - `getSkills(cwd)` — Skill 目录扫描 + 插件 skills + 内置 skills
   - `getPluginCommands()` — 插件非 skill 命令
   - `getWorkflowCommands()` — Workflow 命令
   - `COMMANDS()` — ~100 个内置命令（memoized）
2. **过滤**：
   - `meetsAvailabilityRequirement()` — 按认证/供应商过滤
   - `isCommandEnabled()` — 按功能开关过滤

## 阶段9：系统上下文和用户上下文

**文件** `src/context.ts`

1. **`getSystemContext()`** — memoized，5 个并行 git 命令：
   - 当前分支、默认分支
   - `git status --short`（截断至 2000 字符）
   - `git log --oneline -n 5`
   - `git config user.name`

2. **`getUserContext()`** — memoized：
   - `getMemoryFiles()` — 读取所有 CLAUDE.md / 记忆文件
   - `getClaudeMds()` — 组装 CLAUDE.md 内容字符串

## 阶段10：延迟预取

**函数 `startDeferredPrefetches()`** — REPL 渲染后触发

1. `initUser()` — 初始化用户资料
2. `getUserContext()` — 加载 CLAUDE.md
3. `prefetchSystemContextIfSafe()` — 加载 git status
4. AWS/GCP 凭证预取
5. `initializeAnalyticsGates()` — 加载 GrowthBook 功能开关
6. `refreshModelCapabilities()` — 刷新模型能力缓存
7. `settingsChangeDetector.initialize()` — 开始监听 settings 变更
8. `skillChangeDetector.initialize()` — 开始监听 skill 文件变更

## 阶段11：会话启动 Hooks `[v1置空]`

1. 跳过 bare 模式
2. 确保 `loadPluginHooks()` 完成
3. 遍历 `executeSessionStartHooks()`：
   - 收集 hook 消息、额外上下文、初始用户消息、监听路径
4. 更新 FileChanged watcher

## 阶段12：REPL 启动

1. **`launchRepl()`** — 创建 Ink 终端应用
2. 渲染 `App` 组件树（REPL、聊天、权限等）
3. 调用 `startDeferredPrefetches()` — 启动后台工作

---

## v1 实际实现 (Phase 1)

general-agent v1 Phase 1 实现的启动流程：

1. **模块级副作用** — colorama ANSI 初始化、`.env` 加载 (`~/.general_agent.env`)
2. **快速路径** — `--version`/`--help` 直接返回
3. **argparse CLI** — `--model`/`--print`/`--verbose`/`--continue`
4. **memoized `init()`** — 版本检查、配置验证、信号注册、STATE 初始化
5. **系统上下文** — `get_system_context()` 并行 5 个 git 命令注入 system prompt
6. **交互式配置** — 首次运行弹出向导（模型/接口/API key）
7. **REPL** — readline 输入循环、斜杠命令、流式响应展示

未实现（Phase 2+）：CLAUE.md 加载、命令注册、Skills 扫描、MCP 连接

## 与 Claude Code 源项目的差异说明

| 功能 | Claude Code | general-agent v1 | 原因 |
|---|---|---|---|
| TUI (Ink/React) | 完整 Ink 组件树 | 无（直接 readline） | Python 生态 |
| 插件系统 | 完整 | 不做 | 复杂性高 |
| Hook 系统 | SessionStart/Stop/PreToolUse 等 | 不做 | v1 不需要 |
| 远程模式/Bridge | 完整 | 不做 | 单人使用 |
| 企业 MDM/Policy | 完整 | 不做 | 个人项目 |
| Agent 定义加载 | 内置+自定义+插件 | 不做（无多 Agent） | v1 单 Agent |
| OTel/分析 | 完整遥测 | 不做 | 个人使用 |
| 配置迁移 | 11 步迁移 | 不做 | 新项目 |
| MCP 连接 | 完整 | 不做 | v1 只做内置工具 |
| Keychain/OAuth | macOS keychain | 不做（直接配置 API key） | 简化 |

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/entrypoints/cli.tsx, src/main.tsx, src/entrypoints/init.ts, src/setup.ts, src/bootstrap/state.ts, src/commands.ts, src/context.ts
