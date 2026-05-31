# 数据结构

> 会话持久化模块的核心类型定义与文件格式。

参考：cc-haha `src/types/logs.ts`、`src/utils/sessionStorage.ts`、`src/utils/listSessionsImpl.ts`

---

## 文件格式

### JSONL 条目结构

每条一行 JSON，不换行，UTF-8 编码。每行是一个独立的 Entry。

```
# 用户消息条目
{"type":"user","uuid":"...","parentUuid":"...","sessionId":"...","timestamp":"...","cwd":"...","version":"0.1.0","gitBranch":"main","message":{"role":"user","content":"Hello"}}

# 助手消息条目
{"type":"assistant","uuid":"...","parentUuid":"...","sessionId":"...","timestamp":"...","message":{"role":"assistant","content":[{"type":"text","text":"Hi!"}]}}

# 元数据条目
{"type":"custom-title","customTitle":"My Session","sessionId":"..."}
{"type":"tag","tag":"important","sessionId":"..."}
{"type":"last-prompt","lastPrompt":"review this PR","sessionId":"..."}
```

---

## Entry

顶层联合类型，所有条目的基类型：

```
Entry:
  type: str                                       # 条目类型标识（见下方枚举）
  uuid: str                                       # [v1] 唯一标识（UUID v4）
  sessionId: str                                  # [v1] 所属会话 ID
  parentUuid: str                                 # (可选) 父消息 UUID，用于链式遍历
  timestamp: str                                  # [v1] ISO 8601 UTC 时间戳
  cwd: str                                        # (可选) 写入时的当前工作目录
  version: str                                    # (可选) Agent 版本号
  gitBranch: str                                  # (可选) 当前 git 分支

entryType: 'user' | 'assistant' | 'attachment' | 'system' | 'custom-title' | 'tag' | 'agent-name' | 'last-prompt' | 'mode' | 'worktree-state'  # v1 仅需前 4 个 + custom-title + tag + last-prompt
```

---

## TranscriptMessage

会话链中的消息条目（user / assistant / attachment / system 四种）：

```
TranscriptMessage extends Entry:
  message: dict                                   # 完整的原始消息对象
    role: 'user' | 'assistant'                    # API 角色标识
    content: str | list[ContentBlock]             # 消息内容
  isSidechain: bool                               # [v1置空] 是否为子 Agent 侧链
  isMeta: bool                                    # (可选) 是否为元消息（不展示）
  isCompactSummary: bool                          # (可选) 是否为压缩摘要
  teamName: str                                   # [v1置空] 所属团队名称
  agentName: str                                  # [v1置空] Agent 名称
```

---

## ContentBlock

消息内容块：

```
ContentBlock:
  type: 'text' | 'tool_use' | 'tool_result'      # 内容块类型
  text: str                                       # 文本内容（type='text' 时）
  id: str                                         # 工具调用 ID
  name: str                                       # 工具名称
  input: dict                                     # 工具输入参数
  content: str | list[ContentBlock]               # 工具结果（可为嵌套块）
  is_error: bool                                  # 是否工具调用错误
```

---

## SessionInfo

会话列表中返回的元数据摘要：

```
SessionInfo:
  sessionId: str                                  # 会话 UUID
  summary: str                                    # 摘要（title > lastPrompt > firstPrompt）
  lastModified: int                               # 最后修改时间（epoch ms）
  fileSize: int                                   # (可选) 文件大小（bytes）
  customTitle: str                                # (可选) 用户自定义标题
  firstPrompt: str                                # (可选) 对话第一条用户消息
  gitBranch: str                                  # (可选) Git 分支
  cwd: str                                        # (可选) 工作目录
  tag: str                                        # (可选) 标签
  createdAt: int                                  # (可选) 创建时间（epoch ms）
```

---

## LiteSessionFile

快速读取的头/尾数据结构（用于会话发现，避免完整解析大文件）：

```
LiteSessionFile:
  head: str                                       # 文件前 64KB
  tail: str                                       # 文件后 64KB
  mtime: int                                      # 修改时间（epoch ms）
  size: int                                       # 文件大小（bytes）
```

---

## 存储路径

```
ProjectsDir:
  ~/.general_agent/projects/
     -> <sanitized-cwd>/                          # 按项目（工作目录）分组
        -> <session-uuid>.jsonl                   # 单次会话的完整历史

sanitizePath(path) -> str:
  方法一（Windows 兼容）：
    将路径转为绝对路径 → 替换非法字符为 '_' → 截断至 MAX_SANITIZED_LENGTH (150)
```

---

## 元数据条目

会话级别的附加信息，非消息链条目：

```
CustomTitleEntry:
  type: 'custom-title'
  customTitle: str                                # 用户自定义标题
  sessionId: str

TagEntry:
  type: 'tag'
  tag: str                                        # 标签文本
  sessionId: str

LastPromptEntry:
  type: 'last-prompt'
  lastPrompt: str                                 # 最后一次用户输入（截断至 200 字符）
  sessionId: str
```

这些元数据条目在会话退出时被重新追加到文件末尾（`reAppendSessionMetadata`），确保在 tail 窗口（64KB）内能被快速扫描读取。

---

## SessionStore

核心存储单例，管理当前会话的持久化：

```
SessionStore:
  _session_file: str | None                       # 当前会话文件路径（惰性创建）
  _disabled: bool                                 # 是否禁用持久化
  _message_uuids: set[str]                        # 已写入 UUID 集（去重）
  _session_metadata: dict[str, Any]               # 缓存元数据（custom_title, tag, last_prompt）

  disable()                                       # 禁用持久化
  is_disabled() -> bool                           # 检查是否禁用（含 bootstrap state 标记）
  ensure_session_file(sid, cwd) -> str            # 惰性创建会话文件路径
  enqueue(entry)                                  # 即时写入单条 JSONL 到磁盘
  insert_message_chain(msgs, sid, cwd, ...) -> str | None  # 批量写入消息链
  save_user_message(msg, sid, cwd, ...) -> str    # 保存用户消息，返回 UUID
  save_assistant_message(msg, sid, cwd, ...) -> str  # 保存助手消息，返回 UUID
  load_transcript(path) -> dict                   # 加载 JSONL 文件，重建消息链
  re_append_metadata()                            # 重启会话元数据到文件末尾
```

---

## v1 简化

general-agent v1 实现了：

```
Entry
TranscriptMessage (含 ContentBlock)
SessionInfo
LiteSessionFile
元数据条目 (custom-title, tag, last-prompt)
存储路径计算函数
SessionStore（即时写入，无缓冲）
SessionDiscovery（list_sessions, get_session_info）
atexit 退出钩子
/resume 斜杠命令
```

跳过的类型：
- `FileHistorySnapshotMessage` — v1 无快照功能
- `AttributionSnapshotMessage` — v1 无此能力
- `ContentReplacementEntry` — v1 无替换机制
- `MarbleOrigamiCommit / Snapshot` — v1 无此压缩模式
- `QueueOperationMessage` — v1 无此队列
- `RemoteAgentMetadata` — v1 无远程 Agent

---

> 最后更新: 2026-05-31 | 参考源 commit: 94b86ea | 参考文件: cc-haha src/types/logs.ts, src/utils/sessionStorage.ts, src/utils/sessionStoragePortable.ts, src/utils/listSessionsImpl.ts
