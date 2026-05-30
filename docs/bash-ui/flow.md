# 流程

> Bash 工具 UI 渲染的完整流程。从命令执行产生输出，到格式化展示给用户。

参考 Claude Code 的 Bash 输出渲染管线：BashTool → mapToolResult → UI 组件链 → 用户可见。

---

## 概览

当前 general-agent 的 Bash 工具只做了命令执行，输出是原始文本直接返回给用户，没有任何渲染处理。Claude Code 有完整的渲染管线：

```
BashTool.call()
  │
  ├─→ 模型侧: mapToolResultToToolResultBlockParam()  # 截断、持久化
  │
  └─→ 用户侧: BashToolResultMessage (React 组件)
        ├─ OutputLine (stdout)   # ANSI 渲染 + 截断 + JSON 美化
        ├─ OutputLine (stderr)   # 同上, 标红
        └─ ShellProgressMessage  # 流式进度
```

v1 目标：在纯文本 CLI 环境下实现核心渲染能力。

---

## 阶段1：输出分类和提取

命令执行后产出的原始数据需要一个统一的输出结构：

1. **收集 stdout/stderr** — 分开保存，不混合
2. **识别输出类型** — 文本、图片（base64）、空输出
3. **提取沙箱违规** — stderr 中 `<sandbox_violations>` 标签内容单独处理
4. **区分静默命令** — `mv`/`cp`/`rm`/`mkdir`/`touch`/`chmod` 等无输出是正常的

## 阶段2：输出格式化（模型侧）

发送给模型的 tool_result 内容需要合理截断避免上下文膨胀：

1. **去除空行** — stdout 开头的空行去掉
2. **大输出持久化** — 结果超过 30K 字符时写入临时文件，tool_result 里放 `<persisted-output>` 标签
3. **图片处理** — 检测到图片数据时注入提示文字
4. **后台任务** — 异步执行的命令附加状态信息

## 阶段3：stdout 行级渲染

每条输出行独立处理，核心组件 `OutputLine`：

1. **ANSI 色码解析** — 解析 SGR 序列（`\033[...m`），转为终端色码，保留原始 bash 输出的彩色文本
2. **JSON 检测和美化** — 单行 <10K 字符时尝试 JSON.parse → pretty print + 2 空格缩进
3. **链接检测** — 可选：http/https URL 转为 OSC 8 超链接
4. **截断规则**（非 verbose 模式）：
   - 默认显示前 **3 行**
   - 如果输出在此范围内 → 直接显示
   - 超出 → 截断并显示 `… +N lines`
   - 处理上限 **3 × 终端宽度 × 4** 字符，防止大输出 O(n)
5. **完整显示**（verbose 模式）：全部输出，但去掉下划线 ANSI 码（渲染会溢出）

## 阶段4：stderr 特殊处理

1. **默认标红** — stderr 内容用红色/警告色显示
2. **隐藏沙箱违规** — 匹配 `<sandbox_violations>...</sandbox_violations>` 标签，从 stderr 中剥离
3. **cwd 重置警告** — 识别特定模式（如 `(cd ... && ...)` 自动行为），以 dim 样式展示而非红色

## 阶段5：静默命令和空输出

1. **静默命令列表** — `mv`、`cp`、`rm`、`mkdir`、`touch`、`chmod`、`chown`、`ln`、`export`、`unset`、`alias` `[v1置空]`
2. **无输出匹配** — 命令匹配静默列表 + 无 stdout/stderr → 显示 `Done`（dim 文本）
3. **非静默无输出** — 显示 `(No output)`（dim 文本）
4. **已中断** — 显示 `Interrupted`（警告色）

## 阶段6：命令显示截断

工具执行时展示的命令行也需要截断：

1. **多行命令** — 最多显示 2 行
2. **单行命令** — 最多显示 160 字符，超出加 `...`
3. **sed 就地编辑** — 不显示完整 sed 命令，而是显示被编辑的文件路径 `[v1置空]`

## 阶段7：进度显示 `[v1置空]`

长时间运行的命令显示流式进度：

1. **触发阈值** — 命令执行超过 2 秒显示进度
2. **无输出** — 显示 `Running...` + 已耗时
3. **有输出** — 显示最后 5 行 + 总行数 + 字节数 + 已耗时
4. **超时显示** — 显示剩余超时时间

> v1 不实现流式进度——需要异步 yield 工具执行中间状态，改动 Agent 循环较大。

## 阶段8：输出折叠分组 `[v1置空]`

多个连续的同类命令折叠为摘要徽章：

1. **搜索类** — `find`/`grep`/`rg`/`locate` → "Searched for N patterns"
2. **读取类** — `cat`/`head`/`tail`/`wc`/`jq` → "Read N files"
3. **列表类** — `ls`/`tree`/`du` → "Listed N directories"
4. **Git 类** — `git ...` → "N git operations"
5. **其他 Bash** — 不归类的折叠为 "Ran N bash commands"

> v1 不实现——需要在 Agent 循环层做连续 tool_use 检测和合并，改动较大。

---

## v1 实际实现计划

1. **BashOut 数据结构** — stdout、stderr、exitCode、interrupted、isImage、noOutputExpected
2. **管道解析器** — 解析 stdin → 接收 stdout+stderr
3. **OutputLine 渲染** — ANSI 解析 + 截断（3 行）+ stderr 标色
4. **命令分类** — 静默命令表，匹配展示 "Done"
5. **耗时显示** — "Took 1.2s"
6. **长命令截断** — 160 字符
7. **不做** — 流式进度、折叠分组、JSON 美化、沙箱违规提取

实现文件：
- `general_agent/tools/bash.py` — 增强 BashTool，添加 BashOut 和渲染逻辑
- `general_agent/tools/bash_ui.py` — 新增：OutputLine、ANSI 解析、截断

---

## 差异说明

| 功能 | Claude Code | general-agent v1 | 原因 |
|---|---|---|---|
| ANSI 渲染 | Ink 组件树的 `<Ansi>` 解析器 | 纯文本正则解析 + colorama | 无 TUI |
| 截断/展开 | TUI `ctrl+o` 交互展开 | 仅 `--verbose` 模式全文 | 无交互 UI |
| 流式进度 | React 组件异步更新 | 不做 | 需改 Agent 循环 |
| 折叠分组 | 多层 state 追踪 | 不做 | 改动大 |
| JSON 美化 | `try/catch JSON.parse` + pretty print | 不做 | 低频场景 |
| 链接渲染 | OSC 8 超链接 | 不做 | 终端差异大 |

---

> 最后更新: 2026-05-31 | 参考源 commit: 5a86ab0
>
> 参考源：cc-haha src/tools/BashTool/BashTool.tsx, UI.tsx, BashToolResultMessage.tsx; src/components/shell/OutputLine.tsx, ShellProgressMessage.tsx; src/utils/terminal.ts; src/ink/Ansi.tsx
