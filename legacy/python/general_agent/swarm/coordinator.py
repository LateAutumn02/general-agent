"""SwarmCoordinator — central orchestrator for the swarm.

Integrates MessageBus, DelegationEngine, DependencyGraph, ParallelExecutor,
QualityJudge, Sangha, and ProactiveMonitor.

Reference: ccswarm crates/ccswarm/src/orchestrator/channel_based.rs (Orchestrator)
           + proactive_master.rs (ProactiveMaster coordination loop)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from general_agent.swarm.types import (
    AgentDefinition,
    AgentIdentity,
    AgentMessage,
    AgentStatus,
    DelegationDecision,
    MessageType,
    ParallelExecutionResult,
    QualityReport,
    SanghaProposal,
    SwarmTask,
    TaskResult,
    TaskStatus,
)
from general_agent.swarm.message_bus import MessageBus
from general_agent.swarm.delegation import MasterDelegationEngine, DEFAULT_RULES
from general_agent.swarm.dependency import DependencyGraph
from general_agent.swarm.executor import ParallelExecutor
from general_agent.swarm.quality import QualityJudge
from general_agent.swarm.sangha import Sangha
from general_agent.swarm.proactive import ProactiveMonitor
from general_agent.swarm.agent import SwarmAgent
from general_agent.swarm.loader import scan_agent_dirs
from general_agent.swarm.tracer import SwarmTracer

logger = logging.getLogger("general_agent.swarm.coordinator")


class SwarmCoordinator:
    """Central orchestrator for a swarm of agents.

    Usage:
        coord = SwarmCoordinator(project_root=".")
        coord.start()
        task_id = coord.submit_task("Build a login page")
        status = coord.get_task_status(task_id)
        coord.shutdown()
    """

    def __init__(
        self,
        project_root: str = "",
        max_concurrent: int = 5,
        custom_rules: list | None = None,
    ) -> None:
        self.project_root = project_root or os.getcwd()

        # Core subsystems
        self.message_bus = MessageBus(
            persistence_file=os.path.join(
                self.project_root, ".glagent", "swarm", "messages.jsonl",
            )
        )
        self.delegation_engine = MasterDelegationEngine(rules=custom_rules)
        self.dependency_graph = DependencyGraph()
        self.executor = ParallelExecutor(max_concurrent=max_concurrent)
        self.quality_judge = QualityJudge()
        self.sangha = Sangha()
        self.tracer = SwarmTracer()

        # Agent registry
        self._agent_definitions: list[AgentDefinition] = []
        self._agent_instances: dict[str, SwarmAgent] = {}
        self._tool_registry = None

        # Task tracking
        self.active_tasks: dict[str, SwarmTask] = {}
        self.completed_tasks: list[TaskResult] = []

        # Proactive monitor
        self._proactive = ProactiveMonitor(self)

        # State
        self._started = False

    # ---- properties ----

    @property
    def agents(self) -> dict[str, AgentIdentity]:
        return {aid: a.identity for aid, a in self._agent_instances.items()}

    @property
    def agent_definitions(self) -> list[AgentDefinition]:
        return list(self._agent_definitions)

    # ---- lifecycle ----

    def start(self) -> None:
        """Initialize the swarm: load agents, register on bus, start monitor."""
        if self._started:
            return

        # Load agent definitions
        self._agent_definitions = scan_agent_dirs(self.project_root)

        # Restore message history
        loaded = self.message_bus.load_from_disk()
        if loaded:
            logger.info("Restored %d messages from disk", len(loaded))

        # Start proactive monitor (background, fire-and-forget)
        try:
            loop = asyncio.get_running_loop()
            self._monitor_task = loop.create_task(self._proactive.start())
        except RuntimeError:
            pass  # No event loop — monitor will start on first async call

        self._started = True
        logger.info(
            "SwarmCoordinator started with %d agent types, %d rules",
            len(self._agent_definitions),
            len(self.delegation_engine.rules),
        )

    async def shutdown(self) -> None:
        """Graceful shutdown: stop monitor, persist, cleanup agents."""
        await self._proactive.stop()

        for agent in self._agent_instances.values():
            agent.shutdown()

        self.message_bus.persist_to_disk()
        self._started = False
        logger.info("SwarmCoordinator shut down")

    # ---- task submission ----

    async def submit_task(
        self,
        description: str,
        *,
        priority: str = "Normal",
        target_role: str = "",
        dependencies: list[str] | None = None,
        dynamic: bool = True,       # True = LLM decomposes & creates agents
        on_progress=None,
        on_text=None,
    ) -> TaskResult | list[TaskResult]:
        """Submit a task to the swarm, execute it, return the result.

        If dynamic=True (default), the LLM decomposes the task and dynamically
        creates the agents it needs. If dynamic=False, uses rule-based matching
        against existing agent definitions.

        Multi-agent tasks are executed in dependency order, with independent
        agents running in parallel.
        """
        if not self._started:
            self.start()

        task = SwarmTask(
            description=description,
            priority=priority,
            target_role=target_role,
            dependencies=dependencies or [],
        )
        self.active_tasks[task.task_id] = task

        # ── Dynamic mode: LLM decomposes & creates agents ──
        if dynamic:
            definitions = await self.delegation_engine.decompose_and_create(description)
            self.tracer.emit(
                event_type="delegation",
                task_id=task.task_id,
                description=f"LLM created {len(definitions)} agent(s): "
                            f"{', '.join(f'{d.name}({d.role.kind})' for d in definitions)}",
            )

            if len(definitions) == 1:
                # Single agent — simple execution
                agent = await self._create_agent(definitions[0])
                task.status = TaskStatus.RUNNING
                sub_task = getattr(definitions[0], "_sub_task", description)
                self.tracer.task_start(agent.agent_id, agent.role, task.task_id, sub_task)
                result = await agent.execute_task(
                    sub_task, task_id=task.task_id,
                    on_progress=on_progress,
                    on_text=on_text,
                )
                self.tracer.task_end(agent.agent_id, agent.role, task.task_id, result)
                self._finish_task(task, result)
                return result
            else:
                # Multi-agent — execute in dependency order
                return await self._execute_multi_agent(
                    definitions, task,
                    on_progress=on_progress,
                    on_text=on_text,
                )

        # ── Static mode: rule-based matching ──
        decision = await self.delegation_engine.delegate(task, self._agent_definitions)
        self.tracer.delegation(task.task_id, decision.target_role, decision.source, decision.confidence)

        agent = await self._get_or_create_agent(decision.target_role)
        if not agent:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=f"No agent available for role: {decision.target_role}",
            )

        task.status = TaskStatus.RUNNING
        self.tracer.task_start(agent.agent_id, agent.role, task.task_id, description)
        result = await agent.execute_task(description, task_id=task.task_id)
        self.tracer.task_end(agent.agent_id, agent.role, task.task_id, result)
        self._finish_task(task, result)
        return result

    async def _execute_multi_agent(
        self, definitions: list[AgentDefinition], task: SwarmTask,
        on_progress=None, on_text=None,
    ) -> list[TaskResult]:
        """Execute multiple agents in dependency order with context sharing.

        After each agent completes, its whiteboard entries are injected into
        dependent agents' prompts so they can "read" what previous agents found.
        This simulates inter-agent communication in sequential mode.
        """
        dep_map: dict[str, list[str]] = {}
        for d in definitions:
            dep_map[d.name] = getattr(d, "_depends_on", []) or []

        completed: dict[str, TaskResult] = {}
        remaining = {d.name: d for d in definitions}
        results: list[TaskResult] = []

        # Collect shared context from completed agents
        shared_context: list[str] = []

        while remaining:
            # Find agents whose deps are satisfied
            ready_names = [
                name for name, d in remaining.items()
                if all(dep in completed for dep in dep_map.get(name, []))
            ]
            if not ready_names:
                logger.error("Circular dependency in agent definitions")
                break

            ready_defs = [remaining.pop(name) for name in ready_names]
            task.status = TaskStatus.RUNNING

            async def _run_one(d: AgentDefinition) -> TaskResult:
                try:
                    agent = await self._create_agent(d)
                    sub_task = getattr(d, "_sub_task", task.description)

                    # Inject shared context from previous agents
                    if shared_context and getattr(d, "_depends_on", None):
                        ctx = "\n".join(shared_context[-3:])
                        agent._state.messages.append({
                            "role": "user",
                            "content": f"[CONTEXT FROM OTHER AGENTS]\n{ctx}\nUse this to avoid duplicate work.",
                        })

                    self.tracer.task_start(agent.agent_id, agent.role, task.task_id, sub_task)
                    result = await agent.execute_task(
                        sub_task, task_id=task.task_id,
                        on_progress=on_progress,
                        on_text=on_text,
                    )
                    self.tracer.task_end(agent.agent_id, agent.role, task.task_id, result)

                    if result.output:
                        shared_context.append(f"[{agent.role}] {result.output[:300]}")
                    for wb in result.whiteboard:
                        if wb.entry_type in ("Discovery", "Conclusion"):
                            shared_context.append(f"[{agent.role}:{wb.entry_type}] {wb.content[:200]}")

                    return result
                except Exception as exc:
                    logger.exception("Agent %s crashed", d.name)
                    return TaskResult(task_id=task.task_id, status=TaskStatus.FAILED, error=str(exc))

            coros = [_run_one(d) for d in ready_defs]
            batch_results = await asyncio.gather(*coros)

            for d, r in zip(ready_defs, batch_results):
                r.task_id = task.task_id
                completed[d.name] = r
                results.append(r)

        for r in results:
            self._finish_task(task, r)
        return results

    def _finish_task(self, task: SwarmTask, result: TaskResult) -> None:
        """Bookkeeping after a task completes."""
        # Quality review
        try:
            report = self.quality_judge.review_sync(result)
            result.quality_score = report.overall_score
            self.tracer.quality(task.task_id, report.overall_score, report.suggestions)
        except Exception:
            pass

        task.status = result.status
        task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.active_tasks.pop(task.task_id, None)
        self.completed_tasks.append(result)
        self.dependency_graph.mark_completed(task.task_id)

        # Persist full trace to disk
        trace_dir = os.path.join(self.project_root, ".glagent", "swarm", "traces")
        trace_file = os.path.join(trace_dir, f"{task.task_id}.json")
        self.tracer.save_to_file(trace_file)

    async def submit_tasks(self, tasks: list[dict[str, Any]]) -> list[TaskResult]:
        """Submit multiple tasks. They execute in parallel batches."""
        results: list[TaskResult] = []
        for t in tasks:
            result = await self.submit_task(
                description=t["description"],
                priority=t.get("priority", "Normal"),
                target_role=t.get("target_role", ""),
                dependencies=t.get("dependencies", []),
            )
            # submit_task may return list[TaskResult] for multi-agent
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        return results

    # ---- parallel execution ----

    async def execute_parallel(
        self, task_descriptions: list[str],
    ) -> ParallelExecutionResult:
        """Execute multiple independent tasks in parallel across agents."""
        tasks = [SwarmTask(description=d) for d in task_descriptions]
        for t in tasks:
            self.active_tasks[t.task_id] = t

        async def _run(task: SwarmTask) -> TaskResult:
            decision = await self.delegation_engine.delegate(task, self._agent_definitions)
            agent = await self._get_or_create_agent(decision.target_role)
            if not agent:
                return TaskResult(task_id=task.task_id, status=TaskStatus.FAILED, error="No agent available")
            task.status = TaskStatus.RUNNING
            result = await agent.execute_task(task.description, task_id=task.task_id)
            task.status = result.status
            task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.completed_tasks.append(result)
            self.dependency_graph.mark_completed(task.task_id)
            return result

        result = await self.executor.execute(tasks, _run)

        # Quality review
        try:
            report = await self.quality_judge.review(
                result.task_results[0] if result.task_results else TaskResult(task_id=""),
            )
            result.quality_report = report
        except Exception:
            pass

        return result

    # ---- agent management ----

    async def _get_or_create_agent(self, role_kind: str) -> SwarmAgent | None:
        """Get an available agent of the given role, or create one."""
        # Find existing available agent
        for agent in self._agent_instances.values():
            if agent.role == role_kind and agent.status == AgentStatus.AVAILABLE:
                return agent

        # Create new agent
        definition = None
        for d in self._agent_definitions:
            if d.role.kind == role_kind:
                definition = d
                break
        if not definition:
            logger.warning("No agent definition for role: %s", role_kind)
            return None

        return await self._create_agent(definition)

    async def _create_agent(self, definition: AgentDefinition) -> SwarmAgent:
        """Initialize a new agent instance and register it."""
        from general_agent.tools.factory import create_registry

        session_id = os.path.basename(self.message_bus._persist_file or "swarm")  # noqa: SLF001

        agent = SwarmAgent(definition=definition, session_id=session_id)

        # Register on bus
        q = self.message_bus.register(agent.agent_id)
        agent.set_bus_queue(q)

        # Create tool registry scoped to this agent's role
        registry = create_registry()
        agent._tool_registry = registry  # noqa: SLF001

        await agent.initialize(registry)

        # Send registration message
        self.message_bus.send(AgentMessage(
            msg_type=MessageType.REGISTRATION,
            sender_id=agent.agent_id,
            payload={"role": agent.role, "definition": definition.name},
        ))

        self._agent_instances[agent.agent_id] = agent
        self.tracer.agent_create(agent.agent_id, agent.role)
        return agent

    def register_agent(self, definition: AgentDefinition) -> str:
        """Register an agent definition and create its instance."""
        self._agent_definitions.append(definition)
        # Create synchronously (non-async fallback)
        agent_id = definition.name
        return agent_id

    def unregister_agent(self, agent_id: str) -> None:
        agent = self._agent_instances.pop(agent_id, None)
        if agent:
            agent.shutdown()
        self.message_bus.unregister(agent_id)

    # ---- query ----

    def get_status(self) -> dict[str, Any]:
        return {
            "started": self._started,
            "agent_count": len(self._agent_instances),
            "agent_definitions": len(self._agent_definitions),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "agents": [
                {"id": aid[:8], "role": a.role, "status": a.status.value}
                for aid, a in self._agent_instances.items()
            ],
            "ready_tasks": len(self.dependency_graph.get_ready_tasks()),
            "blocked_tasks": len(self.dependency_graph.get_blocked_tasks()),
        }

    def get_agent_status(self, agent_id: str) -> dict[str, Any] | None:
        agent = self._agent_instances.get(agent_id)
        if not agent:
            return None
        return {
            "agent_id": agent.agent_id,
            "role": agent.role,
            "status": agent.status.value,
            "whiteboard_entries": len(agent.whiteboard),
        }

    def get_task_status(self, task_id: str) -> TaskStatus | None:
        task = self.active_tasks.get(task_id)
        return task.status if task else None

    # ---- sangha integration ----

    def propose(self, title: str, description: str) -> SanghaProposal:
        proposal = self.sangha.propose(title, description, "user")
        self.message_bus.broadcast(
            MessageType.SANGHA_PROPOSAL,
            {"proposal_id": proposal.proposal_id, "title": title, "description": description},
            sender_id="coordinator",
        )
        return proposal

    def vote(self, proposal_id: str, agent_id: str, vote: str, reason: str = "") -> None:
        self.sangha.vote(proposal_id, agent_id, vote, reason)
        self.message_bus.broadcast(
            MessageType.SANGHA_VOTE,
            {"proposal_id": proposal_id, "agent_id": agent_id, "vote": vote},
            sender_id=agent_id,
        )
