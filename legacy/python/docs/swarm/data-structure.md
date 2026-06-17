# Swarm 蜂群 — 数据结构

> Swarm 多 Agent 系统的核心类型定义。完整覆盖 Message Bus、Agent、任务分发、质量审查、共识投票。

参考：ccswarm `coordination/mod.rs`、`agent/mod.rs`、`subagent/parallel_executor.rs`、`orchestrator/master_delegation.rs`、`orchestrator/proactive_master.rs`、`agent/whiteboard.rs`、`agent/personality.rs`

---

## AgentRole

Agent 角色枚举：

```
AgentRole:
  kind: 'Frontend' | 'Backend' | 'DevOps' | 'QA' | 'GeneralPurpose' | 'Master'
  technologies: list[str]         # 技术栈 ['React', 'TypeScript']
  responsibilities: list[str]     # 职责描述
  boundaries: list[str]           # 边界限制（不允许做的事）
```

---

## AgentPersonality

```
AgentPersonality:
  formality: float                # 0.0 随意 ~ 1.0 正式
  verbosity: float                # 0.0 简洁 ~ 1.0 详尽
  directness: float               # 0.0 委婉 ~ 1.0 直接
  creativity: float               # 0.0 保守 ~ 1.0 创新
  risk_tolerance: float           # 0.0 谨慎 ~ 1.0 大胆
```

参考 ccswarm `agent/personality.rs` `PersonalityTraits`。

---

## AgentDefinition

从 `.glagent/agents/<name>/AGENT.md` 加载：

```
AgentDefinition:
  name: str                       # Agent 名称（目录名）
  role: AgentRole                 # 角色
  personality: AgentPersonality   # 人格特质
  model: str                      # (可选) 指定模型，默认用全局
  system_prompt: str              # 角色系统提示词（body 部分）
  tools: list[str]                # 允许的工具列表，["all"] 表示全部
  auto_accept: bool               # 是否自动批准低风险工具调用
  risk_threshold: int             # (可选) 自动批准风险阈值 0-10
  max_turns: int                  # (可选) 每任务最大轮次，默认 20
```

参考 ccswarm `ccswarm.json` 的 agent 配置段。

---

## AgentIdentity

运行实例标识：

```
AgentIdentity:
  agent_id: str                   # UUID
  definition: AgentDefinition     # 指向定义
  session_id: str                 # swarm 会话 ID
  started_at: str                 # ISO 8601
  status: AgentStatus             # 当前状态
```

---

## AgentStatus

```
AgentStatus:
  'Initializing' | 'Available' | 'Working' | 'WaitingForHelp'
  | 'WaitingForReview' | 'Error' | 'Disconnected' | 'ShuttingDown'
```

---

## WhiteboardEntry

Agent 结构化思考记录，可被其他 Agent 读取：

```
WhiteboardEntry:
  entry_id: str                   # UUID
  agent_id: str                   # 作者
  entry_type: 'Discovery' | 'Hypothesis' | 'Decision' | 'Question'
             | 'TodoList' | 'ComparisonTable' | 'Conclusion'
  content: str                    # 内容
  annotations: list[str]          # (可选) 注释
  related_task: str               # (可选) 关联 task_id
  visible_to: list[str]           # (可选) 可见性，默认所有 Agent
  created_at: str                 # ISO 8601
```

参考 ccswarm `agent/whiteboard.rs` `WhiteboardEntry` + `EntryType`。

---

## SwarmTask

```
SwarmTask:
  task_id: str                    # UUID
  description: str                # 自然语言描述
  priority: 'Low' | 'Normal' | 'High' | 'Critical'
  target_role: str                # (可选) 指定角色，不指定则自动匹配
  dependencies: list[str]         # 依赖的 task_id
  deadline: str                   # (v1置空) 截止时间
  status: TaskStatus
  created_at: str                 # ISO 8601
  completed_at: str               # (可选) ISO 8601
```

---

## TaskStatus

```
TaskStatus:
  'Pending' | 'Blocked' | 'Running' | 'Completed' | 'Failed' | 'Cancelled' | 'TimedOut'
```

---

## TaskResult

```
TaskResult:
  task_id: str
  agent_id: str
  status: TaskStatus
  output: str                     # Agent 最终回复文本
  artifacts: list[str]            # 产生的文件路径等
  whiteboard: list[WhiteboardEntry]  # Agent 记录板
  quality_score: float            # (可选) LLM Judge 打分 0.0-1.0
  error: str                      # (可选) 错误信息
  duration_ms: int
  retries: int
```

---

## ParallelExecutionResult

```
ParallelExecutionResult:
  execution_id: str               # 批次 ID
  status: 'Completed' | 'PartialFailure' | 'Timeout' | 'Cancelled'
  task_results: list[TaskResult]
  total_duration_ms: int
  successful_count: int
  failed_count: int
  quality_report: QualityReport   # (可选)
```

---

## QualityReport

LLM Judge 报告：

```
QualityReport:
  overall_score: float                    # 0.0-1.0
  dimensions:
    completeness: float                   # 是否完整覆盖需求
    correctness: float                    # 逻辑/代码是否正确
    style_consistency: float              # 风格是否统一
    security: float                       # 是否有安全隐患
  suggestions: list[str]                  # 改进建议
  conflicts: list[ConflictInfo]           # (可选) Agent 间冲突

ConflictInfo:
  file_path: str
  agent_a: str
  agent_b: str
  description: str
```

参考 ccswarm `llm_quality_judge.rs` 的 8 维度评估（v1 精简为 4 维）。

---

## AgentMessage

Message Bus 上的消息：

```
AgentMessage:
  msg_id: str                     # UUID
  msg_type: MessageType
  sender_id: str
  recipient_id: str               # None = 广播
  payload: any                    # 消息内容，依 msg_type 而异
  timestamp: str                  # ISO 8601
  priority: 'Low' | 'Normal' | 'High' | 'Critical'

MessageType:
  'Registration'                  # payload: AgentDefinition
  'TaskAssignment'                # payload: SwarmTask
  'TaskProgress'                  # payload: {task_id, pct_complete, summary}
  'TaskCompleted'                 # payload: TaskResult
  'HelpRequest'                   # payload: {question, context}
  'HelpResponse'                  # payload: {answer, references}
  'StatusUpdate'                  # payload: {status, message}
  'Heartbeat'                     # payload: {agent_id, timestamp}
  'InterAgentMessage'             # payload: {content}
  'WhiteboardUpdate'              # payload: WhiteboardEntry
  'QualityIssue'                  # payload: {task_id, score, issue}
  'SanghaProposal'                # payload: SanghaProposal
  'SanghaVote'                    # payload: SanghaVote
  'Custom'                        # payload: {type, data}
```

参考 ccswarm `coordination/mod.rs` `AgentMessage` 枚举。

---

## MessageBus

```
MessageBus:
  channels: dict[str, asyncio.Queue]     # Agent → 消息队列
  history: list[AgentMessage]            # 最多 2000 条
  persistence_file: str                  # JSON 文件路径

  register(agent_id) -> asyncio.Queue
  unregister(agent_id)
  send(msg: AgentMessage)               # 若 recipient_id=None → 广播
  get_messages(agent_id) -> list[AgentMessage]  # 拉取+清空
  get_history(since) -> list[AgentMessage]      # 查询历史
  persist_to_disk()                      # 每 50 条自动触发
  load_from_disk()                       # 恢复时调用
```

参考 ccswarm `coordination/mod.rs` `CoordinationBus` + `ai_message_bus.rs`。

---

## DelegationRule

任务分发规则：

```
DelegationRule:
  name: str                        # 规则名称
  priority: int                    # 数值越大越优先
  keywords: list[str]              # 关键词
  target_role: str                 # 目标角色
  conditions: list[DelegationCondition]  # (可选) 附加条件

DelegationCondition:
  field: str                       # 匹配字段 'description' | 'priority' | 'task_type'
  op: 'contains' | 'equals' | 'above' | 'below'
  value: str | int
```

---

## DelegationDecision

```
DelegationDecision:
  task_id: str
  target_role: str
  confidence: float                # 0.0-1.0
  reasoning: str                   # 为什么选这个
  source: 'rule' | 'llm'          # 决策来源
```

---

## DependencyGraph

```
DependencyGraph:
  nodes: dict[str, TaskNode]       # task_id → node
  edges: list[tuple[str, str]]     # (from_task_id, to_task_id)

  add_task(task: SwarmTask)
  remove_task(task_id)
  get_ready_tasks() -> list[SwarmTask]     # 依赖全部满足的
  get_blocked_tasks() -> list[SwarmTask]   # 有未满足依赖的
  topological_order() -> list[list[str]]   # 按层级排列的 task_id 组
```

参考 ccswarm `orchestrator/proactive_master.rs` `DependencyGraph`。

---

## SanghaProposal / SanghaVote

```
SanghaProposal:
  proposal_id: str                 # UUID
  title: str
  description: str
  proposer_id: str                 # agent_id 或 'user'
  status: 'Open' | 'Voting' | 'Passed' | 'Rejected'
  votes: list[SanghaVote]
  deadline: str                    # ISO 8601（默认 5 分钟）
  created_at: str

SanghaVote:
  agent_id: str
  vote: 'Approve' | 'Reject' | 'Abstain'
  reason: str                      # 投票理由
  weight: float                    # 投票权重（默认 1.0）
  timestamp: str
```

---

## SwarmCoordinator

核心主控：

```
SwarmCoordinator:
  agents: dict[str, AgentIdentity]
  message_bus: MessageBus
  delegation_engine: MasterDelegationEngine
  dependency_graph: DependencyGraph
  task_queue: asyncio.PriorityQueue
  active_tasks: dict[str, SwarmTask]
  completed_tasks: list[TaskResult]
  quality_judge: QualityJudge
  proactive_monitor: ProactiveMonitor
  max_concurrent: int                      # 默认 5
  semaphore: asyncio.Semaphore

  # Lifecycle
  start()                                  # 启动 Coordinator 和 Proactive Monitor
  shutdown()                               # 通知所有 Agent，持久化消息

  # Task management
  submit_task(description, *, priority, target_role, dependencies) -> str
  submit_tasks(tasks: list) -> list[str]   # 批量提交，自动并行
  execute_parallel(tasks) -> ParallelExecutionResult

  # Agent management
  register_agent(definition: AgentDefinition) -> str  # 返回 agent_id
  unregister_agent(agent_id)

  # Query
  get_status() -> dict                     # swarm 概览
  get_agent_status(agent_id) -> dict       # 单个 Agent 详情
  get_task_status(task_id) -> TaskStatus

  # Sangha
  propose(title, description) -> str       # 返回 proposal_id
  vote(proposal_id, vote, reason)          # Agent 投票
```

---

## 文件结构

```
general_agent/swarm/
  __init__.py              # 模块入口 + 快捷函数
  types.py                 # 所有类型定义
  message_bus.py           # MessageBus 实现
  coordinator.py           # SwarmCoordinator 实现
  agent.py                 # SwarmAgent 类
  delegation.py            # MasterDelegationEngine
  dependency.py            # DependencyGraph + 拓扑排序
  executor.py              # 并行执行器
  quality.py               # LLM Judge 质量审查
  sangha.py                # 共识投票
  proactive.py             # Proactive Monitor 自主监控
  whiteboard.py            # Agent 记录板
  loader.py                # Agent 定义加载
```

---

> 最后更新: 2026-05-31 | 参考源 commit: 467acb8 | 参考文件: ccswarm crates/ccswarm/src/ (coordination/, agent/, orchestrator/, subagent/)
