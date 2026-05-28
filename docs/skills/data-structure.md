# 数据结构

> Skills 系统的数据结构定义。

---

## SKILL.md 文件格式

每个 Skill 目录（目录名 = skill 名）下必须包含 `SKILL.md`，使用 YAML frontmatter + Markdown 正文：

```yaml
---
name: pdf
description: Process and analyze PDF files
when_to_use: When the user mentions a PDF file
allowed-tools: Bash(ls *), Read, Write
model: claude-sonnet-4-20250514
user-invocable: true
context: inline
paths: "*.pdf"
---
# PDF Processing Skill

Instructions for processing PDF files...
```

### frontmatter 字段

- `name: str` — skill 唯一标识
- `description: str` — 一句话说明，帮助 AI 判断何时调用
- `when_to_use: str` — 触发条件说明
- `allowed-tools: str`（可选）— 该 skill 运行时可用的工具白名单
- `model: str`（可选）— 指定执行此 skill 的模型
- `user-invocable: bool`（可选，默认 true）— 是否允许用户手动 `/skill-name` 调用
- `context: str`（可选，默认 inline）— 执行模式 `inline` 或 `fork`
- `paths: str`（可选）— glob 路径模式，在匹配文件被触碰时激活此 skill
- `disable-model-invocation: bool`（可选）— 禁止模型通过 Skill 工具调用

### prompt 正文

frontmatter 之后的 Markdown 正文即为 skill 的 prompt 内容，注入到对话中指导 AI。支持以下占位符：
- `$ARGUMENTS` / `$1`, `$2` — 用户传入的参数
- `${CLAUDE_SKILL_DIR}` — skill 目录绝对路径
- `${CLAUDE_SESSION_ID}` — 当前会话 ID

---

## Skill 命令结构

Skill 被加载后转换为 Command 对象：

```
SkillCommand:
  name: str                   # 同 frontmatter name
  description: str             # 同 frontmatter description
  whenToUse: str               # 同 frontmatter when_to_use
  type: 'prompt'               # 固定为 prompt 类型

  # 执行配置
  allowedTools: list[str]      # 同 frontmatter allowed-tools
  model: str                   # (可选) 同 frontmatter model
  context: 'inline' | 'fork'   # 执行模式
  userInvocable: bool          # 是否允许用户调用

  # 条件激活
  paths: str                   # (可选) glob 模式，非空则为条件 skill

  # 来源追踪
  loadedFrom: str              # 'skills' | 'dynamic' | 'conditional' | 'plugin' | 'mcp'
  source: str                  # 来源详细信息

  # prompt 生成
  getPromptForCommand(args, context) -> list[ContentBlock]
```

---

## v1 简化结构

general-agent v1 使用简化的 Skill 结构：
- **仅项目级**：`<project>/.claude/skills/<name>/SKILL.md`
- **仅 Inline 模式**：不支持 `context: fork`
- **不支持**：`paths`（条件 skill）、`model`、`disable-model-invocation`

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/types/command.ts, src/tools/SkillTool/, src/skills/loadSkillsDir.ts
