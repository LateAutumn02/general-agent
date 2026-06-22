# 会话持久化流程

> 最后更新：2026-06-22

## 阶段1：会话创建

1. **生成 UUID** - 进程启动时通过 `crypto.randomUUID()` 生成唯一 sessionId。此时不创建任何文件。

2. **懒创建 JSONL 文件** - `.jsonl` 文件直到**第一条用户或助手消息**才在磁盘上创建（`materializeSessionFile()`）。
   - 之前的条目暂存在内存 `pendingEntries[]` 中。
   - 这避免了空会话污染磁盘。

3. **文件路径格式**：
   ```
   .general-agent/sessions/<sanitized_cwd>/<sessionId>.jsonl
   ```
   - `sanitized_cwd` 将路径中的非字母数字字符替换为 `-`（如 `/Users/foo/my-project` → `-Users-foo-my-project`）。
   - 超长路径（>200 字符）截断并追加 hash 后缀以保证唯一性。

4. **子 agent 转录路径**：
   ```
   <sessionDir>/subagents/agent-<agentId>.jsonl   # 子 agent 消息流
   <sessionDir>/subagents/agent-<agentId>.meta.json  # 附带元数据：agentType, worktreePath, description
   ```

5. **每条消息都打上链条标记**：
   - `parentUuid` - 指向前一条消息，形成可遍历的单链表。
   - `sessionId` - 所属会话 ID。
   - `cwd` - 当时的当前工作目录。
   - `timestamp` - ISO 时间戳。
   - `version` - 写入时的协议版本。
   - `gitBranch` - 当前 git 分支名。

## 阶段2：持续写入

1. **追加只写** - 每条日志条目追加到 `.jsonl` 文件末尾，一行一条 JSON。文件从不重写（死 fork 分支留在磁盘上不做物理删除）。

2. **批量写入队列** - 使用 `writeQueue` Map 管理写入，默认 **100ms** 刷新周期（远程模式下 **10ms**），减少磁盘 I/O。
   - 使用 `appendFile` 写盘。
   - 遇到 ENOENT 自动 mkdir 并重试。

3. **支持的条目类型**（每条 JSONL 行的 `type` 字段）：
   | 类型 | 说明 |
   |------|------|
   | `user` | 用户输入消息 |
   | `assistant` | 模型回复（含 tool_use blocks） |
   | `system` | 系统消息、compact_boundary 等 |
   | `attachment` | 附件引用 |
   | `custom-title` | 自定义会话标题 |
   | `tag` | 会话标签 |
   | `agent-name` / `agent-color` / `agent-setting` | Agent 名称/颜色/配置 |
   | `mode` | coordinator / normal 模式标记 |
   | `worktree-state` | 是否在 worktree 中 |
   | `pr-link` | 关联的 PR 编号/URL/仓库 |
   | `file-history-snapshot` | 文件历史快照 |
   | `attribution-snapshot` | 代码归属快照 (ant-internal) |
   | `content-replacement` | 内容替换记录 |
   | `summary` | 压缩摘要 |
   | `compact_boundary` (system subtype) | 上下文压缩边界标记 |

4. **退出时重追加元数据** - 每次会话退出（包括 compact 后），以下字段被**重新追加到 EOF**：
   - `customTitle`, `tag`, `agentName`, `agentColor`, `agentSetting`, `mode`, `worktreeState`, `prLink`
   - 目的：让这些数据始终位于文件末尾 64KB 窗口内，lite 读取只需扫描尾块。

5. **parentUuid 链** - 每条 transcript message 都有 `parentUuid` 指向前驱。
   - 加载时从最新叶子沿链表回走到根，即可重建对话树。
   - Ctrl+Z 撤回产生的死分支永远留在 JSONL 中，但加载时被丢弃。

## 阶段3：列出可恢复会话（/resume 无参数）

这是用户输入 `/resume`（不带参数）时的完整流程：

### 3a. 获取 lite 会话文件列表

1. **`getSessionFilesLite(projectDir)`** — 扫描 `.general-agent/sessions/<sanitized_cwd>/` 下所有 `.jsonl` 文件。
2. 对每个文件 stat 获取 `mtime`（修改时间）和 `size`（文件大小），返回 `LogOption[]`。
3. 此步骤**不读取文件内容**，速度极快。

### 3b. 增强 lite 日志（提取元数据）

4. **`enrichLogs(allLogs, startIndex, count)`** — 对每个 lite log：
   - 调用 `readHeadAndTail(filePath, fileSize)` 读取文件**首尾各 64KB**。
   - 从 head 提取 `firstPrompt`（第一条有意义用户消息，跳过 tool_result / isMeta / isCompactSummary / slash command 等）。
   - 从 tail 提取最后的值：`customTitle`, `tag`, `gitBranch`, `isSidechain`, `projectPath`, `agentSetting`, `prNumber/Url/Repository`。
   - 提取使用字符串模式匹配（不解析完整 JSON），性能优先。
5. **过滤**：
   - 排除 `isSidechain === true` 的 sidechain 会话。
   - 排除当前正在使用的 sessionId（不要 resume 自己）。

### 3c. 排序与展示

6. 按 `modified`（最后修改时间）降序排列，最近使用的排在最前。
7. **`LogSelector` UI 渲染**（会话选择器组件）：
   - **可滚动列表** — 显示会话标题（customTitle 或 firstPrompt），辅助信息（日期、消息数、文件大小）。
   - **搜索框** — 实时过滤，支持 Fuse.js 模糊搜索（300ms 防抖）。深度搜索时读取会话消息内容匹配。
   - **分支过滤** — 可选仅显示当前 git 分支的会话。
   - **Tag 标签页** — 按 tag 过滤会话。
   - **树形视图** — fork 出的会话显示为可折叠分组。
   - **预览面板** — 高亮某个会话时显示消息内容预览。
   - **在线重命名** — 如果 `isCustomTitleEnabled()`，可内联编辑会话标题。
   - **跨项目切换** — 可选显示所有仓库的会话（而非仅当前项目）。
   - **加载中 / 空状态 / 错误处理**。

### 3d. 搜索增强

8. **`searchSessionsByCustomTitle(arg, { exact: true })`** — 精确标题匹配，用于 `/resume <title>`。
9. **`agenticSessionSearch(query, logs)`** — AI 驱动的语义搜索（可选功能）。

## 阶段4：完整加载会话内容（选中某个会话后）

当用户在 LogSelector 中选择了一个会话（或通过 UUID/标题直接指定），触发完整加载：

### 4a. 判断是否需要完整加载

1. **`isLiteLog(log)`** — 如果当前 LogOption 只有元数据没有 messages，调用 **`loadFullLog(log)`** 拉取完整内容。

### 4b. 大文件优化读取

2. 对文件大小 > **5MB**（`SKIP_PRECOMPACT_THRESHOLD`）的会话：
   - **`readTranscriptForLoad()`** — 单次正向分块读取（每块 1MB）。
   - 在 fd 层切除 **compact_boundary** 之前的旧内容（compact 前的内容被丢弃）。
   - 跳过 `attribution-snapshot` 行（在读取阶段即过滤，不入内存）。
   - 将**最后一个** attr-snap 重排到 EOF。
   - 峰值内存 = 输出大小，而非文件大小。

### 4c. 链式解析

3. **`walkChainBeforeParse()`** — 在 JSON.parse 之前：
   - 字节级索引所有消息行。
   - 从最新 `parentUuid` 叶子沿链回溯到根。
   - 只保留链上的行（丢弃 Ctrl+Z 撤回产生的死 fork 分支）。
   - 在 parse 之前削减数据量，减少 GC 压力。

### 4d. JSON 解析与分类

4. **`parseJSONL(buffer)`** — 解析过滤后的 buffer 为 `Entry[]`。
5. 将 Entry 分类到各个 Map 中：
   - `messages` — 按 uuid 索引。
   - `summaries` — 压缩摘要。
   - `customTitles` — 自定义标题。
   - `tags` — 标签。
   - `agentNames` / `agentColors` / `agentSettings` — Agent 配置。
   - `prNumbers` / `prUrls` / `prRepositories` — PR 信息。
   - `modes` — coordinator/normal 模式。
   - `worktreeStates` — worktree 状态。
   - `fileHistorySnapshots` — 文件历史。
   - `attributionSnapshots` — 代码归属。
   - `contentReplacements` — 内容替换。
   - `contextCollapseCommits` / `contextCollapseSnapshot` — 上下文折叠。

### 4e. post-compact 处理

6. **`applyPreservedSegmentRelinks()`** — 将 compact 后保留的消息（preserved segment）接回消息链。
7. **`applySnipRemovals()`** — 移除被裁剪的中间区间，跨间隙重连 parentUuid。

### 4f. 构建对话链

8. **Leaf UUID 计算** — 找到终端消息（无子节点的消息），沿 parentUuid 向后找到最近的 user/assistant 祖先。检测并处理循环引用。
9. **`buildConversationChain(messages, leafMessage)`** — 从叶子沿 parentUuid 回走到根，建立有序消息列表。
10. **`recoverOrphanedParallelToolResults()`** — 恢复兄弟 assistant 消息和并行 tool_results（同一轮对话中的并行工具调用）。

### 4g. 返回完整结果

11. 返回 **`ResumeLoadResult`**，包含：
    - `messages: Message[]` — 完整的有序对话历史。
    - `fileHistorySnapshots`, `attributionSnapshots`, `contentReplacements`
    - `contextCollapseCommits`, `contextCollapseSnapshot`
    - `sessionId`, `agentName`, `agentColor`, `agentSetting`
    - `customTitle`, `tag`, `mode`
    - `worktreeSession`, `prNumber`, `prUrl`, `prRepository`

## 阶段5：/resume 命令分发逻辑

`/resume` 命令根据参数分三种路径处理：

### 路径A：无参数 — 会话选择器

```
/resume
```
1. 显示 `LogSelector` UI。
2. 用户上下键选择，Enter 确认，Esc 取消。
3. 选择后进入阶段 6（跨项目检测 + 恢复）。

### 路径B：UUID 参数 — 直接查找

```
/resume <uuid>
```
1. 验证参数是否为合法 UUID 格式（`/^[0-9a-f]{8}-...$/i`）。
2. 在 enriched logs 中过滤匹配 sessionId 的会话。
3. 按修改时间降序排列，取第一个。
4. 找到 → `loadFullLog()` → 直接恢复（跳过选择器 UI）。
5. 未找到 → **回退查找**：`getLastSessionLog(uuid)` 直接从磁盘文件查找。
   - 这是为了处理被 `enrichLogs` 丢弃的会话（例如首条消息 >16KB 导致 firstPrompt 提取失败）。
   - 从 `.general-agent/sessions/*/` 下所有项目目录中搜索 `<uuid>.jsonl`。
6. 仍未找到 → 显示 `"Session <uuid> was not found."`。

### 路径C：标题参数 — 精确匹配

```
/resume <title>
```
1. 仅在 `isCustomTitleEnabled()` 为 true 时生效。
2. 调用 **`searchSessionsByCustomTitle(arg, { exact: true })`** — 精确（区分大小写）标题匹配。
3. **1 个匹配** → 直接 `loadFullLog()` → 恢复。
4. **多个匹配** → 显示错误：`"Found N sessions matching X. Please use /resume to pick a specific session."`
5. **0 个匹配** → 显示错误：`"Session X was not found."`（此时 `isCustomTitleEnabled()` 为 false 也算 0 匹配）。

## 阶段6：跨项目检测

在选择会话后、执行恢复前，进行跨项目检测：

1. **`checkCrossProjectResume(fullLog, showAllProjects, worktreePaths)`**：
   - 比较会话记录的 cwd 与当前 cwd。
   - 考虑所有 worktree 路径。

2. **同项目** → 直接恢复（正常路径）。

3. **同仓库不同 worktree** → 直接恢复（cd 到 worktree 路径即可）。

4. **完全不同的项目** → **不恢复！** 而是：
   - 生成等效的 CLI 命令（如 `general-agent --resume <sessionId> --cwd <path>`）。
   - 复制到剪贴板（`setClipboard`）。
   - 显示消息：
     ```
     This conversation is from a different directory.

     To resume, run:
       <command>

     (Command copied to clipboard)
     ```
   - 用户需要在对应目录手动执行。

## 阶段7：执行会话恢复

当确定可以恢复后，调用 **`context.resume(sessionId, fullLog, entrypoint)`**，触发以下流程：

### 7a. 会话 ID 处理

1. 决定是否 fork：
   - `--fork-session` 标志 → 保持当前新 UUID（但复制消息内容到新文件）。
   - 否则 → **`switchSession(resumedId)`** 切换到恢复的会话 ID。
2. 重命名 asciicast 录制文件以匹配新的 sessionId。

### 7b. Worktree 恢复

3. **`restoreWorktreeForResume(worktreeSession)`**：
   - 如果会话上次在 worktree 中退出，`process.chdir()` 回到 worktree 目录。
   - 如果 `--worktree` 创建了新的 worktree，则优先使用新 worktree。
   - 如果目录已被删除（`/exit` 或手动删除），清除 worktree 缓存。

### 7c. 元数据恢复

4. **`restoreSessionMetadata(result)`** — 将会话的 title、tag、agent、mode、worktree、prLink 写入内存缓存。
5. **`adoptResumedSessionFile()`** — 将 `Project.sessionFile` 指向恢复的 JSONL 文件路径。
6. 退出时能正确 `reAppendSessionMetadata()` 到 EOF。

### 7d. Agent 恢复

7. **`restoreAgentFromSession(agentSetting)`**：
   - 如果用户传了 `--agent` CLI 参数 → 保持用户指定。
   - 如果会话有 agentSetting → 恢复对应 agent 定义 + model override。
   - 如果 agent 不再可用 → 回退到默认行为。

### 7e. 状态恢复

8. **`restoreSessionStateFromLog(result)`**：
   - 恢复 file history 快照（文件级别历史追踪）。
   - 恢复 attribution 快照（代码归属信息）。
   - 恢复 context-collapse 提交日志。
   - 恢复 TodoWrite 待办列表（从转录中提取最后的 TodoWrite tool_use）。

### 7f. 重建 TUI

9. **重建 transcript** — 从恢复的 `Message[]` 重新渲染完整的对话历史：
   - 用户消息 → `{ type: 'user' }` transcript item。
   - 助手消息 → `{ type: 'assistant' }` transcript item。
   - 工具调用 → `{ type: 'tool_summary' }` 带状态（成功/失败/待审批）。
   - 错误消息 → `{ type: 'error' }`。
   - 每一轮对话之间加上分隔线 `{ type: 'separator' }`。

10. **TUI 状态**：
    - 输入框回到 prompt 模式，placeholder 正常显示。
    - Footer 更新为恢复后的 session 信息。
    - 后台任务列表恢复。
    - 权限偏好恢复。

### 7g. 继续对话

11. 用户输入新消息 → 作为普通 `TurnRequest` 追加到恢复后的 `AgentState`。
12. 新消息沿 parentUuid 链正确拼接到恢复后的消息列表末尾。
13. 所有新消息正常写入同一个 JSONL 文件。

## 阶段8：--resume / --continue CLI 启动参数

除 `/resume` slash command 外，还支持 CLI 参数直接恢复：

### --continue
```
general-agent --continue
```
1. 自动找到当前项目最近使用的会话。
2. 执行完整加载和恢复流程（同上阶段 4-7）。
3. 不显示会话选择器。

### --resume <sessionId>
```
general-agent --resume <uuid>
```
1. 按 UUID 查找会话（同阶段 5 路径 B）。
2. 执行完整加载和恢复流程。
3. 不进入 TUI 选择器。
4. 如果指定 `--fork-session`，创建新 UUID 但复制原会话消息。

## v1 实现范围

v1 必须先完成以下核心功能，体验保持一致：

1. ✅ JSONL 追加写存储。
2. ✅ `/resume`（无参数）显示会话列表选择器。
3. ✅ `/resume <uuid>` 按 UUID 直接恢复。
4. ✅ `/resume <title>` 按标题精确匹配恢复（如启用）。
5. ✅ `--continue` / `--resume` CLI 参数。
6. ✅ 恢复完整 messages + 重建 TUI transcript。
7. ✅ 过滤 sidechain + 当前 session。
8. ✅ lite 元数据读取（首尾 64KB 扫描）。
9. ✅ 会话标题使用第一条用户消息（`firstPrompt`）。

### v2 后续迭代

以下功能暂缓，在 v2 实现：

- ❌ fork session（Ctrl+Z 撤回后的死分支恢复）。
- ❌ 跨项目检测（复制命令到剪贴板，暂不支持跨目录恢复）。
- ❌ TreeSelect 树形视图（fork 分支分组显示）。
- ❌ 深度搜索（Fuse.js 模糊匹配会话内容）。
- ❌ 内联重命名（`isCustomTitleEnabled`）。
- ❌ Tag 标签过滤。
- ❌ 分支过滤。
- ❌ AI 语义搜索。
- ❌ compact_boundary 处理（上下文压缩边界）。
- ❌ worktree session 恢复。
- ❌ agent/coordinator mode 恢复。
- ❌ context-collapse 恢复。
- ❌ file history / attribution / todo 状态恢复。
