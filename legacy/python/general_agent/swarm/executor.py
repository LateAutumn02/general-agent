"""Parallel executor — asyncio.gather + Semaphore for concurrent agent tasks.

Reference: ccswarm crates/ccswarm/src/subagent/parallel_executor.rs
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from general_agent.swarm.types import (
    ParallelExecutionResult,
    SwarmTask,
    TaskResult,
    TaskStatus,
)

logger = logging.getLogger("general_agent.swarm.executor")

DEFAULT_MAX_CONCURRENT = 5
DEFAULT_TIMEOUT_S = 300  # 5 minutes


class ParallelExecutor:
    """Execute multiple agent tasks concurrently with backpressure."""

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        default_timeout_s: float = DEFAULT_TIMEOUT_S,
        fail_fast: bool = False,
        collect_partial_on_timeout: bool = True,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.default_timeout_s = default_timeout_s
        self.fail_fast = fail_fast
        self.collect_partial_on_timeout = collect_partial_on_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(
        self,
        tasks: list[SwarmTask],
        executor_fn: Callable[[SwarmTask], Awaitable[TaskResult]],
    ) -> ParallelExecutionResult:
        """Execute multiple tasks in parallel with semaphore backpressure.

        Args:
            tasks: Tasks to execute.
            executor_fn: Async function (task) -> TaskResult.

        Returns:
            ParallelExecutionResult with per-task results and aggregate stats.
        """
        start = time.monotonic()

        async def _run_one(task: SwarmTask) -> TaskResult:
            async with self._semaphore:
                try:
                    result = await asyncio.wait_for(
                        executor_fn(task),
                        timeout=self.default_timeout_s,
                    )
                    return result
                except asyncio.TimeoutError:
                    logger.warning("Task %s timed out", task.task_id)
                    if self.collect_partial_on_timeout:
                        return TaskResult(
                            task_id=task.task_id,
                            status=TaskStatus.TIMED_OUT,
                            error="Timeout",
                        )
                    raise
                except Exception as e:
                    logger.error("Task %s failed: %s", task.task_id, e)
                    if self.fail_fast:
                        raise
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                    )

        # Run all tasks
        coros = [_run_one(t) for t in tasks]
        results: list[TaskResult] = []
        if self.fail_fast:
            results = await asyncio.gather(*coros)
        else:
            results = await asyncio.gather(*coros, return_exceptions=False)

        # Build aggregate result
        duration = int((time.monotonic() - start) * 1000)
        success = sum(1 for r in results if r.status == TaskStatus.COMPLETED)
        failed = sum(1 for r in results if r.status != TaskStatus.COMPLETED)

        return ParallelExecutionResult(
            task_results=results,
            total_duration_ms=duration,
            successful_count=success,
            failed_count=failed,
            status="Completed" if failed == 0 else "PartialFailure",
        )

    async def execute_strategy(
        self,
        tasks: list[SwarmTask],
        executor_fn: Callable[[SwarmTask], Awaitable[TaskResult]],
        strategy: str = "CollectAll",
    ) -> Any:
        """Execute and aggregate results according to a strategy."""
        result = await self.execute(tasks, executor_fn)

        if strategy == "FirstSuccess":
            for r in result.task_results:
                if r.status == TaskStatus.COMPLETED:
                    return r.output
            return None

        if strategy == "HighestConfidence":
            best = None
            best_score = -1.0
            for r in result.task_results:
                if r.quality_score > best_score:
                    best_score = r.quality_score
                    best = r.output
            return best

        if strategy == "MergeObjects":
            merged: dict[str, Any] = {}
            for r in result.task_results:
                if r.status == TaskStatus.COMPLETED:
                    try:
                        import json
                        data = json.loads(r.output)
                        if isinstance(data, dict):
                            merged.update(data)
                    except (json.JSONDecodeError, TypeError):
                        pass
            return merged if merged else None

        # CollectAll (default)
        return [r for r in result.task_results if r.status == TaskStatus.COMPLETED]


class AggregationStrategy:
    """Aggregation strategy constants (matching ccswarm)."""
    COLLECT_ALL = "CollectAll"
    MERGE_OBJECTS = "MergeObjects"
    FIRST_SUCCESS = "FirstSuccess"
    HIGHEST_CONFIDENCE = "HighestConfidence"
