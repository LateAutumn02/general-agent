# 流程

> 沙箱系统的执行流程。命令隔离、文件系统和网络限制。

---

## 概览

沙箱系统在 macOS（Seatbelt）和 Linux（Bubblewrap）上提供容器级命令执行隔离。它拦截 Bash 工具调用，在沙箱容器中执行命令，限制文件系统写访问和网络访问，并记录违规行为。v1 采纳沙箱的核心安全理念——通过 OS 级隔离执行不可信命令。

---

## 阶段1：启用检查

### 平台支持

| 平台 | 技术 | 状态 |
|---|---|---|
| macOS | Seatbelt（内置） | 支持 |
| Linux / WSL2 | Bubblewrap (`bwrap`) + Socat | 需要 `apt install bubblewrap socat` |
| WSL1 | 不支持 | 明确阻止 |

### 依赖检查

- **ripgrep** — 所有平台（检测危险目录）
- **bubblewrap** — Linux/WSL2（核心隔离）
- **socat** — Linux/WSL2（HTTP/SOCKS 代理）
- **seccomp** — Linux/WSL2（可选，Unix 域套接字过滤）

### 启用条件

```python
is_sandboxing_enabled():
  if not is_supported_platform(): return False
  if check_dependencies().has_errors(): return False
  if not is_platform_in_enabled_list(): return False
  return settings.get('sandbox.enabled', False)
```

---

## 阶段2：启动初始化

### 平台特定初始化

1. **macOS** — Seatbelt 始终可用，无需设置
2. **Linux/WSL2** — bwrap 必须安装好并通过 `check_dependencies()` 验证
3. **WSL1** — 启动时立即检测并标记为不可用

### 依赖状态检查

```
checkDependencies():
  ├── ripgrep: required_all = True  → 必须存在
  ├── seatbelt (macOS): 内置        → 总是通过
  └── bwrap + socat (Linux):
      ├── bwrap: required_all = True → 必须存在
      ├── socat: required_all = True → 必须存在
      └── seccomp: optional           → 警告但不阻止
```

### 沙箱管理初始化

```
SandboxManager.initialize(sandbox_ask_callback)
  1. 创建 SandboxManager 实例
  2. 如果平台不支持 → 记录原因
  3. 如果依赖缺失 → 记录缺失项
  4. 设置回调（用于网络权限对话框）
  5. is_initialized = True
```

---

## 阶段3：命令执行决策

### 决策流程（`shouldUseSandbox`）

```
should_use_sandbox(command):
  |
  ├── 全局禁用？→ False（平台不支持 / 依赖缺失 / settings.enabled=false）
  |
  ├── dangerouslyDisableSandbox 且 allowed？→ False
  |   (SandboxManager.are_unsandboxed_commands_allowed() 检查)
  |
  ├── 命令为空？→ False
  |
  ├── 命令匹配 excludedCommands 模式？→ False
  |   (来自设置中 sandbox.excludedCommands 列表)
  |
  └── 否则 → True（对命令进行沙箱化）
```

### 排除命令配置

```
新增排除项:
  /sandbox exclude <command>      # 通过 CLI 命令线排除某个命令
  设置: sandbox.excludedCommands  # 排除列表
```

---

## 阶段4：沙箱包装

### `wrapWithSandbox()` 流程

```
Shell 执行:
  |
  ├── 检查 should_use_sandbox(command)
  |
  ├── SandboxManager.wrap_with_sandbox(command, shell, config, signal)
  |    |
  |    ├── 应用文件系统限制（读写路径）
  |    |   ├── allowWrite: [cwd, temp_dir, ...additional_dirs, ...allow_rules]
  |    |   ├── denyWrite: [settings_files, managed_dirs, .claude/skills, ...]
  |    |   ├── denyRead: [deny_rules from permissions]
  |    |   └── allowRead: [allow_read_rules]
  |    |
  |    ├── 强制网络限制
  |    |   ├── HTTP 代理：sandbox.network.httpProxyPort
  |    |   ├── SOCKS 代理：sandbox.network.socksProxyPort
  |    |   ├── 域过滤：allowedDomains / deniedDomains
  |    |   └── Unix 域套接字：allowUnixSockets / allowAllUnixSockets
  |    |
  |    ├── 记录违规（通过 ViolationStore）
  |    └── 触发 ask 回调（用于网络权限）
  |
  ├── 创建沙箱临时目录（mode: 0o700）
  |
  ├── 命令在隔离容器中执行
  |
  └── SandboxManager.cleanup_after_command()
       ├── 清理 bwrap 临时文件
       └── 清理裸仓库 git 文件（安全防护 — 防止植入）
```

### 文件系统限制派生

沙箱的文件系统限制从**权限规则**中派生：

```
权限规则 → 文件系统限制：

Edit(allow)   → allowWrite 中添加解析后的路径
Edit(deny)    → denyWrite 中添加解析后的路径
Read(deny)    → denyRead 中添加解析后的路径
Write(allow)  → allowWrite 中添加解析后的路径
Write(deny)   → denyWrite 中添加解析后的路径

始终：
  allowWrite: ['.', temp_dir, additional_dirs, git_worktree_paths]
  denyWrite:  [settings.json files, managed_settings_dir, .claude/skills]
```

### 路径解析

- `//path` → 绝对路径
- `/path` → 相对于设置文件
- `~/path` → 相对于 home
- `./path` / `path` → 相对于当前工作目录

---

## 阶段5：网络限制

### HTTP/SOCKS 代理模式

所有网络流量通过配置的代理端口路由：
- `sandbox.network.httpProxyPort`
- `sandbox.network.socksProxyPort`

### 域过滤

- `allowedDomains` — 允许的域
- `deniedDomains` — 拒绝的域
- `WebFetch` 权限规则 → 双重复用为网络过滤

### 网络权限对话框

当请求超出允许的域时：
1. 沙箱记录网络违规
2. 触发 `SandboxAskCallback`
3. 向用户显示权限对话框
4. 用户允许/拒绝/持久保存

### Unix 域套接字控制

- `allowUnixSockets` — 精确允许
- `allowAllUnixSockets` — 禁用过滤（仅 Linux）
- `allowLocalBinding` — 允许本地端口绑定

---

## 阶段6：安全特性

### 裸仓库入侵防御

关键安全防护：攻击者可能试图将恶意文件植入工作树中，诱使未沙箱化的 git 将这些文件视为裸仓库。沙箱通过以下方式阻止：

1. 所有命令执行后调用 `scrubBareGitRepoFiles()`
2. 检查和移除 `HEAD`、`objects`、`refs`、`hooks`、`config` 文件
3. 对已存在的文件进行 denyWrite

### 违规记录

`SandboxViolationStore` 跟踪违规：
- 最多保留 10 条最近违规
- 按类型过滤，支持忽略模式（`sandbox.ignoreViolations`）
- 显示在扩展视图中（UI）

### killswitch

- `sandbox.failIfUnavailable: true` — 如果沙箱无法启动则退出并报错
- `sandbox.enabled: false` — 全局关闭
- `dangerouslyDisableSandbox` — 参数级 per-command 关闭

---

## 阶段7：PowerShell 沙箱

沙箱也支持 PowerShell 命令：
1. PowerShell 命令首先被检测
2. 内部 Shell 被替换为 `/bin/sh`（bwrap 硬编码 `<shell> -c '<cmd>'`）
3. 与 Bash 应用相同的文件系统和网络限制
4. 结果进行沙箱违规清洗

---

## v1 简化

general-agent v1 的沙箱实现：

1. **OS 级容器隔离** — macOS Seatbelt / Linux Bubblewrap
2. **文件系统限制** — 从权限规则派生的读写限制
3. **网络隔离** — 域过滤 / 代理路由
4. **命令级决策** — `should_use_sandbox()` per 命令
5. **不做** — 违规 UI、Channel 网络权限对话框、XAA、seccomp（可选）

---

## 与 Claude Code 源项目的差异说明

| 功能 | Claude Code | general-agent v1 | 原因 |
|---|---|---|---|
| 容器技术 | `@anthropic-ai/sandbox-runtime` 外部包 | 直接集成 Seatbelt / bwrap | 避免外部包依赖 |
| 违规 UI | React 组件 + 扩展视图 | 仅记录日志 | 不实现 TUI |
| 网络权限对话框 | SandboxPermissionRequest（TUI） | 按权限规则自动决定 | 简化 |
| 医生诊断 | `/doctor` 命令 | 手动检查 | 最小化 |
| Channel 网络权限中继 | Telegram/Discord 消息提示 | 不做 | 无 channel |
| 缓存编辑 | Cached MC API 集成 | 不做 | API 特定 |
| 沙箱设置 UI | 交互式模式选择器 | 配置文件 | 仅文件配置 |

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/utils/sandbox/sandbox-adapter.ts, src/tools/BashTool/shouldUseSandbox.ts, src/utils/Shell.ts
