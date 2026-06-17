# Bash UI 渲染流程

> Bash 工具执行 → Rich 渲染面板 → Textual ChatContainer 的完整管线。

---

## 架构概览

general-agent v2 采用 **Textual TUI** 替代了早期 v1 的 raw-ANSI print 方案。渲染管线：

```
BashTool.call()
  │  执行命令, 生成 BashOut
  ├─→ _format_for_model()        # 纯文本 → API tool_result
  └─→ _format_for_display()      # Rich Panel → 用户终端
        │
        └─→ bash_ui.render_bash_panel(out: BashOut) → Panel
              │
              └─→ Bridge.on_progress(Panel) → ToolDisplayMessage
                    │
                    └─→ ChatContainer.write(Panel, panel_meta=...)
                          │
                          └─→ Textual Static widget 渲染
```

## 数据流

```
用户输入 → Editor → run_agent()
  │
  ├─ on_text(chunk)     → Bridge → StreamMessage → StreamingHandler → 实时文本
  ├─ on_progress(tool)  → Bridge → ProgressMessage  → ChatContainer (工具状态点)
  ├─ on_progress(panel) → Bridge → ToolDisplayMessage → ChatContainer (Bash面板)
  └─ on_permission(...) → Bridge → PermissionRequest  → notify()
```

## 组件职责

| 组件 | 文件 | 职责 |
|---|---|---|
| `BashOut` | `tools/bash_ui.py` | 命令执行的结构化输出（stdout, stderr, exit_code, duration） |
| `render_bash_panel()` | `tools/bash_ui.py` | BashOut → Rich Panel（border, title, subtitle） |
| `render_tool_call()` | `tools/bash_ui.py` | 工具状态点 → Rich Text（● Bash(cmd)） |
| `BashTool` | `tools/bash.py` | 命令执行 + 模型侧/用户侧格式化 |
| `RequestBridge` | `ui/bridge.py` | Agent 回调 → Textual Message 转换 |
| `StreamingHandler` | `ui/streaming.py` | 流式文本节流（100ms）刷新到 Static widget |
| `TextualAgentApp` | `ui/app.py` | Textual TUI 主应用（布局 + 消息路由 + 请求处理） |
| `ChatContainer` | `ui/widgets/chat.py` | 消息历史（VerticalScroll + Rich renderable 挂载） |
| `PromptInput` | `ui/widgets/editor.py` | 底部输入框（Enter 提交, ! 开头的 shell 模式） |
| `StatusBar` | `ui/widgets/status_bar.py` | 顶部状态栏（模型, Token 用量, 费用） |

## CSS 主题

两个 TCSS 文件控制所有样式：

- `styles/layout.tcss` — 布局（StatusBar dock top, ChatContainer 1fr, PromptInput dock bottom）
- `styles/panels.tcss` — 面板样式（.tool-panel, .completed, .failed, .user-message, .agent-response）

---

## 与 v1 的差异

| 功能 | v1 (ANSI print) | v2 (Textual) |
|---|---|---|
| 终端输出 | `print()` + ANSI 码 | Textual Widget 局部刷新 |
| Bash 面板 | 手写 `┌─┐` 边框 + ANSI 色码 | Rich Panel + CSS 类 |
| 流式输出 | `sys.stdout.write()` | StreamingHandler + 节流 timer |
| 用户输入 | prompt_toolkit PromptSession | Textual Input widget |
| 工具状态 | ANSI 色点 (`●`) | Rich Text 渲染 |
| 布局 | 无（纯流式输出） | 3 区布局（状态栏/聊天/输入） |
| 主题 | 硬编码色码 | CSS + Textual Theme 变量 |

---

> 最后更新: 2026-06-01 | 参考: cc-haha v1 docs, TunaCode ui/app.py
