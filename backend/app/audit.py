"""Writing to the audit log.

Audit rows never contain message bodies.  They point at message ids, so that
nothing private (an internal note) can ever leak through the audit trail either.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from .models import Agent, AuditLog


@dataclass(frozen=True)
class Actor:
    type: str  # "agent" | "system"
    id: Optional[int]
    name: str


SYSTEM = Actor("system", None, "Frontdesk system")


def agent_actor(agent: Agent) -> Actor:
    return Actor("agent", agent.id, agent.name)


def record(
    session: Session,
    actor: Actor,
    action: str,
    occurred_at: datetime,
    ticket_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    session.add(
        AuditLog(
            ticket_id=ticket_id,
            actor_type=actor.type,
            actor_id=actor.id,
            actor_name=actor.name,
            action=action,
            details=_jsonable(details or {}),
            occurred_at=occurred_at,
        )
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value
