# Multi-task session manager data structures

> Core types and contracts for user-created TUI task sessions.

---

## TaskState

`TaskState` is the canonical in-memory record for a task session.

```
TaskState:
  id: str                       # Unique task id shown in task detail
  type: TaskType                # Task category, currently local_agent or local_bash
  status: TaskStatus            # Lifecycle state
  description: str              # Short row title from user-created task prompt
  start_time: float             # Unix timestamp when task was created
  end_time: float               # (optional) Unix timestamp when task reached terminal state
  error: str                    # (optional) Failure message
  tool_use_id: str              # (optional) Parent tool invocation id
  prompt: str                   # Full child-agent prompt
  agent_type: str               # (optional) Future named-agent type
  model: str                    # (optional) Future model override
  result: any                   # Full task result
  messages: list[dict]          # Child-agent conversation messages
  activity: str                 # Latest visible progress line for the board row
  summary: str                  # Short terminal result summary
  tool_use_count: int           # Number of tool calls used by the child agent
  total_input_tokens: int       # Accumulated input tokens when available
  total_output_tokens: int      # Accumulated output tokens when available
  pending_messages: list[str]   # Queued messages/input requests for Needs input
  runtime_state: any            # (optional) Live AgentState owned by this task session
  run_task: any                 # (optional) asyncio task for the active agent loop
  permission_request: dict      # (optional) Tool permission request waiting for y/n
```

---

## TaskType

```
TaskType:
  LOCAL_AGENT                  # Forked child agent task
  LOCAL_BASH                   # Reserved for background shell tasks
```

`LOCAL_BASH` exists in the base task model but is not part of this v1 feature.

---

## TaskStatus

```
TaskStatus:
  PENDING                      # Created but not yet running
  RUNNING                      # Currently executing
  COMPLETED                    # Finished successfully
  FAILED                       # Finished with error
  KILLED                       # Stopped by user/system
```

Terminal statuses:

```
TERMINAL_STATUS:
  completed
  failed
  killed
```

---

## TaskRegistry

`TaskRegistry` owns all in-process background task records.

```
TaskRegistry:
  create(task_type, **kwargs) -> TaskState       # Create and store a task
  get(task_id) -> TaskState                      # Look up one task
  update(task_id, **kwargs) -> TaskState         # Update non-terminal task fields
  complete(task_id, result, error) -> None       # Mark task completed or failed
  kill(task_id) -> None                          # Mark task killed
  list_running() -> list[TaskState]              # Return running tasks
  all() -> list[TaskState]                       # Return all tasks
  drain_pending_messages(task_id) -> list[str]   # Move pending messages out of a task
```

The shared process registry is accessed through:

```
get_task_registry() -> TaskRegistry
```

---

## AgentState Addition

The main agent state owns the registry used by the TUI and tools.

```
AgentState:
  task_registry: TaskRegistry    # Shared task store for task sessions and TUI board
  require_tool_confirmation: bool # TUI task sessions must ask before executing tools
```

User-created task sessions create their own `AgentState`. The main chat `AgentState` and task `AgentState` do not share messages.

---

## Task Session Creation Input

```
TaskSessionInput:
  prompt: str                    # First user message for the task session
  title: str                     # (optional) Short board row title
```

---

## Task Session Runtime

```
TaskSessionRuntime:
  task_state: TaskState          # Row metadata and transcript mirror
  agent_state: AgentState        # Independent agent loop state
  streaming_text: str            # Currently streaming assistant text, displayed as a truncated tail
  permission_request: dict       # (optional) Tool permission waiting for y/n
```

---

## TaskBoardScreen

```
TaskBoardScreen:
  task_registry: TaskRegistry    # Registry displayed by the board
  _refresh() -> None             # Rebuild header and grouped row options
  action_new_task() -> None      # Create a new user-managed task session
  action_open_task() -> None     # Open highlighted task session
  action_close() -> None         # Return to chat
```

Bindings:

```
left          # Open board from chat screen
/tasks        # Open board from chat screen
n             # Create a new task session
enter         # Open selected task detail
r             # Refresh board
right         # Close board
escape        # Close board
```

---

## TaskSessionScreen

```
TaskSessionScreen:
  task_state: TaskState          # Task record being inspected
  _run_task_turn(user_text) -> None  # Run one task-local agent turn
  _refresh() -> None             # Re-render status, transcript, and streaming output
  action_close() -> None         # Return to task board
```

Bindings:

```
r             # Refresh detail
enter         # Submit task-local input through PromptInput
y             # Approve waiting tool permission
n             # Deny waiting tool permission
right         # Close detail
escape        # Close detail
```

---

## Board Grouping

```
Needs input:
  status == pending OR pending_messages is not empty

Working:
  status == running AND pending_messages is empty

Completed:
  status in completed, failed, killed
```

The grouping is intentionally display-oriented. It does not introduce a new lifecycle status.

---

## Persistence Contract

v1 persistence contract:

```
Task storage:
  memory only

Process restart:
  tasks are lost

Terminal close:
  tasks stop
```

Future persistent storage should not overload session transcript JSONL directly. Prefer a task-specific path such as:

```
.glagent/tasks/<task_id>.jsonl
.glagent/tasks/<task_id>.json
```

---

> Last updated: 2026-06-16 | Reference source: `docs/multi-task/flow.md`
