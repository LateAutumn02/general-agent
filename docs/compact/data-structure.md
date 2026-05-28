# 数据结构

> 上下文压缩（Compact）系统的核心数据结构。

---

## 压缩阈值常量

```
AUTOCOMPACT_BUFFER_TOKENS: 13,000      # 自动压缩缓冲区
WARNING_THRESHOLD_BUFFER_TOKENS: 20,000 # 警告阈值缓冲区
ERROR_THRESHOLD_BUFFER_TOKENS: 20,000   # 错误阈值缓冲区
MANUAL_COMPACT_BUFFER_TOKENS: 3,000     # 手动压缩缓冲区
MAX_OUTPUT_TOKENS_FOR_SUMMARY: 20,000   # 压缩摘要输出上限
MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES: 3 # 断路器
```

## 上下文窗口计算

```
getEffectiveContextWindowSize(model) -> int:
  MIN(contextWindowForModel, CLAUDE_CODE_AUTO_COMPACT_WINDOW) - 20,000

contextWindowForModel:
  1,000,000  如果模型名后缀 '[1m]' 或 1M beta 启用
  200,000    默认（MODEL_CONTEXT_WINDOW_DEFAULT）
```

## Token 阈值层级

对于标准 200K 模型：

| 层级 | 阈值 | 条件 |
|---|---|---|
| **警告** | 147,000 | `isAboveWarningThreshold` |
| **错误** | 147,000 | `isAboveErrorThreshold` |
| **自动压缩** | 167,000 | `isAboveAutoCompactThreshold` |
| **阻塞** | 177,000 | `isAtBlockingLimit`（仅自动压缩关闭时） |

---

## AutoCompactTrackingState

跨轮次追踪的压缩状态：

```
AutoCompactTrackingState:
  compacted: bool              # 本轮是否已压缩成功
  turnCounter: int             # 压缩后轮次计数器
  turnId: str                  # 压缩轮次标识
  consecutiveFailures: int     # 连续失败次数（断路器，上限 3）
```

---

## CompactionResult

压缩操作的完整结果：

```
CompactionResult:
  boundaryMarker: SystemMessage           # 系统压缩边界消息（SystemCompactBoundaryMessage）
  summaryMessages: list[UserMessage]       # 摘要注入为用户消息
  attachments: list[AttachmentMessage]    # 压缩后附件
  hookResults: list[HookResultMessage]    # SessionStart hook 结果
  messagesToKeep: list[Message]           # (可选) 保留的尾部消息
  userDisplayMessage: str                # (可选) Hook 提供的显示文本
  preCompactTokenCount: int              # 压缩前 Token 数
  postCompactTokenCount: int             # 压缩 API 总 Token 数
  truePostCompactTokenCount: int         # 结果上下文大小估计
  compactionUsage: dict                  # Token 用量详情
```

---

## RecompactionInfo

压缩链信息（用于循环检测）：

```
RecompactionInfo:
  isRecompactionInChain: bool            # 同一链内重新压缩检测
  turnsSincePreviousCompact: int          # 自上次压缩以来的轮次
  previousCompactTurnId: str             # (可选) 上次压缩轮次 ID
  autoCompactThreshold: int              # 自动压缩阈值
  querySource: str                       # 查询源
```

---

## MicrocompactResult

增量微压缩的结果：

```
MicrocompactResult:
  messages: list[Message]                # 微压缩后的消息
  compactionInfo:
    pendingCacheEdits: dict             # (可选) 待处理缓存编辑
```

---

## Token 警告状态

```
TokenWarningState:
  isAboveWarningThreshold: bool           # 超警告阈值
  isAboveErrorThreshold: bool            # 超错误阈值
  isAboveAutoCompactThreshold: bool       # 超自动压缩阈值
  isAtBlockingLimit: bool                # 达阻塞限制
  currentTokenCount: int                 # 当前 Token 数
  threshold: int                         # 自动压缩阈值
  messagesSinceCompact: int              # 自上次压缩以来的消息数
```

---

## SessionMemoryCompactConfig `[v1置空]`

```
SessionMemoryCompactConfig:
  minTokens: int           # 最小 Token 阈值（默认 10,000）
  minTextBlockMessages: int  # 最小文本块消息数（默认 5）
  maxTokens: int           # 最大 Token 限制（默认 40,000）
```

---

## TimeBasedMCConfig

基于时间的微压缩触发配置：

```
TimeBasedMCConfig:
  enabled: bool                  # 是否启用
  gapThresholdMinutes: int       # 空闲间隔阈值（默认 60 分钟）
  keepRecent: int                # 保留最近 N 个工具结果（默认 5）
```

---

## SystemCompactBoundaryMessage

压缩边界系统消息：

```
SystemCompactBoundaryMessage:
  role: 'system'
  subtype: 'compact_boundary'
  compactMetadata:
    trigger: str                  # 触发原因（auto / manual / reactive）
    preTokens: int               # 压缩前 Token 数
    userContext: str              # 用户上下文
    messagesSummarized: int       # 被压缩的消息数
    preservedSegment: dict        # (可选) 保留的片段信息
    preCompactDiscoveredTools: list  # (可选) 压缩前已发现的工具
```

## 摘要消息标记

压缩后的摘要消息注入时带有特殊标记：

```
CompactSummaryMessage:
  role: 'user'
  isCompactSummary: true         # 标记为压缩摘要
  suppressFollowUpQuestions: bool  # 是否强制继续不提问
```

---

## v1 简化

general-agent v1 仅需：

```
CompactionResult
AutoCompactTrackingState
TokenWarningState
SystemCompactBoundaryMessage
阈值常量
```

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/services/compact/compact.ts, autoCompact.ts, microCompact.ts, prompt.ts
