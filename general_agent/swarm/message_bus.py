"""Message Bus — asyncio.Queue based inter-agent communication.

Broadcast + point-to-point + JSON persistence.
Reference: ccswarm crates/ccswarm/src/coordination/mod.rs (CoordinationBus)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from general_agent.swarm.types import AgentMessage, MessageType, _new_id, _now

logger = logging.getLogger("general_agent.swarm.bus")

MAX_HISTORY = 2000
AUTO_PERSIST_EVERY = 50  # persist every N messages


class MessageBus:
    """Central message bus for swarm agents.

    Each registered agent gets an asyncio.Queue.
    send() with recipient_id="" is a broadcast to all registered agents.
    Messages are persisted to JSON for crash recovery.
    """

    def __init__(self, persistence_file: str = "") -> None:
        self._channels: dict[str, asyncio.Queue[AgentMessage]] = {}
        self._history: list[AgentMessage] = []
        self._persist_file = persistence_file
        self._persist_counter = 0

    # ---- registration ----

    def register(self, agent_id: str) -> asyncio.Queue[AgentMessage]:
        if agent_id in self._channels:
            return self._channels[agent_id]
        q: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._channels[agent_id] = q
        logger.debug("Agent registered on bus: %s", agent_id)
        return q

    def unregister(self, agent_id: str) -> None:
        self._channels.pop(agent_id, None)
        logger.debug("Agent unregistered from bus: %s", agent_id)

    @property
    def agent_ids(self) -> list[str]:
        return list(self._channels.keys())

    # ---- send ----

    def send(self, msg: AgentMessage) -> None:
        """Send a message. Empty recipient_id = broadcast."""
        self._history.append(msg)
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

        if not msg.recipient_id:
            # Broadcast
            for q in self._channels.values():
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass
        else:
            # Point-to-point
            q = self._channels.get(msg.recipient_id)
            if q:
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass

        self._persist_counter += 1
        if self._persist_counter >= AUTO_PERSIST_EVERY:
            self.persist_to_disk()
            self._persist_counter = 0

    def broadcast(self, msg_type: MessageType, payload: Any, *,
                  sender_id: str = "", priority: str = "Normal") -> None:
        """Convenience: broadcast to all agents."""
        self.send(AgentMessage(
            msg_type=msg_type,
            sender_id=sender_id,
            payload=payload,
            priority=priority,
        ))

    def send_to(self, recipient_id: str, msg_type: MessageType, payload: Any, *,
                sender_id: str = "", priority: str = "Normal") -> None:
        """Convenience: point-to-point."""
        self.send(AgentMessage(
            msg_type=msg_type,
            sender_id=sender_id,
            recipient_id=recipient_id,
            payload=payload,
            priority=priority,
        ))

    # ---- receive ----

    async def get_messages(self, agent_id: str) -> list[AgentMessage]:
        """Drain pending messages for an agent."""
        q = self._channels.get(agent_id)
        if not q:
            return []
        msgs: list[AgentMessage] = []
        while not q.empty():
            try:
                msgs.append(q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return msgs

    def get_messages_sync(self, agent_id: str) -> list[AgentMessage]:
        """Non-async drain for sync callers."""
        q = self._channels.get(agent_id)
        if not q:
            return []
        msgs: list[AgentMessage] = []
        while not q.empty():
            try:
                msgs.append(q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return msgs

    # ---- history ----

    def get_history(self, since: str = "") -> list[AgentMessage]:
        """Return messages after a given ISO timestamp."""
        if not since:
            return list(self._history)
        return [m for m in self._history if m.timestamp > since]

    # ---- persistence ----

    def persist_to_disk(self) -> None:
        if not self._persist_file:
            return
        try:
            os.makedirs(os.path.dirname(self._persist_file), exist_ok=True)
            with open(self._persist_file, "w", encoding="utf-8") as f:
                for msg in self._history[-1000:]:  # keep last 1000
                    f.write(json.dumps(self._msg_to_dict(msg), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("MessageBus persist failed: %s", e)

    def load_from_disk(self) -> list[AgentMessage]:
        if not self._persist_file or not os.path.exists(self._persist_file):
            return []
        msgs: list[AgentMessage] = []
        try:
            with open(self._persist_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msgs.append(self._dict_to_msg(json.loads(line)))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            logger.warning("MessageBus load failed: %s", e)
        self._history = msgs[-MAX_HISTORY:]
        return msgs

    @staticmethod
    def _msg_to_dict(msg: AgentMessage) -> dict[str, Any]:
        return {
            "msg_id": msg.msg_id,
            "msg_type": msg.msg_type.value,
            "sender_id": msg.sender_id,
            "recipient_id": msg.recipient_id,
            "payload": msg.payload,
            "timestamp": msg.timestamp,
            "priority": msg.priority,
        }

    @staticmethod
    def _dict_to_msg(d: dict[str, Any]) -> AgentMessage:
        return AgentMessage(
            msg_id=d["msg_id"],
            msg_type=MessageType(d["msg_type"]),
            sender_id=d.get("sender_id", ""),
            recipient_id=d.get("recipient_id", ""),
            payload=d.get("payload"),
            timestamp=d.get("timestamp", _now()),
            priority=d.get("priority", "Normal"),
        )
