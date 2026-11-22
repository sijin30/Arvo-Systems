"""HTTP API.  Thin: validate, call the service layer, commit, present."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import accounts, audit, clock, jobs, security, service, throttle, views
from . import schemas as s
from .config import Settings
from .deps import current_agent, get_session, get_settings, lead_agent
from .errors import DomainError, bad_request, not_found
from .models import Agent, AuditLog, Holiday, Ticket
from .portal import portal

api = APIRouter(prefix="/api")

# ------------------------------------------------------------------ auth
_DUMMY_HASH = security.hash_password("not-a-real-password", 1000)


@api.post("/auth/login", response_model=s.LoginOut)
def login(
    body: s.LoginIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    email = body.email.strip().lower()
    if throttle.agent_logins.blocked(email):
        raise DomainError(429, "too_many_attempts", "Too many failed logins. Try again in a few minutes.")
    agent = session.scalar(select(Agent).where(Agent.email == email))
    stored = agent.password_hash if agent else _DUMMY_HASH
    ok = security.verify_password(body.password, stored)
    if not (agent and agent.is_active and ok):
        throttle.agent_logins.record_failure(email)
        raise DomainError(401, "bad_credentials", "Incorrect email or password.")
    throttle.agent_logins.reset(email)
    return s.LoginOut(
        token=security.create_token(settings, security.AGENT, agent.id),
        agent=s.AgentOut(id=agent.id, name=agent.name, email=agent.email, role=agent.role),
    )


@api.post("/auth/password", status_code=204)
def change_password(
    body: s.PasswordChangeIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    agent: Agent = Depends(current_agent),
):
    accounts.change_password(
        session, agent, audit.agent_actor(agent),
        current=body.current_password, new=body.new_password,
        iterations=settings.password_iterations, now=clock.now(),
    )
    session.commit()


@api.get("/auth/me", response_model=s.AgentOut)
def me(agent: Agent = Depends(current_agent)):
    return s.AgentOut(id=agent.id, name=agent.name, email=agent.email, role=agent.role)


@api.get("/agents", response_model=list[s.AgentOut])
def list_agents(session: Session = Depends(get_session), _: Agent = Depends(current_agent)):
    rows = session.scalars(select(Agent).where(Agent.is_active).order_by(Agent.name)).all()
    return [s.AgentOut(id=a.id, name=a.name, email=a.email, role=a.role) for a in rows]


@api.get("/health")
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


# --------------------------------------------------------------- tickets
tickets = APIRouter(prefix="/tickets", tags=["tickets"])

Scope = Literal["mine", "all"]
ViewName = Literal["active", "unassigned", "late", "waiting", "resolved", "closed", "history"]


def _detail(session: Session, agent: Agent, ticket_id: int) -> s.TicketDetail:
    session.expire_all()
    ticket = session.get(Ticket, ticket_id, populate_existing=True)
    if ticket is None:
        raise not_found()
    return views.ticket_detail(session, ticket, agent, service.get_holidays(session), clock.now())


@tickets.get("", response_model=s.TicketList)
def list_tickets(
    scope: Scope = "all",
    view: ViewName = "active",
    q: Optional[str] = Query(default=None, max_length=100),
    priority: Optional[s.Priority] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    return views.list_tickets(
        session, agent, service.get_holidays(session), clock.now(),
        scope=scope, view=view, q=q, priority=priority, limit=limit, offset=offset,
    )


@tickets.get("/counts", response_model=s.TicketCounts)
def counts(
    scope: Scope = "all",
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    return views.ticket_counts(session, agent, service.get_holidays(session), clock.now(), scope)


@tickets.get("/export.csv")
def export_csv(
    scope: Scope = "all",
    view: ViewName = "active",
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    result = views.list_tickets(
        session, agent, service.get_holidays(session), clock.now(),
        scope=scope, view=view, q=None, priority=None, limit=200, offset=0,
    )
    return Response(
        content=views.tickets_csv(result.items),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tickets.csv"'},
    )


@tickets.post("", response_model=s.TicketDetail, status_code=201)
def create_ticket(
    body: s.TicketCreateIn,
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    ticket = service.create_ticket(
        session, agent,
        subject=body.subject, description=body.description, priority=body.priority,
        customer_name=body.customer_name, customer_email=body.customer_email,
        related_ticket_id=body.related_ticket_id, now=clock.now(),
    )
    ticket_id = ticket.id
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.get("/{ticket_id}", response_model=s.TicketDetail)
def get_ticket(ticket_id: int, session: Session = Depends(get_session), agent: Agent = Depends(current_agent)):
    return _detail(session, agent, ticket_id)


@tickets.post("/{ticket_id}/claim", response_model=s.TicketDetail)
def claim(ticket_id: int, session: Session = Depends(get_session), agent: Agent = Depends(current_agent)):
    service.claim_ticket(session, agent, ticket_id, clock.now())
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.post("/{ticket_id}/release", response_model=s.TicketDetail)
def release(ticket_id: int, session: Session = Depends(get_session), agent: Agent = Depends(current_agent)):
    service.release_ticket(session, agent, ticket_id, clock.now())
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.post("/{ticket_id}/assign", response_model=s.TicketDetail)
def assign(
    ticket_id: int,
    body: s.AssignIn,
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    service.assign_ticket(session, agent, ticket_id, body.agent_id, clock.now())
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.post("/{ticket_id}/messages", response_model=s.TicketDetail, status_code=201)
def post_message(
    ticket_id: int,
    body: s.MessageIn,
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    service.add_message(
        session, agent, ticket_id,
        kind=body.kind, body=body.body, set_waiting=body.set_waiting, now=clock.now(),
    )
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.post("/{ticket_id}/resolve", response_model=s.TicketDetail)
def resolve(
    ticket_id: int,
    body: s.ResolveIn,
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    service.resolve_ticket(session, agent, ticket_id, body.message, clock.now())
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.post("/{ticket_id}/reopen", response_model=s.TicketDetail)
def reopen(
    ticket_id: int,
    body: s.ReopenIn,
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    service.reopen_ticket(session, agent, ticket_id, body.message, clock.now())
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.post("/{ticket_id}/priority", response_model=s.TicketDetail)
def set_priority(
    ticket_id: int,
    body: s.PriorityIn,
    session: Session = Depends(get_session),
    agent: Agent = Depends(current_agent),
):
    service.change_priority(session, agent, ticket_id, body.priority, clock.now())
    session.commit()
    return _detail(session, agent, ticket_id)


@tickets.get("/{ticket_id}/audit", response_model=list[s.AuditEntry])
def ticket_audit(
    ticket_id: int, session: Session = Depends(get_session), _: Agent = Depends(current_agent)
):
    if session.get(Ticket, ticket_id) is None:
        raise not_found()
    rows = session.scalars(
        select(AuditLog).where(AuditLog.ticket_id == ticket_id).order_by(AuditLog.seq)
    ).all()
    return [
        s.AuditEntry(
            seq=r.seq, action=r.action, actor_type=r.actor_type, actor_name=r.actor_name,
            occurred_at=r.occurred_at, recorded_at=r.recorded_at, details=r.details,
        )
        for r in rows
    ]


@tickets.get("/{ticket_id}/transcript", response_class=PlainTextResponse)
def transcript(
    ticket_id: int, session: Session = Depends(get_session), _: Agent = Depends(current_agent)
):
    """Customer-safe copy of the conversation (never includes internal notes)."""
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise not_found()
    return PlainTextResponse(views.transcript_text(session, ticket))


api.include_router(tickets)

# --------------------------------------------------- customer-facing view
public = APIRouter(prefix="/public", tags=["customer"])


def _by_token(session: Session, token: str) -> Ticket:
    ticket = session.scalar(select(Ticket).where(Ticket.public_token == token))
    if ticket is None:
        raise not_found()
    return ticket


@public.get("/tickets/{token}", response_model=s.CustomerTicketView)
def public_ticket(token: str, response: Response, session: Session = Depends(get_session)):
    response.headers["Cache-Control"] = "no-store"
    return views.customer_view(session, _by_token(session, token))


@public.get("/tickets/{token}/transcript", response_class=PlainTextResponse)
def public_transcript(token: str, session: Session = Depends(get_session)):
    return PlainTextResponse(
        views.transcript_text(session, _by_token(session, token)),
        headers={"Cache-Control": "no-store"},
    )


api.include_router(public)

# ---------------------------------------------------------- admin things
admin = APIRouter(tags=["admin"])


@admin.get("/holidays", response_model=list[s.HolidayOut])
def list_holidays(session: Session = Depends(get_session), _: Agent = Depends(current_agent)):
    rows = session.scalars(select(Holiday).order_by(Holiday.day)).all()
    return [s.HolidayOut(day=h.day, name=h.name) for h in rows]


@admin.post("/holidays", response_model=s.HolidayOut, status_code=201)
def add_holiday(
    body: s.HolidayIn, session: Session = Depends(get_session), agent: Agent = Depends(lead_agent)
):
    if session.get(Holiday, body.day) is not None:
        raise DomainError(409, "holiday_exists", "That date is already a holiday.")
    session.add(Holiday(day=body.day, name=body.name.strip()))
    audit.record(
        session, audit.agent_actor(agent), "holiday.added", occurred_at=clock.now(),
        details={"day": body.day.isoformat(), "name": body.name.strip()},
    )
    session.commit()
    return s.HolidayOut(day=body.day, name=body.name.strip())


@admin.delete("/holidays/{day}", status_code=204)
def remove_holiday(
    day: str, session: Session = Depends(get_session), agent: Agent = Depends(lead_agent)
):
    from datetime import date

    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        raise bad_request("bad_date", "Use the format YYYY-MM-DD.")
    holiday = session.get(Holiday, parsed)
    if holiday is None:
        raise not_found("Holiday")
    session.delete(holiday)
    audit.record(
        session, audit.agent_actor(agent), "holiday.removed", occurred_at=clock.now(),
        details={"day": parsed.isoformat(), "name": holiday.name},
    )
    session.commit()
    return Response(status_code=204)


@admin.get("/audit/verify", response_model=s.AuditVerifyOut)
def verify_audit(session: Session = Depends(get_session), _: Agent = Depends(lead_agent)):
    broken = session.execute(text("SELECT audit_verify()")).scalar()
    count = session.execute(text("SELECT count(*) FROM audit_log")).scalar()
    return s.AuditVerifyOut(intact=broken is None, first_broken_seq=broken, entries_checked=count or 0)


@admin.post("/ops/housekeeping", response_model=s.HousekeepingOut)
def run_housekeeping(request: Request, _: Agent = Depends(lead_agent)):
    return jobs.run_housekeeping(request.app.state.session_factory)


def _agent_admin(a: Agent, active_tickets: int) -> s.AgentAdminOut:
    return s.AgentAdminOut(
        id=a.id, name=a.name, email=a.email, role=a.role,
        is_active=a.is_active, active_tickets=active_tickets,
    )


@admin.get("/admin/agents", response_model=list[s.AgentAdminOut])
def admin_list_agents(session: Session = Depends(get_session), _: Agent = Depends(lead_agent)):
    return [_agent_admin(a, n) for a, n in accounts.list_agents_for_admin(session)]


@admin.post("/admin/agents", response_model=s.AgentAdminOut, status_code=201)
def admin_create_agent(
    body: s.AgentCreateIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    lead: Agent = Depends(lead_agent),
):
    agent = accounts.create_agent(
        session, lead, name=body.name, email=body.email, password=body.password,
        role=body.role, iterations=settings.password_iterations, now=clock.now(),
    )
    session.commit()
    return _agent_admin(agent, 0)


@admin.post("/admin/agents/{agent_id}/deactivate", response_model=s.AgentAdminOut)
def admin_deactivate_agent(
    agent_id: int, session: Session = Depends(get_session), lead: Agent = Depends(lead_agent)
):
    agent = accounts.set_agent_active(session, lead, agent_id, False, clock.now())
    session.commit()
    return _agent_admin(agent, 0)


@admin.post("/admin/agents/{agent_id}/activate", response_model=s.AgentAdminOut)
def admin_activate_agent(
    agent_id: int, session: Session = Depends(get_session), lead: Agent = Depends(lead_agent)
):
    agent = accounts.set_agent_active(session, lead, agent_id, True, clock.now())
    session.commit()
    return _agent_admin(agent, 0)


@admin.post("/admin/agents/{agent_id}/password", status_code=204)
def admin_reset_password(
    agent_id: int,
    body: s.PasswordResetIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    lead: Agent = Depends(lead_agent),
):
    accounts.reset_agent_password(
        session, lead, agent_id, body.password, settings.password_iterations, clock.now()
    )
    session.commit()



api.include_router(admin)
api.include_router(portal)
