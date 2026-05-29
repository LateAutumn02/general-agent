# general-agent 文档指南

> general-agent 设计文档的组织方式与编写规范。

## 文档结构

每个功能模块包含 **两个文件**：

| 文件 | 用途 | 面向读者 |
|---|---|---|
| `flow.md` | 模块的完整生命周期与执行流程 | 要理解"怎么做" |
| `data-structure.md` | 核心类型定义、接口设计、数据格式 | 要查阅"长什么样" |

分离的理由：流程关注行为逻辑（先干什么后干什么），数据结构关注静态定义（接口长什么样），两者独立变化，分开维护不易耦合。

## 编写规范

### flow.md 规范

流程文档描述一个模块从启动到结束的完整生命周期，核心要求：

1. **按阶段拆分** — 用 `## 阶段N：名称` 或 `## 阶段标题` 划分，子步骤用数字列表

   ```markdown
   ## 阶段1：工具注册

   1. **构建工具对象** — 说明这步做什么
   2. **按环境拼装** — 说明这步做什么
   ```

2. **每步一句话说明意图** — 格式：`粗体名称 + 破折号 + 一句话`

3. **标注 v1 范围** — 当前版本暂不实现的步骤标注 `[v1置空]`

4. **末尾必须包含三个部分**：
   - **v1 简化流程** — 用 3-5 条描述 v1 实际会做什么
   - **差异说明** — 列出跳过的步骤及原因
   - **参考源** — 标注从哪个项目的哪些文件分析得出

### data-structure.md 规范

数据结构文档描述模块的类型和接口，使用统一的伪代码风格。

#### 伪代码风格

必须遵守以下格式规则：

1. **类型定义格式**：
   ```
   TypeName:
     field_name: type         # 字段用途说明
     optional_field: type     # (可选) 其后描述含义
     nested:
       sub_field: type        # 嵌套子字段
   ```

2. **基础类型名称**：
   - `str`、`int`、`float`、`bool`
   - `list`、`list[str]`、`list[dict]`（泛型用方括号）
   - `dict`、`fn`
   - 枚举类型值用单引号：`'allow' | 'deny' | 'ask'`

3. **函数签名**：
   ```
   function_name(args, options) -> ReturnType
   ```

4. **注释规则**：
   - 每行类型定义后必须跟 `# 中文用途说明`
   - 可选字段在注释开头说明条件：`# (可选) 用途说明`
   - 不要写废话注释（如 `# str 字符串类型`）

5. **禁止的做法**：
   - 不要混用 TypeScript 语法（`string[]`、`?` 可选标记）
   - 不要混用 YAML/JSON 风格的缩进
   - 不要同一个类型在多个文件重复定义（用引用代替）

**示例（正确）：**

```
Tool:
  name: str                   # 工具唯一名称
  inputSchema: dict           # 输入参数 JSON Schema
  isEnabled() -> bool         # 是否在当前环境可用
  call(args, context) -> ToolResult  # 执行业务逻辑

ToolResult:
  data: any                   # 工具执行结果数据
  newMessages: list           # (可选) 附加注入的消息列表

PermissionResult:
  behavior: 'allow' | 'deny' | 'ask'  # 权限决策结果
  message: str                # (可选) 决策说明
```

**示例（错误）：**

```
// 错误：混用 TypeScript 语法
Tool:
  aliases: string[]           // 用到了 TS 数组语法
  isReadOnly?: boolean        // ? 是 TS 可选标记
```

#### 编写内容

1. **标注 v1 范围** — 字段标注 `[v1]` 表示 v1 需要，否则默认不需要

2. **复杂类型拆出去** — 如果某个类型本身很大（如 AppState 有 85 个字段），在本文档写概要，完整定义放引用位置

3. **避免循环引用** — 如果一个类型在多个模块中用到，选一个主文档定义，其余文档用 `> 详见 xxx/data-structure.md` 引用

### 元信息规范

每个文档末尾必须包含元信息行：

```markdown
> 最后更新: YYYY-MM-DD | 参考源 commit: <short-hash> | [可选: 参考文件路径]
```

- **日期**：文档最后修改日期
- **commit**：参考项目源码对应的 short hash（7 位）
- **参考文件**：所在模块的流程文档末尾已有完整参考源列表时可不写参考文件，仅写日期和 commit；全局文档和数据结构文档需写明参考文件

**完整示例：**

```markdown
> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/memdir/
```

---

## 当前模块

| 模块 | 目录 | 状态 |
|---|---|---|
| 系统架构 | `architecture/` | 已完成 |
| Agent 核心循环 | `agent/` | Phase 3 已完成 |
| 工具系统 | `tools/` | Phase 2 已完成 |
| 记忆系统 | `memory/` | Phase 4 已完成 |
| Skills 系统 | `skills/` | 已完成 |
| 程序初始化 | `initialization/` | Phase 1 已完成 |
| 多 Agent 编排 | `multi-agent/` | Phase 5 已完成 |
| MCP 协议 | `mcp/` | 已完成 |
| 上下文压缩 | `compact/` | 已完成 |
| 沙箱安全 | `sandbox/` | 已完成 |
| API 集成 | `api/` | Phase 1 已完成 |

## 设计理念

这套双文件模式借鉴了以下理念：

- **Diataxis 框架**中"解释"与"参考"的分离——流程是解释（how it works），数据结构是参考（API reference）
- **Anthropic Claude Code 文档规范**中"保持文件简洁可扫描"的原则，每个文件聚焦单一职责
- **Docs-as-code 实践**，文档与代码同仓库，随功能迭代同步更新

补充模块文档时，照抄现有模块的格式即可。

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
