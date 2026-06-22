# 工具系统流程

> 最后更新：2026-06-17

## 阶段1：工具注册

1. **定义工具元数据** - name、description、inputSchema、permission policy。
2. **按平台过滤** - Windows 可启用 PowerShell，Git Bash/WSL 可启用 Bash。
3. **按模式过滤** - plan 模式禁用写操作，print 模式禁用交互审批。

## 阶段2：工具调用

1. **校验输入** - 使用 schema 校验模型传入参数。
2. **生成权限检查** - 调用前创建 PermissionCheck。
3. **执行工具** - 接收 abort signal，输出结构化 ToolResult。
4. **生成 UI 摘要** - 主 transcript 显示短摘要，完整输出留给详情视图。

## 阶段3：工具编排

1. **只读工具并发** - Read/Glob/Grep/WebFetch 可以并发。
2. **写入工具串行** - Edit/Write/Bash 写操作串行。
3. **长任务后台化** - 超时或用户按键可将 shell task 放入后台任务列表。

## v1 工具范围

1. Bash / PowerShell。
2. Read / Write / Edit。
3. Glob / Grep。
4. WebFetch / WebSearch 可以延后到 API 稳定后实现。

