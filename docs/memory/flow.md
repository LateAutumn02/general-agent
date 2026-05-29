# 流程

> 记忆系统的完整生命周期流程。从启动加载、运行时检索、对话结束提取，到夜间整理。

---

## 记忆系统概览

Claude Code 有四个记忆子系统，general-agent v1 仅实现其中最核心的 **memdir（文件持久化记忆）**：

| 子系统 | 用途 | 时机 | v1 |
|---|---|---|---|
| **memdir** | 文件持久化长期记忆，MEMORY.md 索引 + 独立 .md 文件 | 启动加载 | 实现 |
| **Session Memory** | 每会话的结构化工作笔记 | 对话中 post-sampling hook | 不实现（用 Memory 覆盖） |
| **extractMemories** | 自动从对话提取长期记忆写入磁盘 | 每轮对话结束 stop hook | 不实现（改手动触发） |
| **autoDream** | 跨会话记忆整合与修剪 | 定期（24h + 5 会话） | 不实现（无多会话场景） |

---

## 启动时：加载记忆

1. **检查开关** — 优先级链：`CLAUDE_CODE_DISABLE_AUTO_MEMORY` 环境变量 > Simple 模式 > 远程模式 > settings.json `autoMemoryEnabled` > 默认 `true`
2. **解析路径** — 确定记忆存储目录：
   - 优先级：`CLAUDE_COWORK_MEMORY_PATH_OVERRIDE` 环境变量 > settings `autoMemoryDirectory`（仅信任 user/policy/local/flag 来源，不信任 projectSettings）> 默认 `~/.claude/projects/<sanitized-git-root>/memory/`
3. **读取 MEMORY.md** — 如果存在，读取索引文件，截断到 200 行 / 25KB
4. **注入系统提示词** — 将 MEMORY.md 内容注入系统提示词，AI 通过索引看到所有记忆概况
5. **注入行为指令** — 注入记忆使用说明（如何保存、何时读取、不被信任的回忆需验证）
6. **注入类型说明** — 注入四类记忆的定义和示例（user / feedback / project / reference）
7. **注入排除规则** — 注入不应保存的内容（代码模式、Git 历史、CLAUDE.md 已有内容、临时任务细节）

## 运行时：按需检索 `[v1置空]`

Claude Code 在每轮对话时用轻量模型检索相关记忆，流程如下：

1. **扫描记忆清单** — `scanMemoryFiles()` 扫描所有 .md 文件（排除 MEMORY.md），读取 frontmatter 中 `description` 和 `type`，生成 `[{type, filename, mtime, description}]` 列表（最多 200 条）
2. **过滤已展示** — 排除前几轮已经检索过的文件，避免重复
3. **侧查询选择** — 用 Sonnet `sideQuery()` + `json_schema` 输出，从清单中选出最多 5 条最相关的记忆
4. **注入上下文** — 将被选中记忆文件的**完整内容**注入对话
5. **时效警告** — 超过 1 天的记忆包裹 `<system-reminder>` 警告："N days old. Verify against current code before asserting as fact."

> v1 跳过按需检索，启动时全量加载 MEMORY.md 索引即可。后续版本可加入此流程。

## 对话结束时：提取新记忆

Claude Code 在每个查询轮次结束后，通过 stop hook 自动触发的完整流程：

1. **触发判断** — 检查前提条件：
   - 仅主 Agent（非子 Agent），`tengu_passport_quail` 开关开启，`isAutoMemoryEnabled()`，非远程模式
   - 节流：每 N 轮触发一次（默认每轮，`tengu_bramble_lintel`）
2. **合并队列** — 如果上一次提取还在进行中，暂存上下文到 `pendingContext`，完成后执行一次尾随提取
3. **跳过检查** — `hasMemoryWritesSince()`：如果主 Agent 在本轮已经直接写入过记忆文件，跳过提取，推进游标
4. **扫描现有记忆** — `scanMemoryFiles()` 从主线程获取现有记忆清单（避免分叉 Agent 浪费时间做 `ls`）
5. **构建提取提示词** — 分为 auto-only 和 combined（含 team）两种模式：
   - **Opener 头**：告知分析最近 N 条消息，列出可用工具，建议 2-turn 策略（第 1 轮并行读取，第 2 轮并行写入），注入现有记忆清单
   - **类型说明**：注入四类记忆的定义
   - **排除规则**：注入不应保存的内容
6. **运行分叉 Agent** — `runForkedAgent()`：
   - 限制 5 轮，`skipTranscript`（不写转录日志）
   - 工具白名单：Read/Grep/Glob（读任意文件），Bash（仅只读命令），Edit/Write（仅限记忆目录路径）
   - Agent 独立运行，读取现有记忆文件，决定新增/更新/不操作
7. **后处理**：
   - 推进游标 `lastMemoryMessageUuid`（标记已处理的最后一条消息）
   - 提取写入的文件路径
   - 生成系统消息告知用户保存了哪些记忆
8. **尾随提取** — 如果执行期间有新的提取请求进入 `pendingContext`，再跑一次（确保不丢失）

## 夜间整理：AutoDream `[v1置空]`

定期的跨会话记忆整合，三个关卡，从最便宜的检查起：

1. **时间关卡** — 距上一次整理 >= 24 小时（通过 `.consolidate-lock` 的 mtime 判断）
2. **会话关卡** — 自上次整理以来 >= 5 个新会话转录文件
3. **锁关卡** — `tryAcquireConsolidationLock()` 写入当前 PID 到锁文件，处理死锁（检测 1 小时内失效的 PID）

扫描节流：时间关卡通过但会话关卡未通过时，10 分钟内不再重复扫描会话文件。

**执行流程：**
1. 注册 `DreamTask` 显示在 UI 状态栏
2. 构建 4 阶段整理提示词：
   - **Phase 1 Orient** — `ls` 记忆目录，读 MEMORY.md，浏览主题文件
   - **Phase 2 Gather** — 浏览日志，检查过期记忆，用 grep 搜索会话转录
   - **Phase 3 Consolidate** — 合并新信息到主题文件，转换相对日期为绝对，删除被推翻的旧结论
   - **Phase 4 Prune** — 保持 MEMORY.md 在 200 行 / 25KB 内，移除过期指针
3. 运行分叉 Agent（工具白名单同上）
4. 完成时标记任务完成，失败时回滚锁文件 mtime

---

## 记忆文件格式

每个记忆文件使用 YAML frontmatter + Markdown 正文：

```yaml
---
name: 记忆名称
description: 一句话描述（用于索引和检索）
type: user              # user / feedback / project / reference
---
记忆正文内容
```

**四种类型：**

| 类型 | 含义 | 举例 |
|---|---|---|
| `user` | 用户角色、偏好、技术栈、知识 | "用户是全栈开发者，偏好 React + TypeScript" |
| `feedback` | 行为反馈、修正和确认 | "用户不喜欢过度注释，偏好简洁代码" |
| `project` | 项目状态、截止日期、决策背景 | "API v2 需在 6 月前完成" |
| `reference` | 外部系统引用 | "用户偏好用 xx 文档平台" |

**MEMORY.md 索引格式：**

```markdown
- [用户角色与偏好](user_role.md) — 用户是全栈开发者，偏好 React + TypeScript
- [项目截止日期](project_state.md) — API v2 需在 6 月前完成
```

限制：最多 200 行，最多 25KB。超出截断并追加警告。

**不应保存的内容：**
- 代码模式、语法选择、框架用法细节
- Git 历史、commit 信息
- 调试过程、临时修复
- 已在 CLAUDE.md 中描述的内容
- 临时/一次性任务细节

---

## 记忆系统安全

- **路径验证**：team memory 写入前做全符号链接感知的包含性检查（resolve + realpath 双重验证）
- **Key 消毒**：`validateTeamMemKey()` 过滤 null 字节、URL 编码遍历、Unicode 规范化、反斜杠注入
- **设置来源**：`autoMemoryDirectory` 仅信任 user/policy/local/flag 来源，不信任 `projectSettings`（防止恶意仓库重定向记忆写入）
- **分叉 Agent 权限**：`createAutoMemCanUseTool()` 限制 Edit/Write 仅在记忆目录内

---

## v1 简化流程

general-agent v1 对记忆系统做了最大程度的简化，仅保留最核心的文件级持久化：

1. **启动时** — 读取 `<project>/.claude/memory/` 下所有 .md 文件，全量注入系统提示词
2. **手动提取** — 用户通过 `/memory save` 命令主动触发，AI 直接调用 Write/Edit 工具操作记忆文件
3. **不做** — 按需检索、自动提取（stop hook）、夜间整理（AutoDream）、Session Memory、team memory

## v1 实际实现 (Phase 4)

完整还原 cc-haha memdir 记忆系统：

- **YAML frontmatter** — name/description/type 三字段
- **四类型** — user / feedback / project / reference
- **MEMORY.md 索引** — 写/删时自动重建，200行/25KB 截断
- **行为指令注入** — 何时存取、四类型说明、排除规则、信任但验证
- **时效警告** — 超过1天记忆包裹 `<system-reminder>`
- **自动提取** — run_agent() 结束后注入提示词，agent 自行判断保存
- **按需检索** — API 侧查询选 5 条最相关记忆
- **Session Memory** — 每次会话自动保存笔记（9 节模板）
- **AutoDream** — 启动时检查 24h + ≥3 条记忆，提示整理
- **/memory** 命令 — `list` / `refresh`

不做：分叉Agent提取（依赖 multi-agent，留空写入文档）

---

## 与 Claude Code 源项目的差异说明

| 功能 | Claude Code | general-agent v1 | 原因 |
|---|---|---|---|
| 按需检索 | Sonnet 侧查询，选最多 5 条 | 全量加载 MEMORY.md | 简化实现，v1 记忆文件不多 |
| 自动提取 | stop hook + 分叉 Agent | 用户手动 `/memory save` | 分叉 Agent 实现复杂 |
| AutoDream | 定期整合 + 修剪 | 不做 | v1 无多会话场景 |
| Session Memory | post-sampling hook | 不做 | 用长期记忆覆盖 |
| Team Memory | 团队共享记忆 | 不做 | v1 单用户 |
| 安全验证 | 全符号链接感知 | 基本路径校验 | 攻击面有限 |

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/memdir/, src/services/SessionMemory/, src/services/extractMemories/, src/services/autoDream/
