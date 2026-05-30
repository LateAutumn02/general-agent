# 数据结构

> Bash 工具 UI 渲染层的核心数据结构。

---

## BashOut

命令执行产出的原始数据，替代当前直接返回字符串的设计：

```
BashOut:
  stdout: str                    # 标准输出内容
  stderr: str                    # 标准错误内容
  exitCode: int                  # 退出码（0 = 成功）
  interrupted: bool              # 是否被用户中断（Ctrl+C）
  isImage: bool                  # 是否为图片数据
  noOutputExpected: bool         # 命令是否为静默命令（无输出正常）
  persistedOutputPath: str       # (可选) 输出过大时写入的临时文件路径 [v1置空]
  persistedOutputSize: int       # (可选) 持久化文件的字节数 [v1置空]
```

---

## CommandClass

命令分类枚举，用于决定空输出时的展示文字：

```
CommandClass:
  'silent'                       # mv/cp/rm/mkdir/touch → 显示 "Done"
  'search'                       # find/grep/rg → 空输出显示 "(no matches)"
  'read'                         # cat/head/tail/wc → 空输出显示 "(empty)"
  'list'                         # ls/tree/du → 空输出显示 "(empty directory)"
  'general'                      # 其他 → 空输出显示 "(no output)"
```

---

## 静默命令表

```
BASH_SILENT_COMMANDS:
  'mv' 'cp' 'rm' 'mkdir' 'rmdir' 'touch'
  'chmod' 'chown' 'chgrp' 'ln' 'export'
  'unset' 'alias' 'source' '.' 'cd'
```

---

## 截断常量

```
MAX_STDOUT_LINES: 3              # 默认显示行数
MAX_STDOUT_CHARS_PROCESS: 3 × terminal_width × 4  # 处理字符上限（防 OOM）
MAX_COMMAND_DISPLAY_LINES: 2     # 命令回显最大行数
MAX_COMMAND_DISPLAY_CHARS: 160   # 命令回显最大字符数
PADDING_TO_PREVENT_OVERFLOW: 10  # 截断前缀 "  ⎿ " 占位
```

---

## TruncationResult

截断操作的结果：

```
TruncationResult:
  text: str                      # 截断后的文本
  omittedLines: int              # 被截掉的行数
  isTruncated: bool              # 是否发生了截断
```

---

## ANSISpan

ANSI 解析后的一个格式化区间：

```
ANSISpan:
  text: str                      # 文本内容
  bold: bool                     # 粗体
  dim: bool                      # 暗色
  italic: bool                   # 斜体 [v1置空]
  underline: bool                # 下划线
  strikethrough: bool            # 删除线 [v1置空]
  fg: str | None                 # 前景色 ('red' | 'green' | 'blue' | ... | '#rrggbb')
  bg: str | None                 # 背景色
```

---

## BashResult（模型侧，替代当前 str 返回值）

模型侧 API 响应的 tool_result 格式化：

```
BashResult:
  model_output: str              # 发送给模型的文本（截断后的）
  display_output: str            # 给用户看的文本（完整或已渲染）
  exit_code: int                 # 退出码（0 正常）
  duration_ms: int               # 执行耗时（毫秒）
```

---

## 命令回显格式

工具执行时在终端显示的命令行：

```
回显格式:
  [tool_use_id] 命令文本 (最多 160 字符, 最多 2 行)

示例:
  → Bash ls -la /home/user/project
  → Bash find . -name "*.py" -exec grep "import" {} \;  # 截断至 160 字符
```

---

> 最后更新: 2026-05-31 | 参考源 commit: 5a86ab0 | 参考文件: cc-haha src/tools/BashTool/BashTool.tsx, src/components/shell/OutputLine.tsx, src/utils/terminal.ts
