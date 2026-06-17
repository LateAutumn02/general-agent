"""Task dependency graph with topological sort.

Reference: ccswarm crates/ccswarm/src/orchestrator/proactive_master.rs (DependencyGraph)
"""

from __future__ import annotations

from collections import defaultdict, deque

from general_agent.swarm.types import SwarmTask, TaskStatus


class DependencyGraph:
    """Directed acyclic graph of task dependencies.

    Tracks which tasks are blocked, which are ready, and provides
    topological ordering for parallel execution batches.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, SwarmTask] = {}
        # task_id → set of task_ids that depend on it
        self._dependents: dict[str, set[str]] = defaultdict(set)

    def add_task(self, task: SwarmTask) -> None:
        self._tasks[task.task_id] = task
        for dep_id in task.dependencies:
            self._dependents[dep_id].add(task.task_id)

    def remove_task(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)
        self._dependents.pop(task_id, None)
        for deps in self._dependents.values():
            deps.discard(task_id)

    def mark_completed(self, task_id: str) -> None:
        """Mark a task as completed — unblocks its dependents."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED

    def mark_failed(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
        # Dependents become blocked
        for dep_id in self._dependents.get(task_id, set()):
            dep_task = self._tasks.get(dep_id)
            if dep_task:
                dep_task.status = TaskStatus.BLOCKED

    # ---- query ----

    def get_ready_tasks(self) -> list[SwarmTask]:
        """Tasks whose dependencies are all completed (or no dependencies)."""
        ready: list[SwarmTask] = []
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            if self._dependencies_satisfied(task):
                ready.append(task)
        return ready

    def get_blocked_tasks(self) -> list[SwarmTask]:
        """Tasks with unsatisfied dependencies."""
        blocked: list[SwarmTask] = []
        for task in self._tasks.values():
            if task.status == TaskStatus.BLOCKED:
                blocked.append(task)
            elif task.status == TaskStatus.PENDING and not self._dependencies_satisfied(task):
                blocked.append(task)
        return blocked

    def _dependencies_satisfied(self, task: SwarmTask) -> bool:
        if not task.dependencies:
            return True
        return all(
            self._tasks.get(dep_id) and self._tasks[dep_id].status == TaskStatus.COMPLETED
            for dep_id in task.dependencies
        )

    # ---- topological sort ----

    def topological_batches(self) -> list[list[SwarmTask]]:
        """Return tasks grouped into parallel-executable batches.

        Batch 0 = tasks with no dependencies.
        Batch 1 = tasks whose deps are all in batch 0.
        etc.
        """
        # Build in-degree map (only counting PENDING/BLOCKED tasks)
        pending_ids = {t.task_id for t in self._tasks.values()
                       if t.status in (TaskStatus.PENDING, TaskStatus.BLOCKED)}
        in_degree: dict[str, int] = defaultdict(int)
        children: dict[str, list[str]] = defaultdict(list)

        for tid in pending_ids:
            task = self._tasks[tid]
            for dep_id in task.dependencies:
                if dep_id in pending_ids:
                    in_degree[tid] += 1
                    children[dep_id].append(tid)
            if tid not in in_degree:
                in_degree[tid] = 0

        # Kahn's algorithm
        queue = deque(tid for tid, deg in in_degree.items() if deg == 0 and tid in pending_ids)
        batches: list[list[SwarmTask]] = []
        visited: set[str] = set()

        while queue:
            batch: list[SwarmTask] = []
            for _ in range(len(queue)):
                tid = queue.popleft()
                if tid in visited:
                    continue
                visited.add(tid)
                batch.append(self._tasks[tid])
                for child_id in children.get(tid, []):
                    in_degree[child_id] -= 1
                    if in_degree[child_id] == 0:
                        queue.append(child_id)
            if batch:
                batches.append(batch)

        return batches

    def __len__(self) -> int:
        return len(self._tasks)
