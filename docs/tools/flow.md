# 流程

> 工具系统的执行流程。从工具注册、API 触发调用、参数校验、权限检查、执行、到结果返回。

---

## 启动时：工具注册

工具注册分四步：构建工具对象 → 按环境条件拼装 → 按权限规则过滤 → 合并 MCP 工具。

### 1. 构建工具对象（buildTool）

每个工具文件只定义核心逻辑（call、inputSchema），其他方法（isEnabled、isConcurrencySafe、checkPermissions 等）由 buildTool() 自动填充默认值。目的：50+ 个工具共享一套默认行为，消除重复样板代码。只有需要特殊行为的工具（如 Bash 需要真正的权限检查）才覆盖默认值。

### 2. 按环境条件拼装（getAllBaseTools）

不是简单列出所有工具，而是根据环境变量和功能开关决定哪些工具被包含。例如：USER_TYPE === ant 才有 ConfigTool 和 REPLTool，isTodoV2Enabled() 才加载新版任务工具。不同环境下拼出的列表不一样，外部用户比 Ant 内部少很多工具。

### 3. 按权限规则过滤（getTools）

在上一步基础上做运行时过滤：filterToolsByDenyRules 剔除被 deny 禁止的工具（如用户设 deny: WebFetch，AI 就看不到它），CLAUDE_CODE_SIMPLE 模式只保留 Bash+Read+Edit，isEnabled() 排除自身不可用的工具。

与环境过滤的区别：环境过滤是代码层面决定工具存不存在（用户改不了），权限过滤是运行时根据用户配置决定工具可不可用（用户随时能改）。

### 4. 合并 MCP 工具（assembleToolPool）

内置工具在前、MCP 在后，各自排序，同名冲突内置优先。排序保证 prompt cache 稳定——API 在最后一个内置工具处设缓存断点，MCP 工具随便变不影响缓存。

### 5. 注入系统提示词

将所有工具的定义（name + description + input_schema）写入 system prompt，AI 据此决定调用哪个工具。

## 运行时：工具调用触发

1. **API 流式返回** — AI 在响应中生成 `tool_use` 内容块
2. **收集 tool_use 块** — 解析响应中的每个 tool_use：id、name、input
3. **判断继续** — 如果有 tool_use 块，进入工具执行阶段

## 工具执行：单个工具调用

### 1. 参数校验

- **Zod/JSON Schema 校验** — 用工具定义的 inputSchema 校验参数格式
- **工具特定校验** — 调用 `tool.validateInput(args, context)`，可拒绝并返回错误原因

### 2. 权限检查

按优先级依次检查：

- **拒绝规则** — 匹配 alwaysDenyRules 的规则（工具级别 + 内容级别）
- **询问规则** — 匹配 alwaysAskRules 的规则
- **工具自身权限** — 调用 `tool.checkPermissions(args, context)`，返回 allow/deny/ask
- **模式级放行**：
  - bypassPermissions 模式 → 自动 allow
  - acceptEdits 模式 + 只读操作 + 工作目录内 → allow
  - 其他 → ask（弹出确认对话框）
- **[v1置空] AI 安全分类器** — 在 auto 模式下用分类器判断安全性的步骤

权限结果三种：
- `allow` → 继续执行
- `deny` → 返回拒绝消息给 AI
- `ask` → 用户确认后决定

### 3. 执行工具

- **调用 call()** — `tool.call(args, context, canUseTool, parentMessage, onProgress)`
- **进度回调** — 工具通过 `onProgress({ toolUseID, data })` 报告进度
- **错误处理** — 捕获异常，转为错误 ToolResult

### 4. 收集结果

- **格式化** — 调用 `tool.mapToolResultToToolResultBlockParam(output, toolUseID)`
- **注入消息** — 将 tool_result 内容块包装为 user message
- **注入附加消息** — 工具返回的 `newMessages`（skill prompt、文件变更等）
- **修改上下文** — 工具返回的 `contextModifier`（切换模型、追加权限等）

### 5. 后处理

- **[v1置空] 附加注入** — 文件变更通知、Hook 注入、记忆更新、Skill 发现
- **刷新工具列表** — 新 MCP 连接可能带来新工具
- **更新轮次计数** — turns++

## 并发工具执行 `[v1置空]`

- **并发安全检查** — `tool.isConcurrencySafe(input)` 判断可否并发
- **StreamingToolExecutor** — 边流式接收边执行工具，不等全部响应完成

---

## v1 实际实现 (Phase 2)

general-agent v1 Phase 2 实现的工具系统：

1. **Tool 基类** — `tools/tool.py`，对标 cc-haha buildTool() 模式，提供全部默认值
2. **ToolsRegistry** — `tools/registry.py`，注册/查找/过滤
3. **7 个核心工具**：
   - **BashTool** — shell 命令执行，只读检测（黑名单模式），超时处理
   - **FileReadTool** — 文件读取，行偏移/限制，始终只读
   - **FileWriteTool** — 文件创建/覆盖，权限询问
   - **FileEditTool** — old_string→new_string 替换，replace_all 支持
   - **GrepTool** — ripgrep 正则搜索，支持 glob 过滤、大小写
   - **GlobTool** — 文件名模式匹配，按修改时间排序
   - **WebFetchTool** — HTTP/HTTPS 获取网页内容，HTML→文本转换

实现模式：
- Tool 基类提供所有默认值（is_enabled=True, is_read_only=False 等）
- 子类只覆盖需要的属性和方法
- PermissionResult(behavior="allow"|"deny"|"ask") 对标 cc-haha 权限检查
- validate_input() 在 call() 之前运行，路径规范化和安全检查

与文档计划差异：
- 未实现并发执行（串行）
- 未实现 AI 安全分类器（走 deny→allow→ask 三层规则）
- 未实现进度回调（on_progress 占位但不用）
- 未实现 auto_classifier_input（v1 不需要）

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/Tool.ts, src/services/tools/toolOrchestration.ts, src/services/tools/StreamingToolExecutor.ts
