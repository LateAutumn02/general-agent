# TUI 流程

> 最后更新：2026-06-22

## 阶段1：渲染主界面

1. **Transcript 区域** - 显示用户消息、AI 回复、工具摘要、Agent 进度线、队友消息。
2. **Streaming 区域** - 当前 assistant delta 在输入框上方流式刷新，完成后并入 transcript。
3. **Interaction 区域** - 输入框、权限审批和补充说明共用底部视觉区域。

## 阶段2：处理输入模式

1. **Prompt 模式** - 默认模式，Enter 发送自然语言请求。
2. **Bash 模式** - 输入开头 `!` 进入 bash mode，提交时转成 Bash tool request。
3. **Command 模式** - 输入开头 `/` 打开命令系统。
4. **File 模式** - 输入 `@` 触发文件搜索和路径补全。

## 阶段3：显示工具调用

1. **无需审批的工具** - transcript 中只显示摘要行。
2. **需要审批的工具** - 底部显示权限面板。
3. **长输出** - 默认折叠。
4. **Agent 调用** - 显示分组进度（"Running 3 agents..."），每行显示 agent 类型/名称、工具计数、token 用量。

## 阶段4：Agent 可视化（蜂群模式）

### 4a. Spinner 区域

```
⠋ Analyzing...
  ╞═ @researcher  Searching: src/auth.ts  3 tools · 12K tokens
  ├─ @reviewer    Idle for 5s
  └─ @tester      Running tests...         8 tools · 45K tokens
```

- 显示 leader 活动动词 + teammate 状态树
- 每行：名称（彩色） + 活动 + 统计
- 空闲显示 "Idle for Xs"

### 4b. Agent 进度线（transcript 内）

```
└─ Agent @researcher  3 tools · 12.5K tokens
   ⎿  Done
```

- 子 agent 完成后在 transcript 中插入摘要行
- 后台 agent 显示 "Running in the background"

### 4c. 工具调用折叠

- 连续同类搜索/读取自动合并为统计行：`"Searching: 5 searches, 3 file reads"`
- 超出 3 行的历史折叠：`"+5 more tool uses [ctrl+o to expand]"`

### 4d. 队友消息渲染

```
@alice> [✓] Completed task #123 (Auth audit)
```

- 消息类型区分：任务完成、任务分配、关闭请求、空闲通知（隐藏）
- 消息自动作为 conversation turn 注入

## 阶段5：任务面板

1. 优先级排序，显示 status / owner / activity / 阻塞关系。
2. 任务 owner 的当前活动实时更新。

## 阶段6：Footer 增强

```
deepseek · deepseek-v4-flash  [main] [@researcher] [@reviewer]
```

- Agent pills：水平滚动的 agent 标签，带颜色
- 选中的高亮

## 阶段7：中断和复制

1. **选中文本 Ctrl+C** - 复制选择，不退出应用。
2. **无选择第一次 Ctrl+C** - 显示退出提示。
3. **无选择第二次 Ctrl+C** - 退出应用。
4. **请求运行中 Esc** - 取消当前 turn。

## v1 实现范围

1. ✅ 使用 Ink + React（chalk 着色）。
2. ✅ Markdown 渲染。
3. ✅ `!` bash mode、`/help`、权限面板。
4. ✅ 交互式 `/resume` 会话选择器。
5. 🔜 Agent 进度线（transcript 内显示 agent 执行结果）。
6. 🔜 工具调用折叠展示。
7. 🔜 Footer Agent Pills。
