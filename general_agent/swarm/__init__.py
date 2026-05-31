"""Swarm — multi-agent orchestration with peer-to-peer communication.

Usage:
    from general_agent.swarm import SwarmCoordinator

    coord = SwarmCoordinator(project_root=".")
    coord.start()
    task_id = await coord.submit_task("Add user authentication")
    status = coord.get_task_status(task_id)
    await coord.shutdown()
"""

from general_agent.swarm.types import (
    AgentDefinition,
    AgentIdentity,
    AgentMessage,
    AgentPersonality,
    AgentRole,
    AgentStatus,
    DelegationDecision,
    DelegationRule,
    MessageType,
    ParallelExecutionResult,
    QualityReport,
    SanghaProposal,
    SanghaVote,
    SwarmTask,
    TaskResult,
    TaskStatus,
    WhiteboardEntry,
)
from general_agent.swarm.message_bus import MessageBus
from general_agent.swarm.delegation import MasterDelegationEngine, DEFAULT_RULES
from general_agent.swarm.dependency import DependencyGraph
from general_agent.swarm.executor import ParallelExecutor
from general_agent.swarm.quality import QualityJudge
from general_agent.swarm.sangha import Sangha
from general_agent.swarm.proactive import ProactiveMonitor
from general_agent.swarm.agent import SwarmAgent
from general_agent.swarm.whiteboard import Whiteboard
from general_agent.swarm.loader import scan_agent_dirs, BUILTIN_AGENTS
from general_agent.swarm.coordinator import SwarmCoordinator

__all__ = [
    # Coordinator
    "SwarmCoordinator",
    # Core subsystems
    "MessageBus",
    "MasterDelegationEngine",
    "DependencyGraph",
    "ParallelExecutor",
    "QualityJudge",
    "Sangha",
    "ProactiveMonitor",
    "SwarmAgent",
    "Whiteboard",
    # Types
    "AgentDefinition",
    "AgentIdentity",
    "AgentMessage",
    "AgentPersonality",
    "AgentRole",
    "AgentStatus",
    "DelegationDecision",
    "DelegationRule",
    "MessageType",
    "ParallelExecutionResult",
    "QualityReport",
    "SanghaProposal",
    "SanghaVote",
    "SwarmTask",
    "TaskResult",
    "TaskStatus",
    "WhiteboardEntry",
    # Data
    "DEFAULT_RULES",
    "BUILTIN_AGENTS",
    "scan_agent_dirs",
]
