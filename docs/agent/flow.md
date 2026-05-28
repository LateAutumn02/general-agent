# 流程

> 描述 general-agent 核心对话循环的逻辑流程。一次用户输入触发一个对话回合，回合内是 while(true) 循环：每轮调 API → 有工具就执行后继续 → 无工具就收尾退出。

---

## 阶段0：会话初始化（对话回合开始，一轮一次）

1. **构建系统提示词** — 聚合默认系统提示 + 工具描述 + 用户 CLAUDE.md + 记忆文件
2. **处理用户输入** — 解析斜杠命令、附件文件、@引用
3. **加载历史消息** — 恢复上次会话的上下文（如果有）

## 阶段1：预处理（每轮迭代开始，共 13 个子步骤）

以下按源码中的实际执行顺序排列。标注 `[v1置空]` 的步骤 general-agent v1 暂不实现，原因见末尾差异说明。

1. **Skill 发现预取** — 异步启动 skill 文件发现，与模型流式和工具调用并发执行
2. **消息裁剪** — 截取上一次 compact 边界之后的消息作为本轮 API 输入
3. **工具结果预算裁剪** `[v1置空]` — 对超出大小上限的 tool_result 内容进行截断，限制上下文膨胀
4. **历史 Snip 裁剪** `[v1置空]` — 在 token 压力下裁剪旧轮次的对话历史（snipCompactIfNeeded）
5. **微压缩** `[v1置空]` — 删除无用的 tool_use/tool_result 对，缩减上下文
6. **上下文折叠** `[v1置空]` — 将已归档消息投影为摘要视图（context collapse）
7. **自动压缩** — 如果 token 超过阈值，通过侧查询生成摘要来压缩上下文
   - v1 仅做简单的 token 计数 + 历史消息头尾截断
8. **Token 硬阻塞检查** — 如果已经远超限制且无恢复路径，直接拒绝并提示 /compact
9. **记忆预取** `[v1置空]` — 异步启动相关记忆检索（general-agent v1 用 MEMORY.md 全量注入，不做按需检索）
10. **同步 autoCompact 追踪状态** — 更新压缩追踪计数
11. **组装完整系统提示词** — 将 systemPrompt 与 systemContext 合并为 API 使用的最终格式
12. **选择模型** — 根据权限模式和上下文大小选择主循环模型
13. **初始化流式工具执行器** — 如果启用，创建 StreamingToolExecutor

## 阶段2：API 调用

1. **构建请求** — 拼装 system prompt + 历史消息 + 工具定义
2. **流式发送** — 向 Anthropic API 发起流式请求
3. **接收响应** — 处理三种流式事件：
   - text_delta：追加到 AI 回复文本
   - tool_use：记录工具调用块
   - tool_result：注入之前的工具结果
4. **记录停止原因** — end_turn / max_tokens / tool_use

## 阶段3：判断是否继续

流式响应结束后，根据是否有 tool_use 块决定分支：
- **有 tool_use 块** → 阶段4（执行工具），然后 continue 回到阶段1
- **无 tool_use 块** → 阶段5（收尾），检查是否需要自愈重试，否则退出循环

## 阶段4：工具执行

1. **校验参数** — 用 schema 校验每个工具调用的输入参数
2. **权限检查** — 依次检查：拒绝规则匹配 → 询问规则匹配 → 工具自身 checkPermissions
3. **执行工具** — 调用工具的 call() 方法
4. **收集结果** — 将工具输出格式化为 tool_result
5. **注入附件** — 文件变更通知、Hook 注入、记忆更新、Skill 发现
6. **刷新工具列表** — 如果有新的 MCP 连接加入，刷新可用工具
7. **更新轮次计数** — turns++
8. **continue** — 回到阶段1（下一轮 API 调用）

## 阶段5：收尾（无工具调用）

1. **错误恢复检查**：
   - prompt-too-long（413）：先尝试 collapse drain → 再尝试 reactive compact → 否则报错
   - max_output_tokens：升级 token 上限后重试（最多 3 次）
   - media-size 错误：通过 reactive compact 剥离媒体后重试
2. **模型 fallback** — 如果主模型返回 overload 错误，自动切换到备用模型重试
3. **Stop Hook 检查** — 执行注册的 stop hook，可能触发额外处理
4. **费用追踪** — 记录本轮 API 调用消耗的 token 和费用
5. **Token 预算检查** — 检查 task_budget 剩余是否足够继续，不足则注入提醒
6. **生成工具调用摘要** — 异步生成本轮工具调用摘要（供下一轮 yield）
7. **返回** — 退出 while(true) 循环，返回对话结果

---

## 与 Claude Code 源项目的差异说明

general-agent v1 对主循环做了以下简化，以下步骤在 v1 中跳过或不完整实现：

- **工具结果预算裁剪** — 置空（v1 不会遇到极大的 tool_result，先不做）
- **历史 Snip 裁剪** — 置空（snip 是实验性功能，v1 暂不需要）
- **微压缩** — 置空（需要分析完整对话历史判断冗余，实现复杂）
- **上下文折叠** — 置空（高级特性，v1 用简单的头尾截断替代）
- **记忆预取（按需检索）** — 用全量注入替代（v1 直接将 MEMORY.md 完整注入系统提示词）
- **流式工具执行** — 置空（先实现顺序执行：调 API → 拿结果 → 执行工具 → 下一轮）
- **自愈机制（max_tokens resume）** — 置空（直接报错让用户处理，不做自动 resume）
- **自愈机制（media-size 恢复）** — 置空（v1 不做图片/PDF 处理）
- **collapse_drain_retry** — 置空（依赖 context collapse）
- **reactive_compact** — 置空（依赖响应式压缩子系统）
- **Token 预算（task_budget）** — 置空（v1 不做 token 预算限制）

> 以上简化目的是降低 v1 实现复杂度。后续版本可按需逐步加入。

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/query.ts:307-1730, src/QueryEngine.ts
