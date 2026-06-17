# 数据结构

> 沙箱系统的核心数据结构。

---

## 沙箱设置

```
SandboxSettings:
  enabled: bool                              # 主开/关（默认 false）
  failIfUnavailable: bool                    # 如果沙箱不可用则失败（默认 false）
  autoAllowBashIfSandboxed: bool             # sandboxed bash 跳过权限询问（默认 true）
  allowUnsandboxedCommands: bool              # 允许 dangerouslyDisableSandbox（默认 true）
  enabledPlatforms: list[str]               # (可选) 可用平台列表

  # 网络
  network:
    allowedDomains: list[str]               # 允许的域
    deniedDomains: list[str]                # 拒绝的域
    allowManagedDomainsOnly: bool            # 仅使用策略设置中的域
    allowUnixSockets: list[str]             # 允许的 Unix 域套接字路径（macOS）
    allowAllUnixSockets: bool               # 禁用套接字过滤
    allowLocalBinding: bool                 # 允许本地端口绑定
    httpProxyPort: int                      # (可选) HTTP 代理端口
    socksProxyPort: int                     # (可选) SOCKS 代理端口

  # 文件系统
  filesystem:
    allowWrite: list[str]                   # 额外可写路径
    denyWrite: list[str]                    # 额外不可写路径
    denyRead: list[str]                     # 不可读路径
    allowRead: list[str]                    # 在 denied 区域内重新允许读取
    allowManagedReadPathsOnly: bool          # 仅使用策略设置中的读取路径

  # 违规处理
  ignoreViolations: dict[str, bool]          # 按类型忽略
  enableWeakerNestedSandbox: bool            # 允许更宽松的嵌套沙箱
  enableWeakerNetworkIsolation: bool         # 允许 trustd.agent（macOS）

  # 命令配置
  excludedCommands: list[str]               # 不进行沙箱化的命令/模式

  # 工具
  ripgrep:
    path: str                               # (可选) 自定义 ripgrep 路径
    args: list[str]                         # (可选) 自定义 ripgrep 参数
```

---

## 沙箱运行时配置

从设置派生的运行时配置：

```
SandboxRuntimeConfig:
  # 文件系统限制
  allowWrite: list[str]                     # 可写路径（从权限规则派生）
  denyWrite: list[str]                      # 不可写路径
  denyRead: list[str]                       # 不可读路径
  allowRead: list[str]                      # 重新允许的读取路径

  # 网络限制
  networkAllowedDomains: list[str]           # 允许的域
  networkDeniedDomains: list[str]            # 拒绝的域
  networkAllowUnixSockets: list[str]         # 允许的 Unix 域套接字
  networkAllowAllUnixSockets: bool           # 禁用套接字过滤
  networkAllowLocalBinding: bool             # 允许本地绑定
  networkHttpProxyPort: int                 # HTTP 代理端口
  networkSocksProxyPort: int                # SOCKS 代理端口

  # 违规处理
  ignoreViolations: dict[str, bool]          # 按类型忽略
  enableWeakerNestedSandbox: bool            # 更宽松的嵌套
  enableWeakerNetworkIsolation: bool         # 更宽松的网络

  # 工具
  useAppImageRipgrepOnLinux: bool            # Ubuntu >= 23.04 调整
  ripgrep: dict                             # ripgrep 配置
```

---

## 沙箱管理器

核心单例状态管理：

```
SandboxManager:
  instance: SandboxManager | None            # 初始化标志

  # 启用检查
  isSandboxingEnabled() -> bool              # 主启用检查
  isSupportedOnThisPlatform() -> bool        # macOS / Linux / WSL2
  areUnsandboxedCommandsAllowed() -> bool     # allowUnsandboxedCommands 检查
  isSandboxUnavailable() -> bool             # 平台不支持或依赖缺失
  getSandboxUnavailableReason() -> str       # 不可用原因

  # 设置
  setSandboxSettings(settings) -> None       # 更新设置
  getSandboxEnabledSetting() -> bool          # sandbox.enabled

  # 命令包装
  wrapWithSandbox(command, shell, config, signal) -> str  # 用沙箱包裹命令
  cleanupAfterCommand() -> None              # 清理沙箱临时文件
  scrubBareGitRepoFiles() -> None            # 移除裸仓库工作树文件

  # 依赖项
  checkDependencies() -> DependencyStatus    # 检查依赖项
```

---

## 依赖状态

```
DependencyStatus:
  ripgrep: DependencyResult                  # rg 路径 + 版本
  bwrap: DependencyResult | None             # bwrap 存在性（Linux）
  socat: DependencyResult | None             # socat 存在性（Linux）
  seccomp: DependencyResult | None           # seccomp filter 存在性（Linux）

DependencyResult:
  available: bool                            # 要求/可选存在
  path: str                                  # 路径（如果找到）
  error: str                                 # 缺失时的错误信息
  errors: list[str]                          # 检查期间的所有错误
```

---

## 沙箱违规事件

```
SandboxViolationEvent:
  type: str                                  # 违规类型
  message: str                               # 违规描述
  timestamp: int                             # 发生时间
```

---

## 沙箱决策结果

```
ShouldUseSandboxResult:
  shouldUseSandbox: bool                     # 是否对命令进行沙箱化
  reason: str                                # 决策原因（用于调试）
```

---

## v1 简化

general-agent v1 仅需：

```
SandboxSettings（核心字段）
SandboxRuntimeConfig
ShouldUseSandboxResult
依赖状态（最小化，仅 bwrap + rg）
```

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/utils/sandbox/sandbox-adapter.ts, src/entrypoints/sandboxTypes.ts, src/tools/BashTool/shouldUseSandbox.ts
