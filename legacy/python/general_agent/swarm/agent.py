"""SwarmAgent — wraps an AgentLoop for a specific role with swarm communication.

Reference: ccswarm crates/ccswarm/src/agent/mod.rs (ClaudeCodeAgent)
"""

from __future__ import annotations

import asyncio
import logging
import time

from general_agent.agent.loop import AgentState, run_agent
from general_agent.swarm.types import (
    AgentDefinition,
    AgentIdentity,
    AgentStatus,
    AgentMessage,
    MessageType,
    TaskResult,
    TaskStatus,
    WhiteboardEntry,
)
from general_agent.swarm.whiteboard import Whiteboard

logger = logging.getLogger("general_agent.swarm.agent")


class SwarmAgent:
    """An agent instance that participates in a swarm.

    Wraps the core agent loop with:
    - Role-specific system prompt injection
    - Whiteboard for structured thinking
    - Message bus integration (pull messages before each turn)
    - Tool access scoped to role
    """

    def __init__(
        self,
        definition: AgentDefinition,
        session_id: str = "",
    ) -> None:
        self.identity = AgentIdentity(
            definition=definition,
            session_id=session_id,
        )
        self.whiteboard = Whiteboard(self.identity.agent_id)
        self._state: AgentState | None = None
        self._bus_queue: asyncio.Queue[AgentMessage] | None = None
        self._abort = asyncio.Event()
        self._task_start_time = 0.0

    # ---- properties ----

    @property
    def agent_id(self) -> str:
        return self.identity.agent_id

    @property
    def role(self) -> str:
        return self.identity.definition.role.kind

    @property
    def status(self) -> AgentStatus:
        return self.identity.status

    @status.setter
    def status(self, value: AgentStatus) -> None:
        self.identity.status = value

    # ---- lifecycle ----

    def set_bus_queue(self, queue: asyncio.Queue[AgentMessage]) -> None:
        self._bus_queue = queue

    async def initialize(self, tool_registry, git_context: str = "") -> None:
        """Set up the agent state with role-specific system prompt."""
        definition = self.identity.definition
        role_prompt = self._build_role_prompt(definition)

        self._state = AgentState(
            tool_registry=tool_registry,
            git_context=git_context,
            system_prompt_extra=role_prompt,
            max_turns=definition.max_turns,
        )
        self.status = AgentStatus.AVAILABLE
        logger.info("Agent %s (%s) initialized", self.agent_id, self.role)

    def _build_role_prompt(self, definition: AgentDefinition) -> str:
        role = definition.role
        personality = definition.personality
        parts: list[str] = []

        if definition.system_prompt:
            parts.append(definition.system_prompt)
        else:
            parts.append(f"You are a {role.kind} specialist.")
            if role.responsibilities:
                parts.append("Responsibilities: " + ", ".join(role.responsibilities))
            if role.boundaries:
                parts.append("Boundaries: " + ", ".join(role.boundaries))
            if role.technologies:
                parts.append("Technologies: " + ", ".join(role.technologies))

        # Personality
        parts.append(
            f"Communication style: formality={personality.formality:.1f}, "
            f"verbosity={personality.verbosity:.1f}, "
            f"directness={personality.directness:.1f}"
        )

        # Swarm-specific instructions
        parts.append(
            "\nYou are part of a swarm of agents. You can:\n"
            "- Share discoveries via your whiteboard\n"
            "- Request help from other agents\n"
            "- Read other agents' whiteboard entries\n"
            "- Vote on proposals when asked\n"
            "When you discover something useful to others, broadcast it."
        )

        return "\n".join(parts)

    # ---- task execution ----

    async def execute_task(self, task_description: str, task_id: str = "",
                           on_progress=None, on_text=None) -> TaskResult:
        """Run a single task and return the result."""
        if not self._state:
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                status=TaskStatus.FAILED,
                error="Agent not initialized",
            )

        self.status = AgentStatus.WORKING
        self._task_start_time = time.monotonic()

        # Build task prompt with swarm context
        prompt = self._build_task_prompt(task_description)
        self._state.messages.append({"role": "user", "content": prompt})

        try:
            # Use non-streaming for sub-agents to avoid nested-streaming
            # connection pool exhaustion with the parent agent.
            from general_agent.services.api.messages import query_model_without_streaming
            result = await query_model_without_streaming(
                messages=list(self._state.messages),
                system_prompt=self._state.system_prompt_extra,
                model="",  # use default
                max_tokens=4096,
                temperature=0.7,
            )
            content = result.get("content", [])
            result_text = ""
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        result_text += block.get("text", "")
            else:
                result_text = str(content)
            all_messages = list(self._state.messages) + [result]
            if result_text:
                self._state.messages.append({"role": "assistant", "content": result_text})

            duration_ms = int((time.monotonic() - self._task_start_time) * 1000)
            self.status = AgentStatus.AVAILABLE

            # Record conclusions to whiteboard
            if result_text:
                self.whiteboard.add_conclusion(result_text[:500], related_task=task_id)

            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                status=TaskStatus.COMPLETED,
                output=result_text,
                whiteboard=self.whiteboard.get_all(),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - self._task_start_time) * 1000)
            self.status = AgentStatus.ERROR
            logger.error("Agent %s task failed: %s", self.agent_id, e)
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                status=TaskStatus.FAILED,
                error=str(e),
                whiteboard=self.whiteboard.get_all(),
                duration_ms=duration_ms,
            )

    def _build_task_prompt(self, task_description: str) -> str:
        """Wrap the task description with swarm-specific context."""
        # Include relevant whiteboard entries from this agent
        discoveries = self.whiteboard.get_by_type("Discovery")
        discovery_text = ""
        if discoveries:
            discovery_text = "\nPrevious discoveries:\n" + "\n".join(
                f"- {d.content[:200]}" for d in discoveries[-5:]
            )

        return (
            f"Task: {task_description}\n"
            f"{discovery_text}\n"
            f"Complete this task as a {self.role} specialist. "
            f"If you need help from other agents, state what you need clearly."
        )

    # ---- cleanup ----

    def shutdown(self) -> None:
        self._abort.set()
        self.status = AgentStatus.SHUTTING_DOWN
        if self._state:
            self._state.messages.clear()
