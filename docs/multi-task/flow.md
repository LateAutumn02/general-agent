# Multi-task session manager flow

> TUI task session manager for user-created parallel work. This module is different from swarm orchestration and different from the `Agent` tool: it is a manual task/session surface opened from the default chat screen.

---

## Scope

The v1 scope is an in-process manual task session system:

1. The user presses Left Arrow, or runs `/tasks`, to open a task board.
2. The user presses `n` to create a task session with a prompt.
3. Each task owns an independent `AgentState` and message history.
4. Task sessions run independently from the main chat.
5. The task board groups rows into `Needs input`, `Working`, and `Completed`.
6. The user opens a task row to inspect and continue that task.

Non-goals for v1:

- Closing the terminal does not keep tasks alive.
- Tasks are not persisted across process restarts.
- Permission handling is minimal: task sessions can pause for `y/n`, but do not yet support the full reason/remember dialog.
- The task board is not a remote session daemon or CCR bridge.
- The main agent does not create rows by calling `Agent`.

This keeps the first version small and gives the user direct control of parallel task sessions.

---

## Reference Behavior

cc-haha exposes a task footer/panel where rows represent independent Claude sessions. The screenshot-like behavior is:

```text
1 awaiting input · 0 working · 1 completed

Needs input
 ✻ task title   current tool/activity   age

Completed
 ✻ task title   result summary · →      age

Each row is its own Claude session. Open one to see its work.
```

The Python implementation borrows the visible model and keyboard flow, but not the persistence model. cc-haha can have remote/daemon sessions that continue after the terminal closes. general-agent v1 tasks are asyncio tasks inside the current TUI process.

---

## Phase 1: Open Task Board

1. **Left Arrow opens board** - `TextualAgentApp.action_open_tasks()` pushes `TaskBoardScreen`.
2. **Slash command fallback** - `/tasks` opens the same board.
3. **Board reads registry** - Rows are loaded from the shared in-process `TaskRegistry`.
4. **Header summarizes counts** - The top area displays current model, cwd, and counts by state.
5. **Rows are grouped** - Groups are shown only when they contain tasks.

Keyboard behavior:

```text
Left Arrow   open task board from chat
N            create a new task session
Enter        open highlighted task session
R            refresh board
Right Arrow  return to previous screen
Esc          return to previous screen
```

---

## Phase 2: Create Task Session

1. **User presses N** - The board opens a small prompt dialog.
2. **User enters task prompt** - The first line becomes the task title if no explicit title is provided.
3. **TaskState is created** - The new row is stored in `TaskRegistry`.
4. **Task AgentState is created** - The task owns independent messages, abort signal, and turn counter.
5. **First user message is added** - The prompt is appended to the task message history.
6. **Background run starts** - The task session begins processing without blocking the task board.

The main chat is not modified by creating or running a task session.

---

## Phase 3: Task Execution

1. **Task moves to Working** - Status becomes `running`.
2. **Progress is captured** - `on_progress` updates `TaskState.activity` with the latest tool/status line.
3. **Streaming text is captured** - `on_text` updates the task detail streaming area and latest activity.
4. **Messages stay task-local** - Task messages do not enter the main chat.
5. **Permission must pause** - A tool permission request moves the task to `Needs input` until the user opens it and presses `y` or `n`; task sessions must not silently bypass tool confirmation.
6. **Completion updates state** - Successful completion writes `result`, `summary`, `messages`, `end_time`, and status `completed`.
7. **Failure updates state** - Exceptions write `error`, `summary`, `activity`, `end_time`, and status `failed`.

---

## Phase 4: Task Grouping

Task rows are derived from `TaskState`:

1. **Needs input** - Tasks waiting for the user to open them and continue, or tasks with queued `pending_messages`.
2. **Working** - Tasks with an active agent loop.
3. **Completed** - Completed, failed, or killed tasks.

The v1 implementation treats failed/killed as terminal rows under `Completed` because the visible board has only three sections. A later UI can split `Failed` into its own group if it becomes noisy.

---

## Phase 5: Task Session Detail

1. **Enter opens session** - The board pushes `TaskSessionScreen` for the selected row.
2. **Transcript is shown** - The task-local conversation is rendered.
3. **Activity is shown** - The latest tool/progress line is shown near the header.
4. **User can continue** - The bottom input sends another message to this task only.
5. **Task can rerun** - A follow-up message moves a completed task back to `working`.
6. **Large output is summarized** - Tool results and long assistant messages are truncated in the visible transcript to keep Textual responsive.
7. **Streaming is cleared** - The streaming preview is reset after each turn so no stale text remains above the input.
8. **Screen refreshes periodically** - The detail view follows live activity without manual refresh.

---

## Bottom Interaction Design

The default TUI keeps user interaction at the bottom of the screen:

1. **Permission prompts are bottom-anchored** - Tool approval appears near the input area, not at the top of the transcript.
2. **Prompt input is quiet** - The input line uses background `#343536` without a prominent border.
3. **Input text is muted** - Typed/placeholder text uses `#807B6E`.
4. **Session footer is below input** - Model and current working directory are shown below the input with model color `#F6D58B` and cwd color `#9FCF9B`.
5. **Transcript background stays black** - Chat content remains visually separate from the input/approval area.

---

## Phase 6: Main Chat Isolation

The main chat and task sessions are isolated. Creating a task does not append messages to the main chat. Running a task does not stream output into the main chat. Opening a task is like opening another session.

---

## v1 Simplified Flow

1. User opens the task board.
2. User creates a task from the board.
3. Task session starts an independent agent loop.
4. Board displays task status and activity.
5. Task session screen lets the user inspect and continue the task.

---

## Differences From cc-haha

| Area | cc-haha | general-agent v1 |
|---|---|---|
| Lifetime | Can use remote/daemon sessions | In-process asyncio tasks only |
| Close terminal | Some sessions can continue | Tasks stop with the TUI process |
| Storage | AppState plus transcript/task persistence paths | In-memory registry |
| Permission | Mature task/session permission routing | v1 can pause for input; full permission handoff is future work |
| UI entry | Footer/pill task panel | Left Arrow and `/tasks` |
| Creation | User/session orchestration, plus some tool-created tasks | User-created task sessions only |
| Detail | Full teammate/session transcript surfaces | Task-local transcript and prompt input |

---

## Future Work

1. Persist task metadata and transcript under `.glagent/tasks/`.
2. Resume running or terminal tasks on `/resume`.
3. Add a real permission workflow for task sessions.
4. Add task cancellation from the board.
5. Add per-task full transcript scrolling and search.
6. Add daemon/worker mode if terminal-close continuity becomes a product requirement.

---

## Reference Sources

- `reference/cc-haha/src/components/PromptInput/PromptInput.tsx`
- `reference/cc-haha/src/tasks/LocalAgentTask/LocalAgentTask.tsx`
- `reference/cc-haha/src/components/tasks/RemoteSessionProgress.tsx`
- `general_agent/tasks/task.py`
- `general_agent/ui/app.py`

> Last updated: 2026-06-16 | Reference source: local cc-haha reference tree and current general-agent dev
