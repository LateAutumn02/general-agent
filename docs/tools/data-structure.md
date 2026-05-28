# 数据结构

> 工具系统的核心数据结构。Tool 接口、ToolResult、ValidationResult、PermissionResult、工具注册表。

---

## Tool 接口

每个工具必须实现的接口，general-agent v1 仅需核心字段：

```
Tool:
  # === 标识 ===
  [v1] name: str                              # 工具唯一名称
  aliases: list[str]                           # (可选) 别名，向后兼容 [v1置空]
  searchHint: str                              # (可选) 搜索提示 [v1置空]

  # === 核心方法 ===
  [v1] call(args, context, canUseTool, parentMessage, onProgress?) -> ToolResult
       # 执行业务逻辑。接收解析后的输入、工具上下文、权限回调
  [v1] validateInput(args, context) -> ValidationResult | None
       # 在权限检查前验证输入参数。返回 None 表示通过
  [v1] description(input, options) -> str
       # 返回用户可读的工具使用描述，用于权限确认对话框
  [v1] checkPermissions(args, context) -> PermissionResult
       # 工具特定的权限检查。如果不是安全问题返回 allow

  # === 输入/输出 ===
  [v1] inputSchema: dict                       # 输入参数 JSON Schema 定义
  outputSchema: dict                           # (可选) 输出 Schema [v1置空]
  [v1] mapToolResultToToolResultBlockParam(output, toolUseID) -> ToolResultBlock
       # 将工具输出格式化为 API 兼容的 tool_result 内容块

  # === 属性判断 ===
  [v1] isEnabled() -> bool                     # 是否在当前环境可用（默认 true）
  [v1] isReadOnly(input) -> bool               # 是否只读操作（用于权限判断，默认 false）
  isConcurrencySafe(input) -> bool              # 是否可并发执行 [v1置空]（默认 false）
  isDestructive(input) -> bool                 # 是否不可逆操作 [v1置空]

  # === 其他 ===
  prompt(options) -> str                       # 返回该工具在 system prompt 中的说明文本
  interruptBehavior() -> 'cancel' | 'block'    # (可选) 用户中断时的行为 [v1置空]
  maxResultSizeChars: int                      # 工具结果最大字符数（超出则持久化）
```

---

## ToolResult 工具结果

```
ToolResult:
  [v1] data: any                               # 工具执行结果数据（传给 mapToolResultToToolResultBlockParam）
  [v1] newMessages: list                       # (可选) 附加注入的消息（如 skill prompt、文件变更通知）
  contextModifier: fn                          # (可选) 修改上下文的回调 [v1置空]
```

---

## ValidationResult 校验结果

```
ValidationResult:
  result: bool                                 # true = 通过，false = 拒绝
  message: str                                 # (可选) 拒绝时的错误原因（会告知模型）
  errorCode: int                               # (可选) 错误码
```

---

## PermissionResult 权限结果

```
PermissionResult:
  [v1] behavior: 'allow' | 'deny' | 'ask'      # 权限决策结果
  updatedInput: dict                           # (可选) 被 hook 或权限规则修改后的输入 [v1置空]
  message: str                                 # (可选) 决策说明
```

---

## 工具注册表

```
ToolsRegistry:
  [v1] all: list[Tool]                         # 所有已注册的工具
  [v1] getByName(name: str) -> Tool | None     # 按名称查找工具
  [v1] filter(fn) -> list[Tool]                # 按条件过滤（如 isEnabled、权限规则）
  [v1] assemble(mcpTools: list) -> list[Tool]  # 合并 MCP 工具并去重排序
```

---

## ContentBlock 工具相关

流式 API 响应中的工具调用块和结果块：

```
ToolUseBlock:
  type: 'tool_use'
  id: str                      # 唯一标识（与 tool_result 配对）
  name: str                    # 工具名
  input: dict                  # 工具参数（JSON）

ToolResultBlock:
  type: 'tool_result'
  tool_use_id: str             # 对应的 ToolUseBlock.id
  content: str                 # 工具执行结果文本
  is_error: bool               # 是否为错误结果
```

---

## v1 实际实现 (Phase 2)

已实现的 Tool 基类方法：

| 方法 | 默认值 | 说明 |
|---|---|---|
| `is_enabled()` | `True` | 工具是否可用 |
| `is_read_only(args)` | `False` | 是否只读 |
| `is_concurrency_safe(args)` | `False` | 是否可并发 |
| `is_destructive(args)` | `False` | 是否不可逆 |
| `check_permissions(args, ctx)` | `allow` | 权限检查 |
| `validate_input(args, ctx)` | `None` (通过) | 输入校验 |
| `to_classifier_input(args)` | `""` (跳过) | 分类器输入 |

未实现的 cc-haha 方法（v1 不需要）：用户界面渲染、TUI 渲染、prepare_permission_matcher、extract_search_text、grouped_tool_use 渲染。

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/Tool.ts:362-695, src/types/tools.ts, src/types/permissions.ts
