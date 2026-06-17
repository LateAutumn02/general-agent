# TUI 流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/bash-ui, reference/cc-haha/src/components/PromptInput

## 阶段1：渲染主界面

1. **Transcript 区域** - 显示用户消息、AI 回复、工具摘要和分隔线。
2. **Streaming 区域** - 当前 assistant delta 在输入框上方流式刷新，完成后并入 transcript。
3. **Interaction 区域** - 输入框、权限审批和补充说明共用底部视觉区域。
4. **Footer 区域** - 显示模型、cwd、权限模式和后台任务状态。

## 阶段2：处理输入模式

1. **Prompt 模式** - 默认模式，Enter 发送自然语言请求。
2. **Bash 模式** - 输入开头 `!` 进入 bash mode，提交时转成 Bash tool request。
3. **Command 模式** - 输入开头 `/` 打开命令系统。
4. **File 模式** - 输入 `@` 触发文件搜索和路径补全。

## 阶段3：显示工具调用

1. **无需审批的工具** - transcript 中只显示一行 `• Searched files...` 这样的摘要。
2. **需要审批的工具** - 底部显示权限面板，禁止把审批框放到历史顶部。
3. **长输出** - 默认折叠，用户进入工具详情或任务详情时查看完整 stdout/stderr。

## 阶段4：中断和复制

1. **选中文本 Ctrl+C** - 复制选择，不退出应用。
2. **无选择第一次 Ctrl+C** - 显示退出提示。
3. **无选择第二次 Ctrl+C** - 退出应用。
4. **请求运行中 Esc** - 取消当前 turn。

## v1 简化流程

1. 使用 Ink + React。
2. 先实现纯文本 transcript，不做复杂 Markdown block。
3. `!` bash mode、`/help`、权限面板必须在第一版完成。
4. 后台任务详情可先用列表视图。

