# 数据结构

> Bash UI Textual 渲染层的核心数据结构。

---

## BashOut（保留自 v1）

命令执行产出的原始数据：

```
BashOut:
  stdout: str                    # 标准输出内容（含 ANSI 码）
  stderr: str                    # 标准错误内容（含 ANSI 码）
  exit_code: int                 # 退出码（0 = 成功）
  interrupted: bool              # 是否被用户中断
  timed_out: bool                # 是否超时
  duration_ms: int               # 执行耗时（毫秒）
  is_silent: bool                # 是否为静默命令
  is_image: bool                 # 是否为图片数据 [v2 始终 False]
```

---

## 静默命令表（保留自 v1）

```
SILENT_COMMANDS:
  'mv' 'cp' 'rm' 'mkdir' 'rmdir' 'touch'
  'chmod' 'chown' 'chgrp' 'ln' 'export'
  'unset' 'alias' 'source' '.' 'cd'
```

---

## PanelMeta（新增）

给 ChatContainer.write() 传递的样式元数据：

```
PanelMeta:
  css_class: str                 # CSS 类名（空格分隔）
  border_title: str              # 左边框标题
  border_subtitle: str           # 右边框副标题
```

---

## Textual Message 类型（新增）

### ToolDisplayMessage

工具结果面板（承载 Rich renderable）：

```
ToolDisplayMessage:
  renderable: RenderableType     # Rich Panel / Text / Table 等
```

### ProgressMessage

工具状态行（纯文本）：

```
ProgressMessage:
  text: str                      # 工具进度说明
```

### StreamMessage

流式文本增量：

```
StreamMessage:
  chunk: str                     # 一个文本块
```

### StreamEndMessage

流式传输结束信号（无字段）。

### PermissionRequest

权限请求：

```
PermissionRequest:
  tool_name: str
  args: dict
```

---

## 截断常量（保留自 v1）

```
MAX_STDOUT_LINES: 5              # stdout 最多显示行数
MAX_STDERR_LINES: 3              # stderr 最多显示行数
MAX_COMMAND_DISPLAY_LINES: 2     # 命令回显最大行数
MAX_COMMAND_DISPLAY_CHARS: 160   # 命令回显最大字符数
```

---

## Rich 渲染函数返回值

| 函数 | 返回类型 | 用途 |
|---|---|---|
| `render_tool_call()` | `rich.text.Text` | 工具状态指示点 |
| `render_bash_panel()` | `rich.panel.Panel` | Bash 输出面板（含 status subtitle） |
| `code_diff()` | `rich.panel.Panel` | 代码差异面板 |
| `file_preview()` | `rich.panel.Panel` | 文件预览（语法高亮） |

---

> 最后更新: 2026-06-01 | 参考: cc-haha docs/bash-ui/data-structure.md v1
