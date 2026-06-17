# 流程

> Skills 系统的完整生命周期流程。从启动发现、运行时激活、执行注入，到压缩恢复。

---

## 启动时：静态发现

1. **扫描 skill 目录** — 并行扫描所有 skill 目录：
   - `~/.claude/skills/` — 用户全局
   - `<project>/.claude/skills/` — 项目级
   - 通过 `--add-dir` 添加的额外目录
2. **读取 SKILL.md** — 每个子目录下的 SKILL.md，解析 YAML frontmatter
3. **去重** — 按 realpath 去重，跳过重复加载
4. **分类**：
   - 带有 `paths` frontmatter → 存入 `conditionalSkills`（条件 Skill，暂不暴露）
   - 无 `paths` → 存入 `staticSkills`（常规 Skill，立即可用）
5. **注册到命令列表** — 将 Skill 注册到全局命令表，AI 可知其存在
6. **注入 skill 说明** — 在系统提示词中列出所有可用 skill 的名称和描述

## 运行时：动态发现 `[v1置空]`

1. **文件触碰触发** — AI 通过 Read / Write / Edit 触碰文件时
2. **向上遍历** — 检查文件路径的各级父目录下是否存在 `.claude/skills/`
3. **跳过已检查** — 用 `dynamicSkillDirs` Set 避免重复扫描
4. **跳过 gitignore** — 忽略被 .gitignore 排除的路径
5. **加载新 skill** — 发现后存入 `dynamicSkills`

## 运行时：条件 Skill 激活 `[v1置空]`

1. **文件触碰时** — 检查当前触碰的文件路径
2. **glob 匹配** — 遍历所有 `conditionalSkills`，用 gitignore 风格匹配 `paths` frontmatter
3. **激活** — 匹配成功的 skill 移入 `dynamicSkills`，对 AI 可见

## 运行时：Skill 执行

### Inline 模式（默认，v1 使用此模式）

1. **AI 调用 Skill 工具** — 传入 skill 名 + 可选参数（`skill: "pdf", args: "--help"`）
2. **查找 Skill 定义** — 从命令列表中查找对应 Skill
3. **校验输入** — 检查 skill 名有效、未禁用 model-invocation
4. **权限检查**：
   - 检查 deny 规则（精确匹配或前缀 `:*`）
   - 检查 allow 规则
   - 如果 skill 仅使用安全属性，自动放行
5. **处理 prompt**：
   - 用实际参数替换占位符（`$ARGUMENTS`、`$1`、`${CLAUDE_SKILL_DIR}`）
   - 执行内联 shell 命令（`` !`...` ``，非 MCP skill）
6. **注入对话** — 将处理后的 prompt 作为 new user message 注入
7. **修改上下文** — 如果有 `allowedTools`，追加权限白名单；如果有 `model`，切换模型

### Fork 模式 `[v1置空]`

1. **AI 调用 Skill 工具** — 同上
2. **创建子 Agent** — 独立上下文 + token 预算
3. **执行** — 子 Agent 在隔离环境中完成 Skill 任务
4. **返回结果** — 以 tool_result 形式返回主对话

## 压缩时：Skill 恢复

1. **自动压缩发生时** — 检查是否有已激活的 skill
2. **重新注入** — 将已激活 skill 的 prompt 重新注入到压缩后的上下文
3. **防止遗忘** — 确保 AI 在压缩后仍然遵循 skill 中的指令

---

## v1 实际实现

1. **启动时** — 扫描 `<project>/.claude/skills/<name>/SKILL.md`，解析 YAML frontmatter
2. **System prompt** — 注入可用 Skill 列表（name + description + when_to_use）
3. **斜杠命令** — 用户输入 `/skill-name` 激活，prompt 注入对话
4. **优先级** — 内置命令（/help）优先于 skill 命令
5. **不做** — 动态发现、条件 Skill、Fork 模式

---

> 最后更新: 2026-05-28 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/tools/SkillTool/SkillTool.ts, src/skills/, src/services/skillSearch/
