# 权限审批流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/sandbox, reference/cc-haha/src/components/permissions

## 阶段1：权限请求生成

1. **工具声明权限需求** - 工具根据输入生成 PermissionCheck。
2. **策略匹配** - PermissionController 匹配 allow/deny/ask 规则。
3. **自动决策** - 命中 allow/deny 时直接返回，不打扰用户。

## 阶段2：用户审批

1. **底部面板显示** - 展示工具名、原因、命令或 diff 预览。
2. **Yes** - 只允许本次调用。
3. **Yes, don't ask again** - 生成作用域受限的持久或会话规则。
4. **No** - 拒绝调用，并允许用户输入补充说明。

## 阶段3：规则更新

1. **命令前缀规则** - Bash/PowerShell 使用安全前缀而不是整段复杂 shell。
2. **目录规则** - Read/Edit/Write 使用项目内路径规则。
3. **会话规则** - 默认只在当前 session 内生效，持久规则需要明确标记。

## v1 简化流程

1. 默认 ask。
2. 支持 session 内 allow always。
3. 支持 deny reason 回填给 agent。
4. 持久权限文件后置。

