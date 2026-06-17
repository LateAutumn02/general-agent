# 数据结构

> 记忆系统的数据结构定义。

---

## 记忆文件格式

每条记忆是一个 .md 文件，使用 YAML frontmatter + Markdown 正文：

```yaml
---
name: 用户角色与偏好
description: 用户是全栈开发者，偏好 React + TypeScript
type: user
---
用户是某公司前端组长，6 年经验。
技术栈偏好：React 18+, TypeScript, Bun。
代码风格：偏好简洁，不喜欢过度注释。
```

### frontmatter 字段

- `name: str` — 记忆名称
- `description: str` — 一句话描述（用于索引）
- `type: str` — 记忆类型，四选一：
  - `user` — 用户角色、技术栈偏好、代码风格
  - `feedback` — 行为反馈（修正和确认）
  - `project` — 项目状态、截止日期、决策背景
  - `reference` — 外部系统引用（API 地址、文档链接等）

---

## MEMORY.md 索引文件

每行一条索引，指向具体的记忆文件：

```markdown
- [用户角色与偏好](user_role.md) — 用户是全栈开发者，偏好 React + TypeScript
- [项目截止日期](project_state.md) — API v2 需在 6 月前完成
- [用户反馈](feedback.md) — 不喜欢过度注释，偏好简洁代码
```

**限制**：最多 200 行，最多 25KB。超出截断并警告。

---

## 记忆存储结构

```
~/.claude/projects/<sanitized-git-root>/memory/
├── MEMORY.md          # 索引文件
├── user_role.md       # 用户角色、目标、偏好
├── project_state.md   # 项目状态、截止日期、决策
├── feedback.md        # 行为反馈
├── references.md      # 外部系统引用
└── team/              # 团队记忆（可选）
    └── MEMORY.md
```

---

## memoryScan 内存结构

运行时扫描记忆文件返回的内存表示：

```
MemoryHeader:
  path: str                    # 文件相对路径
  mtimeMs: int                 # 修改时间戳（毫秒）
  name: str                    # frontmatter 中的 name
  description: str             # frontmatter 中的 description
  type: 'user' | 'feedback' | 'project' | 'reference'  # 记忆类型

RelevantMemory:
  path: str                    # 文件路径
  mtimeMs: int                 # 修改时间戳（用于时效计算）
```

---

## 会话记忆模板（Session Memory，v1 不做）

```
SessionMemoryTemplate:
  title: str                   # 会话标题
  currentState: str            # AI 正在做什么任务
  taskSpec: str                # 用户要求的具体目标
  filesAndFunctions: str       # 当前涉及的关键文件
  workflow: str                # 常用命令和执行顺序
  errorsAndCorrections: str    # 遇到的错误及修复
  codebaseStructure: str       # 重要的系统组件
  learnings: str               # 什么方法有效/无效
  keyResults: str              # 用户要求的输出成果
  worklog: str                 # 按步骤记录尝试了什么
```

---

## v1 简化数据结构

general-agent v1 简化：
- **无 MEMORY.md 索引**：每个记忆文件独立存在，全量加载
- **仅 user 和 project 两种类型**
- **简单文件结构**：`<project>/.claude/memory/*.md`
- **无 frontmatter 中的 name/description**：直接用文件名和内容

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/memdir/memoryTypes.ts, src/memdir/memdir.ts
