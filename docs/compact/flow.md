# 流程

> 上下文压缩（Compact）的完整流程。从触发条件、摘要生成到会话恢复。

---

## 概览

当对话历史接近模型上下文窗口限制时，Compact 系统自动将历史压缩为结构化摘要，然后将新的对话接续到摘要后面。v1 实现基础自动压缩，跳过 snip、reactive、context collapse 等高级特性。

---

## 压缩类型总览

| 类型 | 触发 | 方式 | v1 |
|---|---|---|---|
| **Auto-Compact** | Token 超过阈值，每轮主循环检查 | 调用模型生成摘要 | 实现 |
| **Manual Compact** | 用户 `/compact` 命令 | 可传入自定义指令 | 实现 |
| **Microcompact** | 时间触发（空闲 >60 分钟）或增量 token 触发 | 清除旧的 tool_result 内容 | 实现 |
| **Session Memory Compact** | 优先于传统 compact | 利用 Session Memory 恢复 [v1置空] | 不实现 |
| **Snip Compact** | Token 压力下裁剪旧轮次 [v1置空] | 删除消息但不重置状态 | 不实现 |
| **Reactive Compact** | API 返回 413 错误 [v1置空] | 剥离媒体后重试 | 不实现 |
| **Context Collapse** | 按需 [v1置空] | 用投影视图替换历史 | 不实现 |
| **Cached Microcompact** | 缓存编辑 API [v1置空] | 使用 API 缓存控制 | 不实现 |

---

## 阶段1：Auto-Compact 触发

### 阈值计算

```
effectiveWindow = MIN(contextWindowForModel, CLAUDE_CODE_AUTO_COMPACT_WINDOW) - 20,000
autoCompactThreshold = effectiveWindow - 13,000
```

对于 200K 模型：
```
effectiveWin = 200,000 - 20,000 = 180,000
autoCompactThreshold = 180,000 - 13,000 = 167,000
```

### 触发流程

主循环在每次 API 调用前检查（`query.ts` 中的优先级顺序）：

1. 工具结果内容裁剪
2. Snip（移除旧消息，不重置状态）`[v1置空]`
3. **MICROCOMPACT**（清除旧工具结果）
4. Context Collapse 投影 `[v1置空]`
5. **AUTOCOMPACT 检查**（见下方）
6. 正常 API 调用

### `shouldAutoCompact()` 检查

- 跳过分叉 Agent（`compact` 和 `session_memory` 查询源）
- 跳过 Context Collapse Agent
- 跳过仅响应模式
- `isAutoCompactEnabled()` 返回 true
- Token 数量 >= 阈值

### 断路器

防止无限压缩循环：
- 最多 3 次连续压缩失败
- 失败通知被抑制（自动重试）

### 尝试顺序

1. `trySessionMemoryCompaction()` `[v1置空]` — 先尝试更廉价的会话记忆压缩
2. 如果失败，回退到 `compactConversation()` with `isAutoCompact=true`

---

## 阶段2：压缩执行

### `compactConversation()` 流程

1. **执行 PreCompact hooks**
2. **投影消息**：只使用 `getMessagesAfterCompactBoundary()` 之后的非 snip 消息
3. **构建提示词**：
   - `getCompactPrompt` — 完整压缩
   - `getPartialCompactPrompt('from')` — 总结枢轴之后的消息
   - `getPartialCompactPrompt('up_to')` — 总结枢轴之前的消息
4. **调用模型** — 通过分叉 Agent（与主循环相同的缓存前缀）
5. **处理 Prompt-Too-Long 重试** — 截断最旧轮次
6. **生成摘要 + 附件**：
   - `CompactionResult.boundaryMarker` — 系统压缩边界标记
   - `CompactionResult.summaryMessages` — 摘要注入为用户消息
   - `CompactionResult.attachments` — 压缩后文件/计划/Skill 附件
7. **执行 SessionStart hooks**（重新注入到压缩后上下文）
8. **执行 PostCompact hooks**
9. **运行 `postCompactCleanup()`** — 清除缓存状态

### 摘要提示词结构

三层结构：

**Layer 1 — NO_TOOLS_PREAMBLE**（强烈禁止工具调用）：
```
CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.
```

**Layer 2 — 9 节摘要结构**：
1. **Primary Request and Intent** — 用户的明确要求
2. **Key Technical Concepts** — 引用的技术和框架
3. **Files and Code Sections** — 具体文件、代码片段及其重要性
4. **Errors and fixes** — 遇到的错误和修复方式
5. **Problem Solving** — 已解决和进行中的问题
6. **All user messages** — 所有非工具结果的用户消息
7. **Pending Tasks** — 明确要完成的任务
8. **Current Work** — 当前正在做什么
9. **Optional Next Step** — 下一步建议，附原文引用

**Layer 3 — NO_TOOLS_TRAILER**（再次提醒）：
```
REMINDER: Do NOT call any tools. Respond with plain text only.
```

### 后处理

`formatCompactSummary()` 剥离 `<analysis>` 块（仅作为草稿辅助），用 "Summary:" 标题替换 `<summary>` XML。

---

## 阶段3：摘要包装和注入

### 用户消息包装

自动压缩后，摘要被包装为：

```
This session is being continued from a previous conversation
that ran out of context. The summary below covers the earlier
portion of the conversation.

{formattedSummary}

If you need specific details from before compaction,
read the full transcript at: {path}
```

当 `suppressFollowUpQuestions=true`（自动压缩）时追加：
```
Continue the conversation from where it left off without
asking the user any further questions. Resume directly.
```

### 边界标记

```
SystemCompactBoundaryMessage:
  role: 'system'
  subtype: 'compact_boundary'
  compactMetadata:
    trigger: str                 # 触发原因
    preTokens: int               # 压缩前 Token 数
    userContext: str             # 用户上下文
    messagesSummarized: int      # 被压缩的消息数
```

---

## 阶段4：Microcompact（增量清理）

在每次 API 调用前对旧工具结果进行增量清理：

1. **时间触发**：空闲 > 60 分钟 → 清除最后 N 个工具之外的所有内容
2. **Token 触发**：超出阈值时增量清除工具结果
3. **缓存编辑触发** `[v1置空]`：使用 API 缓存控制指令清理 KV 缓存

---

## 阶段5：Session Memory Compact `[v1置空]`

优先于传统压缩的廉价替代方案：

1. 阈值：消息 >= 10,000 Token 且 >= 5 条文本块消息
2. 使用现有 Session Memory 作为恢复上下文
3. 如果可能则避免完整的压缩循环
4. 仅在不处于自定义指令模式时使用

---

## 阶段6：Post-Compact 清理

每次成功压缩后：

- 重置 Microcompact 状态
- 重置 Context Collapse 状态
- 清除用户上下文缓存
- 清除记忆文件缓存
- 清除系统提示词节缓存
- 清除分类器批准

---

## 阶段7：Manual Compact（/compact 命令）

与自动压缩不同：
- 错误显示给用户
- `suppressFollowUpQuestions=false`：摘要不强制继续
- 可以传入自定义指令
- 也链式尝试微压缩 → 会话记忆压缩 → 完整压缩

---

## v1 实际实现

完整还原 cc-haha compact 系统：

1. **Token 计数** — `estimate_tokens()` ~4chars/token
2. **Microcompact** — 清除旧工具结果（保留最近 5 条）
3. **Snip Compact** — 8000 token 时裁剪旧轮次
4. **Auto-Compact** — fork agent 生成 9 节摘要
5. **Reactive Compact** — 413 错误时 snip + 重试
6. **Manual `/compact`** — 随时手动压缩
7. **摘要包装** — boundaryMarker + summaryMessages

存根（API 特定）：Context Collapse、Cached MC、Session Memory Compact

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/services/compact/compact.ts, autoCompact.ts, prompt.ts, microCompact.ts
