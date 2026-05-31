# 会话持久化流程

> 历史对话保存到本地文件系统，支持跨会话恢复。JSONL 格式，按项目目录组织，parentUuid 链式连接。

参考：cc-haha `src/utils/sessionStorage.ts`、`src/utils/listSessionsImpl.ts`、`src/utils/sessionStoragePortable.ts`

---

## 阶段1：存储路径解析

1. **计算项目目录** — 将当前工作目录 (cwd) 规范化（绝对路径、symlink 解析）后 sanitize，生成项目目录标识
2. **拼接完整路径** — `~/.general_agent/projects/<sanitized-cwd>/<session-id>.jsonl`
3. **按需创建目录** — 首次写入时 `mkdir -p`，权限 `0o700`

参考 CC 的 `getProjectsDir()` + `getProjectDir()` + `sanitizePath()`。

---

## 阶段2：消息写入

1. **构建 TranscriptMessage** — 每条消息附加元信息：`uuid`、`parentUuid`、`sessionId`、`timestamp`、`cwd`、`version`、`gitBranch`
2. **即时写入 JSONL** — 每条消息调用 `enqueue()` 后立即 `_write_immediate()` 落盘（v1 不做缓冲，CLI 每轮只处理一次对话，缓冲无性能收益）
3. **parentUuid 链** — 先保存用户消息，获得 UUID；保存助手消息时传入该 UUID 作为 `parent_uuid`，建立链式关联
4. **会话元数据** — 会话退出时通过 `atexit` 钩子重新追加 `custom-title`、`tag`、`last-prompt` 等元数据条目到文件末尾（保证在 tail 扫描窗口内）

## 阶段3：会话发现（列表）

1. **扫描项目目录** — 列出 `~/.general_agent/projects/` 下所有子目录
2. **候选文件过滤** — 仅保留 `*.jsonl` 且文件名为合法 UUID 的条目
3. **快速排序** — 通过 `stat` 获取 `mtime`，按最近修改时间倒序
4. **提取元数据** — 仅读取文件头/尾各 64KB（`LITE_READ_BUF_SIZE`），不解析完整文件
5. **解析关键字段** — 从头部提取 `timestamp`、`cwd`、`gitBranch`、`firstPrompt`；从尾部提取 `customTitle`、`tag`、`lastPrompt`
6. **跳过无效会话** — 过滤掉 sidechain 会话（`isSidechain: true`）、无摘要的会话

参考 CC 的 `listSessionsImpl()` + `parseSessionInfoFromLite()` + `listCandidates()`。

## 阶段4：会话恢复

1. **加载 JSONL 文件** — 逐行解析所有条目，构建 `Map[uuid, TranscriptMessage]`
2. **构建 parentUuid 索引** — 建立 uuid → message 的完整映射
3. **处理压缩边界** — 跳过 compact_boundary 之前的已压缩消息
4. **处理 snip 移除** — 删除被标记为 removed 的 UUID，relink 断开的 parentUuid 链
5. **找到叶子节点** — 选择最新（最大 timestamp）且无子节点的 message 作为起点
6. **反向遍历构建链** — 从叶子节点沿 parentUuid 走到根，再反转得到时间正序的消息列表
7. **恢复并行 tool_result** — 恢复因单链遍历丢失的同组并行 tool_use 的 sibling 消息

参考 CC 的 `loadTranscriptFile()` + `buildConversationChain()` + `loadConversationForResume()`。

## 阶段5：会话退出时的善后

1. **atexit 钩子** — 注册 `atexit.register(_flush_session_store_sync)`，即使 `SystemExit` 退出也会执行
2. **重新追加元数据** — 将 `custom-title`、`tag`、`last-prompt` 等重新写到文件末尾（`re_append_metadata()`）
3. **异步清理** — MCP shutdown 等异步清理仍走 `register_cleanup`

参考 CC 的 `cleanup` handler + `reAppendSessionMetadata()`。

---

## v1 简化流程

1. 消息写入：每条消息即时 `enqueue()` → `_write_immediate()` 追加到 JSONL
2. 会话发现：扫描项目目录，按 mtime 排序，头尾读取提取元数据
3. 会话恢复：解析 JSONL，构建 parentUuid 链重建消息序列；链不完整时 fallback 到时间戳排序
4. `/resume` 命令：列出当前项目的历史会话（最多 10 条），用户选择后恢复对话状态
5. `atexit` 退出善后：追加会话元数据到文件末尾
6. 跳过远程持久化（remote ingress / CCR v2）

## 差异说明

| 功能 | v1 状态 | 原因 |
|------|---------|------|
| 远程持久化 (session ingress) | 跳过 | v1 无 CCR 服务器 |
| CCR v2 内部事件 | 跳过 | 同上 |
| Agent sidechain 会话 | 跳过 | 多 Agent 系统已有独立存储 |
| content-replacement 条目 | 跳过 | v1 无此机制 |
| file-history-snapshot 条目 | 跳过 | v1 无快照功能 |
| marble-origami commit/snapshot | 跳过 | v1 无此压缩模式 |
| worktree 感知 | 跳过 | Windows 平台 worktree 实现不完整 |
| `isSessionPersistenceDisabled` | 实现 | 支持 `--no-session-persistence` / 环境变量关闭 |
| `/resume` slash 命令 | 实现 | 交互式会话列表与恢复 |
| `atexit` 退出善后 | 实现 | 比异步 cleanup 更可靠（SystemExit 也会触发） |
| 元数据重追加 | 实现 | 保证 tail 扫描窗口可读 |
| parentUuid 链 fallback | 实现 | 旧文件链不完整时按时间戳排序加载 |

---

> 最后更新: 2026-05-31 | 参考源 commit: 94b86ea | 参考文件: cc-haha src/utils/sessionStorage.ts, listSessionsImpl.ts, sessionStoragePortable.ts
