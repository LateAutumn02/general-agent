"""Swarm type definitions.

Reference: ccswarm crates/ccswarm/src/coordination/mod.rs, agent/mod.rs,
           subagent/parallel_executor.rs, orchestrator/master_delegation.rs
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Agent types
# ---------------------------------------------------------------------------


class AgentStatus(str, Enum):
    INITIALIZING = "Initializing"
    AVAILABLE = "Available"
    WORKING = "Working"
    WAITING_FOR_HELP = "WaitingForHelp"
    WAITING_FOR_REVIEW = "WaitingForReview"
    ERROR = "Error"
    DISCONNECTED = "Disconnected"
    SHUTTING_DOWN = "ShuttingDown"


@dataclass
class AgentRole:
    kind: str  # Frontend | Backend | DevOps | QA | GeneralPurpose | Master
    technologies: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)


@dataclass
class AgentPersonality:
    formality: float = 0.5
    verbosity: float = 0.5
    directness: float = 0.7
    creativity: float = 0.5
    risk_tolerance: float = 0.3


@dataclass
class AgentDefinition:
    name: str
    role: AgentRole = field(default_factory=lambda: AgentRole(kind="GeneralPurpose"))
    personality: AgentPersonality = field(default_factory=AgentPersonality)
    model: str = ""
    system_prompt: str = ""
    tools: list[str] = field(default_factory=lambda: ["all"])
    auto_accept: bool = False
    risk_threshold: int = 5
    max_turns: int = 20


@dataclass
class AgentIdentity:
    agent_id: str = field(default_factory=_new_id)
    definition: AgentDefinition = field(default_factory=AgentDefinition)
    session_id: str = ""
    started_at: str = field(default_factory=_now)
    status: AgentStatus = AgentStatus.INITIALIZING


# ---------------------------------------------------------------------------
# Task types
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    PENDING = "Pending"
    BLOCKED = "Blocked"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    TIMED_OUT = "TimedOut"


@dataclass
class SwarmTask:
    description: str
    task_id: str = field(default_factory=_new_id)
    priority: str = "Normal"  # Low | Normal | High | Critical
    target_role: str = ""     # empty = auto-match
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=_now)
    completed_at: str = ""


# ---------------------------------------------------------------------------
# Whiteboard
# ---------------------------------------------------------------------------


@dataclass
class WhiteboardEntry:
    content: str
    agent_id: str = ""
    entry_id: str = field(default_factory=_new_id)
    entry_type: str = "Note"  # Discovery|Hypothesis|Decision|Question|TodoList|ComparisonTable|Conclusion
    annotations: list[str] = field(default_factory=list)
    related_task: str = ""
    visible_to: list[str] = field(default_factory=list)  # empty = all
    created_at: str = field(default_factory=_now)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    task_id: str
    agent_id: str = ""
    status: TaskStatus = TaskStatus.COMPLETED
    output: str = ""
    artifacts: list[str] = field(default_factory=list)
    whiteboard: list[WhiteboardEntry] = field(default_factory=list)
    quality_score: float = 0.0
    error: str = ""
    duration_ms: int = 0
    retries: int = 0


@dataclass
class ConflictInfo:
    file_path: str
    agent_a: str
    agent_b: str
    description: str


@dataclass
class QualityReport:
    overall_score: float = 0.0
    completeness: float = 0.0
    correctness: float = 0.0
    style_consistency: float = 0.0
    security: float = 0.0
    suggestions: list[str] = field(default_factory=list)
    conflicts: list[ConflictInfo] = field(default_factory=list)


@dataclass
class ParallelExecutionResult:
    execution_id: str = field(default_factory=_new_id)
    status: str = "Completed"  # Completed|PartialFailure|Timeout|Cancelled
    task_results: list[TaskResult] = field(default_factory=list)
    total_duration_ms: int = 0
    successful_count: int = 0
    failed_count: int = 0
    quality_report: QualityReport | None = None


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


class MessageType(str, Enum):
    REGISTRATION = "Registration"
    TASK_ASSIGNMENT = "TaskAssignment"
    TASK_PROGRESS = "TaskProgress"
    TASK_COMPLETED = "TaskCompleted"
    HELP_REQUEST = "HelpRequest"
    HELP_RESPONSE = "HelpResponse"
    STATUS_UPDATE = "StatusUpdate"
    HEARTBEAT = "Heartbeat"
    INTER_AGENT = "InterAgentMessage"
    WHITEBOARD_UPDATE = "WhiteboardUpdate"
    QUALITY_ISSUE = "QualityIssue"
    SANGHA_PROPOSAL = "SanghaProposal"
    SANGHA_VOTE = "SanghaVote"
    CUSTOM = "Custom"


@dataclass
class AgentMessage:
    msg_type: MessageType
    sender_id: str = ""
    recipient_id: str = ""  # empty = broadcast
    payload: Any = None
    msg_id: str = field(default_factory=_new_id)
    timestamp: str = field(default_factory=_now)
    priority: str = "Normal"


# ---------------------------------------------------------------------------
# Delegation types
# ---------------------------------------------------------------------------


@dataclass
class DelegationCondition:
    field: str    # 'description' | 'priority' | 'task_type'
    op: str       # 'contains' | 'equals' | 'above' | 'below'
    value: str | int


@dataclass
class DelegationRule:
    name: str
    priority: int
    keywords: list[str]
    target_role: str
    conditions: list[DelegationCondition] = field(default_factory=list)


@dataclass
class DelegationDecision:
    task_id: str
    target_role: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    source: str = ""  # 'rule' | 'llm'


# ---------------------------------------------------------------------------
# Sangha types
# ---------------------------------------------------------------------------


@dataclass
class SanghaVote:
    agent_id: str
    vote: str = ""  # 'Approve' | 'Reject' | 'Abstain'
    reason: str = ""
    weight: float = 1.0
    timestamp: str = field(default_factory=_now)


@dataclass
class SanghaProposal:
    title: str
    description: str
    proposer_id: str = ""  # agent_id or 'user'
    proposal_id: str = field(default_factory=_new_id)
    status: str = "Open"  # Open|Voting|Passed|Rejected
    votes: list[SanghaVote] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
