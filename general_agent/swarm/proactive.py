"""Proactive Monitor — periodic health checks and autonomous task management.

Reference: ccswarm crates/ccswarm/src/orchestrator/proactive_master.rs
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from general_agent.swarm.coordinator import SwarmCoordinator

logger = logging.getLogger("general_agent.swarm.proactive")

MONITOR_INTERVAL_S = 30
STUCK_THRESHOLD_S = 15 * 60  # 15 minutes


class ProactiveMonitor:
    """Background monitor that checks agent health and unblocks tasks.

    Runs a periodic loop:
    - Heartbeat check: mark disconnected agents
    - Stuck detection: flag agents idle >15 min
    - Dependency resolution: auto-unblock ready tasks
    - Completion patterns: auto-create follow-up tasks
    """

    def __init__(self, coordinator: SwarmCoordinator) -> None:
        self._coordinator = coordinator
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the monitoring loop (background task)."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ProactiveMonitor started (interval=%ds)", MONITOR_INTERVAL_S)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.warning("ProactiveMonitor tick failed: %s", e)
            await asyncio.sleep(MONITOR_INTERVAL_S)

    async def _tick(self) -> None:
        """One monitoring cycle."""
        from general_agent.swarm.types import MessageType
        now = time.monotonic()

        # 1. Heartbeat / stuck detection (use SwarmAgent instances, not AgentIdentity)
        for aid, agent in list(self._coordinator._agent_instances.items()):
            status_val = agent.status.value
            if status_val in ("Error", "Disconnected", "ShuttingDown"):
                continue
            if status_val == "Working":
                if hasattr(agent, "_task_start_time"):
                    elapsed = now - agent._task_start_time  # type: ignore[attr-defined]
                    if elapsed > STUCK_THRESHOLD_S:
                        logger.warning("Agent %s appears stuck (%.0f min)", aid, elapsed / 60)
                        self._coordinator.message_bus.send_to(
                            aid, MessageType.STATUS_UPDATE,
                            {"status": "stuck_check", "elapsed_min": elapsed / 60},
                            sender_id="proactive",
                        )

        # 2. Dependency resolution
        ready = self._coordinator.dependency_graph.get_ready_tasks()
        if ready:
            logger.debug("ProactiveMonitor: %d tasks unblocked", len(ready))
            for task in ready:
                self._coordinator.message_bus.broadcast(
                    MessageType.STATUS_UPDATE,
                    {"status": "task_ready", "task_id": task.task_id},
                    sender_id="proactive",
                )

        # 3. Completion patterns: Development → auto-create Testing
        for task_result in self._coordinator.completed_tasks[-10:]:
            desc_lower = task_result.output.lower()
            dev_keywords = ["implement", "add ", "create ", "build "]
            test_keywords = ["test", "pytest", "jest", "unittest"]

            is_dev = any(kw in desc_lower for kw in dev_keywords)
            has_test = any(kw in desc_lower for kw in test_keywords)

            if is_dev and not has_test:
                existing_test = any(
                    "test" in t.description.lower()
                    for t in self._coordinator.active_tasks.values()
                )
                if not existing_test and self._coordinator._agent_instances:
                    logger.info("ProactiveMonitor: suggesting follow-up testing task")
                    self._coordinator.message_bus.broadcast(
                        MessageType.CUSTOM,
                        {
                            "type": "suggestion",
                            "message": f"Consider adding tests for: {task_result.output[:200]}",
                        },
                        sender_id="proactive",
                    )
