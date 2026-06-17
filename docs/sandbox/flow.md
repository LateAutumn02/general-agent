# 沙箱安全流程

> 最后更新：2026-06-17 | 参考：legacy/python/docs/sandbox, reference/cc-haha/src/utils/permissions

## 阶段1：安全边界建立

1. **确定工作目录** - 默认只信任启动 cwd 和显式 `--add-dir`。
2. **解析路径** - 所有文件工具先 canonicalize，再判断是否在允许目录。
3. **识别危险命令** - Bash/PowerShell 根据命令前缀和 shell 语法判断是否必须审批。

## 阶段2：运行时保护

1. **文件工具保护** - Read/Edit/Write 不能越过允许目录。
2. **Shell 工具保护** - 命令执行前进入权限系统。
3. **网络工具保护** - WebFetch/WebSearch 后续单独设策略。

## 阶段3：错误反馈

1. **拒绝原因明确** - 告诉模型是路径越界、权限拒绝还是命令危险。
2. **不吞错误** - 原始 stderr 和结构化错误都保留。
3. **用户可改策略** - 通过权限面板或配置增加允许目录。

## v1 简化流程

1. 路径沙箱先做。
2. Shell 权限默认 ask。
3. 真正 OS sandbox 后置。

