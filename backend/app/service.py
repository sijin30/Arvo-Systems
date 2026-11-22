"""Ticket business rules.  Every state change in Frontdesk goes through here.

Conventions
-----------
* Each function takes `now`, so one instant is used for the message, the SLA
  bookkeeping and the audit rows written by a single action.
* Every mutation first takes a row lock on the ticket (`lock_ticket`), so two
  agents acting at once are processed one after the other, never interleaved.
* Nothing here commits; the caller owns the transaction.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import audit, sla
from .audit import Actor, agent_actor
from .errors import bad_request, conflict, forbidden, not_found
from .models import ACTIVE_STATUSES, Agent, Customer, Holiday, Message, SlaPause, Ticket


# ------------------------------------------------------------------ helpers
def get_holidays(session: Session) -> set[date]:
    return set(session.scalars(select(Holiday.day)))


def lock_ticket(session: Session, ticket_id: int) -> Ticket:
    """Lock the ticket row for the rest of the transaction and return fresh data."""
    locked = session.execute(
        select(Ticket.id).where(Ticket.id == ticket_id).with_for_update()
    ).scalar_one_or_none()
    if locked is None:
        raise not_found()
    return session.execute(
        select(Ticket).where(Ticket.id == ticket_id).execution_options(populate_existing=True)
    ).scalar_one()


def clock_input(ticket: Ticket) -> sla.ClockInput:
    return sla.ClockInput(
        priority=ticket.priority,
        status=ticket.status,
        created_at=ticket.created_at,
        first_response_at=ticket.first_response_at,
        closed_reason=ticket.closed_reason,
        pauses=[sla.Pause(p.started_at, p.ended_at) for p in ticket.pauses],
    )


def sla_for(ticket: Ticket, holidays: set[date], now: datetime) -> sla.SlaResult:
    return sla.compute_sla(clock_input(ticket), holidays, now)


def open_pause(ticket: Ticket) -> Optional[SlaPause]:
    return next((p for p in ticket.pauses if p.ended_at is None), None)


def _start_pause(ticket: Ticket, reason: str, now: datetime) -> None:
    ticket.pauses.append(SlaPause(reason=reason, started_at=now))


def _end_pause(ticket: Ticket, now: datetime) -> None:
    pause = open_pause(ticket)
    if pause is not None:
        pause.ended_at = max(now, pause.started_at)


def _require_assignee(agent: Agent, ticket: Ticket) -> None:
    if ticket.assignee_id != agent.id:
        owner = ticket.assignee.name if ticket.assignee else None
        raise forbidden(
            f"Only the assigned agent ({owner}) can do this." if owner
            else "Claim the ticket first.",
            code="not_assignee",
        )


def _add_message(
    session: Session, ticket: Ticket, agent: Agent, kind: str, body: str, now: datetime
) -> Message:
    message = Message(
        ticket_id=ticket.id,
        kind=kind,
        visibility="internal" if kind == "internal_note" else "public",
        author_type="customer" if kind == "customer_message" else "agent",
        agent_id=agent.id,
        body=body,
        created_at=now,
    )
    session.add(message)
    session.flush()
    return message


def sync_breaches(session: Session, ticket: Ticket, holidays: set[date], now: datetime) -> int:
    """Write an audit entry the first time each SLA deadline is found to be missed.

    The entry is stamped with the moment the deadline passed (`occurred_at`), while the
    database records when we noticed (`recorded_at`).
    """
    result = sla_for(ticket, holidays, now)
    logged = 0
    for name, metric, attr in (
        ("sla.response_breached", result.response, "response_breach_logged_at"),
        ("sla.resolution_breached", result.resolution, "resolution_breach_logged_at"),
    ):
        if metric.breached and metric.due_at is not None and getattr(ticket, attr) is None:
            audit.record(
                session,
                audit.SYSTEM,
                name,
                occurred_at=metric.due_at,
                ticket_id=ticket.id,
                details={
                    "priority": ticket.priority,
                    "due_at": metric.due_at,
                    "budget_seconds": int(metric.budget.total_seconds()),
                    "detected_at": now,
                },
            )
            setattr(ticket, attr, now)
            logged += 1
    return logged


# ---------------------------------------------------------------- create
def create_ticket(
    session: Session,
    agent: Agent,
    *,
    subject: str,
    description: str,
    priority: str,
    customer_name: str,
    customer_email: str,
    related_ticket_id: Optional[int],
    now: datetime,
) -> Ticket:
    customer = session.scalar(select(Customer).where(Customer.email == customer_email))
    if customer is None:
        customer = Customer(name=customer_name, email=customer_email)
        session.add(customer)
        session.flush()
    if related_ticket_id is not None and session.get(Ticket, related_ticket_id) is None:
        raise bad_request("related_not_found", "The related ticket does not exist.")
    ticket = Ticket(
        subject=subject,
        priority=priority,
        status="new",
        customer_id=customer.id,
        related_ticket_id=related_ticket_id,
        public_token=secrets.token_urlsafe(24),
        created_at=now,
        updated_at=now,
    )
    session.add(ticket)
    session.flush()
    message = Message(
        ticket_id=ticket.id,
        kind="customer_message",
        visibility="public",
        author_type="customer",
        agent_id=agent.id,
        body=description,
        created_at=now,
    )
    session.add(message)
    session.flush()
    audit.record(
        session,
        agent_actor(agent),
        "ticket.created",
        occurred_at=now,
        ticket_id=ticket.id,
        details={
            "priority": priority,
            "customer_id": customer.id,
            "message_id": message.id,
            "related_ticket_id": related_ticket_id,
        },
    )
    session.flush()
    session.refresh(ticket)
    return ticket


# ------------------------------------------------------- ownership
def claim_ticket(session: Session, agent: Agent, ticket_id: int, now: datetime) -> Ticket:
    """Take an unassigned ticket.

    The ownership test and the update are ONE statement, so when two agents click at
    the same moment the database lets exactly one of them win.
    """
    won = session.execute(
        update(Ticket)
        .where(Ticket.id == ticket_id, Ticket.assignee_id.is_(None), Ticket.status == "new")
        .values(assignee_id=agent.id, status="open", updated_at=now)
        .returning(Ticket.id)
    ).first()
    if won is None:
        ticket = session.execute(
            select(Ticket).where(Ticket.id == ticket_id).execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if ticket is None:
            raise not_found()
        if ticket.assignee is not None:
            raise conflict(
                "already_claimed",
                f"{ticket.assignee.name} already took this ticket.",
                assignee={"id": ticket.assignee.id, "name": ticket.assignee.name},
            )
        raise conflict("not_claimable", f"A {ticket.status} ticket cannot be claimed.")
    ticket = lock_ticket(session, ticket_id)
    audit.record(
        session,
        agent_actor(agent),
        "ticket.claimed",
        occurred_at=now,
        ticket_id=ticket.id,
        details={"assignee_id": agent.id},
    )
    session.flush()
    return ticket


def release_ticket(session: Session, agent: Agent, ticket_id: int, now: datetime) -> Ticket:
    ticket = lock_ticket(session, ticket_id)
    if ticket.assignee_id != agent.id and agent.role != "lead":
        raise forbidden("Only the assigned agent or a lead can release this ticket.", "not_assignee")
    if ticket.status != "open":
        raise conflict("not_releasable", "Only a ticket that is open can be released.")
    previous = ticket.assignee_id
    ticket.assignee_id = None
    ticket.status = "new"
    ticket.updated_at = now
    audit.record(
        session,
        agent_actor(agent),
        "ticket.released",
        occurred_at=now,
        ticket_id=ticket.id,
        details={"previous_assignee_id": previous},
    )
    session.flush()
    return ticket


def assign_ticket(
    session: Session, agent: Agent, ticket_id: int, target_id: int, now: datetime
) -> Ticket:
    if agent.role != "lead":
        raise forbidden("Only a lead can assign tickets.", "lead_only")
    ticket = lock_ticket(session, ticket_id)
    target = session.get(Agent, target_id)
    if target is None or not target.is_active:
        raise not_found("Agent")
    if ticket.status not in ACTIVE_STATUSES:
        raise conflict("not_assignable", f"A {ticket.status} ticket cannot be assigned.")
    previous = ticket.assignee_id
    ticket.assignee_id = target.id
    if ticket.status == "new":
        ticket.status = "open"
    ticket.updated_at = now
    audit.record(
        session,
        agent_actor(agent),
        "ticket.assigned",
        occurred_at=now,
        ticket_id=ticket.id,
        details={"from_agent_id": previous, "to_agent_id": target.id},
    )
    session.flush()
    session.refresh(ticket)
    return ticket


# ------------------------------------------------------- conversation
def add_message(
    session: Session,
    agent: Agent,
    ticket_id: int,
    *,
    kind: str,
    body: str,
    set_waiting: bool,
    now: datetime,
) -> Ticket:
    ticket = lock_ticket(session, ticket_id)
    holidays = get_holidays(session)
    actor = agent_actor(agent)

    if set_waiting and kind != "public_reply":
        raise bad_request("set_waiting_needs_reply", "Only a public reply can put a ticket on hold.")

    if kind == "internal_note":
        message = _add_message(session, ticket, agent, kind, body, now)
        audit.record(
            session, actor, "message.internal_note", occurred_at=now,
            ticket_id=ticket.id, details={"message_id": message.id},
        )

    elif kind == "public_reply":
        _require_assignee(agent, ticket)
        if ticket.status not in ("open", "waiting_customer"):
            raise conflict("not_replyable", f"You cannot reply to a {ticket.status} ticket.")
        message = _add_message(session, ticket, agent, kind, body, now)
        first = ticket.first_response_at is None
        if first:
            ticket.first_response_at = now
        audit.record(
            session, actor, "message.public_reply", occurred_at=now, ticket_id=ticket.id,
            details={"message_id": message.id, "first_response": first},
        )
        if set_waiting and ticket.status == "open":
            ticket.status = "waiting_customer"
            _start_pause(ticket, "waiting_customer", now)
            audit.record(
                session, actor, "ticket.waiting_customer", occurred_at=now, ticket_id=ticket.id,
                details={"message_id": message.id, "clock": "paused"},
            )

    elif kind == "customer_message":
        _require_assignee(agent, ticket)
        if ticket.status == "resolved":
            raise conflict("use_reopen", "This ticket is resolved. Reopen it to log the customer's message.")
        if ticket.status not in ("open", "waiting_customer"):
            raise conflict("not_replyable", f"You cannot log a message on a {ticket.status} ticket.")
        message = _add_message(session, ticket, agent, kind, body, now)
        audit.record(
            session, actor, "message.customer_message", occurred_at=now,
            ticket_id=ticket.id, details={"message_id": message.id},
        )
        if ticket.status == "waiting_customer":
            _end_pause(ticket, now)
            ticket.status = "open"
            audit.record(
                session, actor, "ticket.customer_replied", occurred_at=now, ticket_id=ticket.id,
                details={"message_id": message.id, "clock": "resumed"},
            )
    else:  # pragma: no cover - guarded by schema validation
        raise bad_request("bad_kind", "Unknown message kind.")

    ticket.updated_at = now
    session.flush()
    sync_breaches(session, ticket, holidays, now)
    session.flush()
    return ticket


def resolve_ticket(
    session: Session, agent: Agent, ticket_id: int, message: Optional[str], now: datetime
) -> Ticket:
    ticket = lock_ticket(session, ticket_id)
    holidays = get_holidays(session)
    _require_assignee(agent, ticket)
    if ticket.status not in ("open", "waiting_customer"):
        raise conflict("not_resolvable", f"A {ticket.status} ticket cannot be resolved.")
    actor = agent_actor(agent)
    if message:
        reply = _add_message(session, ticket, agent, "public_reply", message, now)
        first = ticket.first_response_at is None
        if first:
            ticket.first_response_at = now
        audit.record(
            session, actor, "message.public_reply", occurred_at=now, ticket_id=ticket.id,
            details={"message_id": reply.id, "first_response": first},
        )
    if ticket.first_response_at is None:
        raise bad_request(
            "reply_required", "Reply to the customer before resolving the ticket."
        )
    previous = ticket.status
    _end_pause(ticket, now)
    ticket.status = "resolved"
    ticket.resolved_at = now
    ticket.updated_at = now
    _start_pause(ticket, "resolved", now)
    audit.record(
        session, actor, "ticket.resolved", occurred_at=now, ticket_id=ticket.id,
        details={"from": previous},
    )
    session.flush()
    sync_breaches(session, ticket, holidays, now)
    session.flush()
    return ticket


def reopen_ticket(
    session: Session, agent: Agent, ticket_id: int, message: Optional[str], now: datetime
) -> Ticket:
    ticket = lock_ticket(session, ticket_id)
    holidays = get_holidays(session)
    if ticket.status != "resolved":
        if ticket.status == "closed":
            raise conflict(
                "closed_create_new",
                "This ticket is closed. Create a new ticket for the customer instead.",
                related_ticket_id=ticket.id,
            )
        raise conflict("not_resolved", "Only a resolved ticket can be reopened.")
    if ticket.resolved_at is None or not sla.reopen_window_open(ticket.resolved_at, now, holidays):
        raise conflict(
            "reopen_window_expired",
            "This ticket was resolved more than a working week ago. "
            "Create a new ticket for the customer instead.",
            related_ticket_id=ticket.id,
        )
    actor = agent_actor(agent)
    _end_pause(ticket, now)
    ticket.status = "open"
    ticket.reopen_count += 1
    ticket.updated_at = now
    message_id = None
    if message:
        logged = _add_message(session, ticket, agent, "customer_message", message, now)
        message_id = logged.id
    audit.record(
        session, actor, "ticket.reopened", occurred_at=now, ticket_id=ticket.id,
        details={"message_id": message_id, "reopen_count": ticket.reopen_count, "clock": "resumed"},
    )
    session.flush()
    sync_breaches(session, ticket, holidays, now)
    session.flush()
    return ticket


def change_priority(
    session: Session, agent: Agent, ticket_id: int, priority: str, now: datetime
) -> Ticket:
    ticket = lock_ticket(session, ticket_id)
    holidays = get_holidays(session)
    if ticket.status not in ACTIVE_STATUSES:
        raise conflict("not_editable", f"The priority of a {ticket.status} ticket cannot change.")
    if ticket.assignee_id not in (None, agent.id) and agent.role != "lead":
        raise forbidden("Only the assigned agent or a lead can change the priority.", "not_assignee")
    if priority == ticket.priority:
        raise bad_request("no_change", f"The ticket is already {priority}.")
    previous = ticket.priority
    ticket.priority = priority
    ticket.response_breach_logged_at = None
    ticket.resolution_breach_logged_at = None
    ticket.updated_at = now
    audit.record(
        session, agent_actor(agent), "ticket.priority_changed", occurred_at=now, ticket_id=ticket.id,
        details={"from": previous, "to": priority, "rule": "deadlines recomputed from creation time"},
    )
    session.flush()
    sync_breaches(session, ticket, holidays, now)
    session.flush()
    return ticket
