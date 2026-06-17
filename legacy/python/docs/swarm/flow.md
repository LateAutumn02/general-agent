# Swarm 蜂群多 Agent 系统 — 流程

> 对等通信的多 Agent 协作系统。Agent 间通过 Message Bus 互相通信和共享上下文，支持并行执行、民主投票、规则+LLM 混合任务分发、质量审查。

参考：ccswarm `src/orchestrator/`、`src/coordination/`、`src/agent/`、`src/subagent/parallel_executor.rs`、`src/orchestrator/proactive_master.rs`

---

## 架构总览

```
用户输入 ("给这个项目加用户认证")
  ↓
SwarmCoordinator
  ├─ DelegationEngine: 关键词+"前端"→Frontend, "数据库"→Backend
  │   无匹配 → LLM fallback 判断
  ├─ DependencyGraph: 前端依赖后端API → 先后端再前端
  ↓
Message Bus (asyncio.Queue + JSON持久化)
  ├─ broadcast: 广播进度/发现/警告
  ├─ point-to-point: HelpRequest, InterAgentMessage
  ↓
  Backend Agent ──→ Frontend Agent
    "API好了"        "收到，开始对接"
       ↓                ↓
  Quality Judge (LLM打分)
       ↓
  汇总输出给用户
```

### 与普通多 Agent (fork) 的区别

| | Fork (现有) | Swarm (本模块) |
|---|---|---|
| 拓扑 | 树形，主→子单向汇报 | 网状，Agent 间对等通信 |
| 上下文 | 隔离 | Message Bus 共享 |
| 分发 | 手动指定 Agent | 规则 + LLM 自动匹配 |
| 并行 | 串行等结果 | asyncio.gather + Semaphore |
| 共识 | 无 | Sangha 简单多数投票 |
| 质量 | 无 | LLM Judge 打分 |

---

## 阶段1：启动——Agent 发现与注册

1. **扫描 Agent 目录** — `<project>/.glagent/agents/` + `~/.glagent/agents/`
2. **解析 Agent 定义** — 每个子目录包含 `AGENT.md`（YAML frontmatter + markdown body）
3. **创建 SwarmCoordinator** — 单例，初始化 Message Bus、Delegate Engine、DependencyGraph、Proactive Monitor
4. **Agent 注册** — Agent 写入 `Registration` → Coordinator 分配 agent_id → 建立 Queue 通道
5. **健康检查启动** — Proactive Monitor 每 30s 发 Heartbeat，连续 3 次无响应标记 Disconnected

参考 ccswarm `channel_based.rs` `Orchestrator::run()` 事件循环。

## 阶段2：任务分析与分发

1. **接收任务** — 用户自然语言 + 可选优先级/截止时间
2. **规则匹配（第一层）** — `DelegationEngine` 遍历规则表：
   - 关键词匹配（"前端/UI/React" → Frontend，"数据库/API" → Backend，"部署/Docker" → DevOps，"测试/QA" → QA）
   - 多条命中 → 按 priority 排序，取最高分
3. **LLM fallback（第二层）** — 无规则命中时调用 LLM：
   - 输入：任务描述 + 可用 Agent 列表
   - 输出：target_role + confidence + reasoning
4. **依赖分析** — 检查 `DependencyGraph`：当前任务依赖哪些未完成的任务
5. **生成 TaskAssignment** — 点对点发送给目标 Agent

参考 ccswarm `master_delegation.rs` `DelegationRule` + `delegate_task()`。

## 阶段3：并行执行

1. **任务拆解** — 如果 LLM 判断需要多 Agent 协作，拆为子任务组
2. **拓扑排序** — 按依赖关系确定执行顺序，无依赖的并行执行
3. **Semaphore 限流** — `asyncio.Semaphore(max_concurrent)`，默认同时 5 个
4. **asyncio.gather 并行** — 独立的任务同时跑
5. **Agent 间通信（对等）**：
   - `HelpRequest` — "这个函数签名是什么？" → 收到请求的 Agent 回复
   - `StatusUpdate` — 广播进度给所有人
   - `InterAgentMessage` — 点对点发送具体信息
6. **Whiteboard** — 每个 Agent 维护一个结构化记录板（发现、假设、结论），可被其他 Agent 读取

参考 ccswarm `parallel_executor.rs` `execute_parallel()` + `buffer_unordered` 模式。

## 阶段4：质量审查

1. **LLM Judge** — 任务完成后，独立 LLM 调用评估结果：
   - 维度：完整性 / 正确性 / 风格一致性 / 安全性
   - 输出：0-1 分 + 具体建议
2. **低于阈值 → 自动修复** — 如果分数 < 0.6，生成修复任务重新分发给同一 Agent
3. **跨 Agent 一致性检查** — 如果两个 Agent 修改了同一文件，检查冲突
4. **汇总报告** — 所有结果 + 评分 + 建议，格式输出

参考 ccswarm `llm_quality_judge.rs` 的 8 维度评估。

## 阶段5：Sangha 共识投票

1. **发起提案** — `/swarm propose "用 Redis 替代内存缓存" "原因..."`
2. **广播** — Coordinator 通过 Message Bus 通知所有 Agent
3. **Agent 投票** — 每个 Agent 基于自己的专业领域投票：
   - Backend Agent 关心性能 → 同意
   - DevOps Agent 关心运维复杂度 → 反对
   - Frontend Agent 不关心 → 弃权
4. **简单多数判定** — >50% 同意 → 通过；平局 → LLM 打破平局
5. **执行** — 通过后自动分解为任务分发给相关 Agent

参考 ccswarm `sangha` 模块理念（它自己也是 stub）。

## 阶段6：Proactive 自主监控

1. **定时轮询** — 每 30s 一个循环：
   - 检查 stuck Agent（>15 分钟无活动） → 发送询问
   - 检查依赖是否满足 → 自动解除阻塞
   - 任务完成模式匹配：Development 完成 → 自动创建 Testing 任务
2. **低风险自动执行** — 置信度 >0.8 的决策自动执行，不需要用户确认
3. **高风险上报** — 置信度 <0.5 或影响范围大的决策，暂停并询问用户

参考 ccswarm `proactive_master.rs` `start_coordination()` 的 tokio::select 循环。

---

## v1 实现范围

| 功能 | 状态 | 说明 |
|------|------|------|
| Message Bus (广播+点对点+持久化) | ✅ | asyncio.Queue + JSON |
| 并行执行 (Semaphore+gather) | ✅ | |
| 规则匹配分发 | ✅ | 4 条硬编码规则 + 可扩展 |
| LLM fallback 分发 | ✅ | 无规则命中时调用 LLM |
| 依赖 DAG + 拓扑排序 | ✅ | |
| LLM Judge 质量审查 | ✅ | 4 维度打分 |
| Sangha 简单多数投票 | ✅ | >50% 通过 |
| Proactive 自主监控 | ✅ | 30s 定时器 |
| Whiteboard 记录板 | ✅ | 结构化 dict，Agent 可互读 |
| Agent 人格 | ✅ | 从 AGENT.md 读取 trait |
| ai-session/PTY | ❌ 置空 | 已有 tools/bash.py |
| 拜占庭容错共识 | ❌ 置空 | 需要多 LLM 实例，开销大且 ccswarm 也未实现 |
| 自我扩展 (Agent 提议新能力) | ❌ 置空 | 实现极其复杂，无参考 |

---

> 最后更新: 2026-05-31 | 参考源 commit: 467acb8 | 参考文件: ccswarm crates/ccswarm/src/orchestrator/, coordination/, agent/, subagent/parallel_executor.rs
