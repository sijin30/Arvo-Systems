"""Turning tickets into API responses, and listing/searching tickets."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Optional

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from . import sla
from . import schemas as s
from .models import ACTIVE_STATUSES, Agent, Customer, Message, Ticket, customer_messages
from .service import sla_for

# ------------------------------------------------------------ presenters


def _metric(m: sla.Metric) -> s.MetricOut:
    return s.MetricOut(
        state=m.state,
        budget_seconds=int(m.budget.total_seconds()),
        due_at=m.due_at,
        remaining_seconds=int(m.remaining.total_seconds()),
        breached=m.breached,
    )


def _sla(r: sla.SlaResult) -> s.SlaOut:
    return s.SlaOut(
        response=_metric(r.response),
        resolution=_metric(r.resolution),
        late=r.late,
        waiting_on_customer=r.waiting_on_customer,
        next_due_at=r.next_due_at,
        auto_close_at=r.auto_close_at,
        reopen_until=r.reopen_until,
    )


def ticket_fields(t: Ticket, holidays: set[date], now: datetime) -> dict:
    result = sla_for(t, holidays, now)
    return dict(
        id=t.id,
        reference=t.reference,
        subject=t.subject,
        priority=t.priority,
        status=t.status,
        customer=s.CustomerRef(id=t.customer.id, name=t.customer.name, email=t.customer.email),
        assignee=s.AgentRef(id=t.assignee.id, name=t.assignee.name) if t.assignee else None,
        created_at=t.created_at,
        updated_at=t.updated_at,
        first_response_at=t.first_response_at,
        resolved_at=t.resolved_at,
        closed_at=t.closed_at,
        closed_reason=t.closed_reason,
        reopen_count=t.reopen_count,
        related_ticket_id=t.related_ticket_id,
        related_reference=t.related_ticket.reference if t.related_ticket else None,
        late=result.late,
        sla=_sla(result),
    )


def ticket_summary(t: Ticket, holidays: set[date], now: datetime) -> s.TicketSummary:
    return s.TicketSummary(**ticket_fields(t, holidays, now))


def actions_for(
    t: Ticket, agent: Agent, holidays: set[date], now: datetime
) -> s.Actions:
    is_owner = t.assignee_id == agent.id
    is_lead = agent.role == "lead"
    active = t.status in ACTIVE_STATUSES
    working = t.status in ("open", "waiting_customer")
    can_reopen = (
        t.status == "resolved"
        and t.resolved_at is not None
        and sla.reopen_window_open(t.resolved_at, now, holidays)
    )
    return s.Actions(
        can_claim=t.status == "new" and t.assignee_id is None,
        can_release=t.status == "open" and (is_owner or is_lead),
        can_assign=is_lead and active,
        can_reply=is_owner and working,
        can_note=True,
        can_log_customer_reply=is_owner and working,
        can_resolve=is_owner and working,
        can_reopen=can_reopen,
        can_change_priority=active and (t.assignee_id is None or is_owner or is_lead),
    )


def agent_message(m: Message) -> s.AgentMessage:
    return s.AgentMessage(
        id=m.id,
        kind=m.kind,
        visibility=m.visibility,
        author_type=m.author_type,
        author=s.AgentRef(id=m.agent.id, name=m.agent.name) if m.agent else None,
        body=m.body,
        created_at=m.created_at,
    )


def ticket_detail(
    session: Session, t: Ticket, agent: Agent, holidays: set[date], now: datetime
) -> s.TicketDetail:
    messages = session.scalars(
        select(Message).where(Message.ticket_id == t.id).order_by(Message.id)
    ).all()
    return s.TicketDetail(
        **ticket_fields(t, holidays, now),
        public_token=t.public_token,
        messages=[agent_message(m) for m in messages],
        actions=actions_for(t, agent, holidays, now),
    )


# ---------------------------------------------------------- listing
VIEWS = ("active", "unassigned", "late", "waiting", "resolved", "closed", "history")
_ACTIVE_VIEWS = {"active", "unassigned", "late", "waiting"}
_MAX_ACTIVE_ROWS = 2000


def _base_query(scope: str, agent: Agent, view: str, q: Optional[str], priority: Optional[str]):
    stmt = select(Ticket).join(Customer, Customer.id == Ticket.customer_id)
    if scope == "mine":
        stmt = stmt.where(Ticket.assignee_id == agent.id)
    if view in ("active", "late"):
        stmt = stmt.where(Ticket.status.in_(ACTIVE_STATUSES))
    elif view == "unassigned":
        stmt = stmt.where(Ticket.status == "new")
    elif view == "waiting":
        stmt = stmt.where(Ticket.status == "waiting_customer")
    elif view == "resolved":
        stmt = stmt.where(Ticket.status == "resolved")
    elif view == "closed":
        stmt = stmt.where(Ticket.status == "closed")
    elif view == "history":
        stmt = stmt.where(Ticket.status.in_(("resolved", "closed")))
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Ticket.subject.ilike(like),
                Ticket.reference.ilike(like),
                Customer.name.ilike(like),
                Customer.email.ilike(like),
            )
        )
    return stmt


def _sort_key(item: s.TicketSummary):
    # Late first, then the nearest deadline, tickets with a stopped clock last.
    far = datetime.max.replace(tzinfo=item.created_at.tzinfo)
    return (not item.late, item.sla.next_due_at or far, item.created_at)


def list_tickets(
    session: Session,
    agent: Agent,
    holidays: set[date],
    now: datetime,
    *,
    scope: str,
    view: str,
    q: Optional[str],
    priority: Optional[str],
    limit: int,
    offset: int,
) -> s.TicketList:
    stmt = _base_query(scope, agent, view, q, priority)
    if view in _ACTIVE_VIEWS:
        rows = session.scalars(stmt.order_by(Ticket.created_at).limit(_MAX_ACTIVE_ROWS)).unique().all()
        items = [ticket_summary(t, holidays, now) for t in rows]
        if view == "late":
            items = [i for i in items if i.late]
        items.sort(key=_sort_key)
        return s.TicketList(items=items[offset : offset + limit], total=len(items))
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (
        session.scalars(stmt.order_by(Ticket.updated_at.desc(), Ticket.id.desc()).limit(limit).offset(offset))
        .unique()
        .all()
    )
    return s.TicketList(items=[ticket_summary(t, holidays, now) for t in rows], total=total or 0)


def ticket_counts(
    session: Session, agent: Agent, holidays: set[date], now: datetime, scope: str
) -> s.TicketCounts:
    stmt = _base_query(scope, agent, "active", None, None)
    rows = session.scalars(stmt.limit(_MAX_ACTIVE_ROWS)).unique().all()
    results = [sla_for(t, holidays, now) for t in rows]
    return s.TicketCounts(
        active=len(rows),
        unassigned=sum(1 for t in rows if t.status == "new"),
        late=sum(1 for r in results if r.late),
        waiting_on_customer=sum(1 for r in results if r.waiting_on_customer),
    )


# ------------------------------------------------- customer-safe output
_CUSTOMER_STATUS = {
    "new": "received",
    "open": "in_progress",
    "waiting_customer": "waiting_for_you",
    "resolved": "resolved",
    "closed": "closed",
}


def _public_rows(session: Session, ticket_id: int):
    """The only way customer-facing code reads messages: through the public view."""
    return session.execute(
        select(customer_messages)
        .where(customer_messages.c.ticket_id == ticket_id)
        .order_by(customer_messages.c.id)
    ).all()


def customer_view(session: Session, t: Ticket) -> s.CustomerTicketView:
    return s.CustomerTicketView(
        reference=t.reference,
        subject=t.subject,
        status=_CUSTOMER_STATUS[t.status],
        created_at=t.created_at,
        messages=[
            s.CustomerMessage(
                id=r.id,
                sender="you" if r.author_type == "customer" else "support",
                body=r.body,
                created_at=r.created_at,
            )
            for r in _public_rows(session, t.id)
        ],
    )


def transcript_text(session: Session, t: Ticket) -> str:
    """Plain-text copy of the conversation that is safe to send to the customer."""
    view = customer_view(session, t)
    lines = [
        f"Ticket {view.reference}: {view.subject}",
        f"Status: {view.status.replace('_', ' ')}",
        "",
    ]
    for m in view.messages:
        who = "You" if m.sender == "you" else "Arvo Support"
        stamp = m.created_at.strftime("%Y-%m-%d %H:%M UTC")
        lines += [f"[{stamp}] {who}", m.body, ""]
    return "\n".join(lines)


def _csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    # Stop spreadsheet programs from running a cell that starts like a formula.
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def tickets_csv(items: list[s.TicketSummary]) -> str:
    """List export.  Deliberately contains no message text of any kind."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "reference", "subject", "priority", "status", "customer", "assignee",
            "created_at", "first_response_at", "resolved_at",
            "response_sla", "resolution_sla", "late",
        ]
    )
    for i in items:
        writer.writerow(
            [
                _csv_safe(i.reference), _csv_safe(i.subject), i.priority, i.status,
                _csv_safe(i.customer.name), _csv_safe(i.assignee.name if i.assignee else ""),
                i.created_at.isoformat(),
                i.first_response_at.isoformat() if i.first_response_at else "",
                i.resolved_at.isoformat() if i.resolved_at else "",
                i.sla.response.state, i.sla.resolution.state, "yes" if i.late else "no",
            ]
        )
    return out.getvalue()


# ------------------------------------------------------------ customer portal
def portal_summary(t: Ticket) -> s.PortalTicketSummary:
    return s.PortalTicketSummary(
        id=t.id,
        reference=t.reference,
        subject=t.subject,
        priority=t.priority,
        status=_CUSTOMER_STATUS[t.status],
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def list_portal_tickets(session: Session, customer: Customer) -> list[s.PortalTicketSummary]:
    rows = session.scalars(
        select(Ticket).where(Ticket.customer_id == customer.id).order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    ).unique().all()
    return [portal_summary(t) for t in rows]


def portal_view(
    session: Session, t: Ticket, holidays: set[date], now: datetime
) -> s.PortalTicketView:
    base = customer_view(session, t)
    reopen_until = None
    can_reopen = False
    if t.status == "resolved" and t.resolved_at is not None:
        can_reopen = sla.reopen_window_open(t.resolved_at, now, holidays)
        if can_reopen:
            from . import worktime as wt

            reopen_until = wt.add_working_time(t.resolved_at, sla.REOPEN_WINDOW, holidays)
    return s.PortalTicketView(
        **base.model_dump(),
        id=t.id,
        priority=t.priority,
        can_reply=t.status in ("new", "open", "waiting_customer"),
        can_reopen=can_reopen,
        reopen_until=reopen_until,
    )
