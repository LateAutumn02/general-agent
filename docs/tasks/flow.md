# 后台任务流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/multi-task, reference/cc-haha/src/tasks/LocalShellTask

## 阶段1：任务创建

1. **用户手动创建** - 在任务面板按快捷键创建独立任务。
2. **Shell 自动后台化** - 长时间运行的 shell command 可切到 background。
3. **Agent 子任务** - 多 agent 后续可以注册为 task。

## 阶段2：任务运行

1. **任务独立状态** - 每个任务有 status、activity、messages、output。
2. **持续更新 UI** - 主 footer 显示 awaiting/running/completed 数量。
3. **需要输入时暂停** - 权限请求或 agent 提问会把任务置为 awaiting input。

## 阶段3：任务查看

1. **任务面板** - 左箭头打开任务列表。
2. **任务详情** - Enter 打开单个任务，查看 transcript 和输出。
3. **任务继续** - 用户可以给 paused/completed task 追加输入重新运行。

## v1 简化流程

1. 用户手动任务。
2. Bash background task。
3. 任务状态只保存在当前进程，持久化后置。

