"""Accounts: customer sign-up, password changes and the lead's agent management."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit, security
from .audit import Actor, agent_actor
from .errors import bad_request, conflict, not_found
from .models import ACTIVE_STATUSES, ROLES, Agent, Customer, Ticket
from .service import customer_actor

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL.match(email) or len(email) > 255:
        raise bad_request("bad_email", "Enter a valid email address.")
    return email


def check_password(password: str) -> None:
    if not (security.MIN_PASSWORD_LENGTH <= len(password) <= security.MAX_PASSWORD_LENGTH):
        raise bad_request(
            "weak_password",
            f"Use a password of at least {security.MIN_PASSWORD_LENGTH} characters.",
        )


# ---------------------------------------------------------------- customers
def signup_customer(
    session: Session, *, name: str, email: str, password: str, iterations: int, now: datetime
) -> Customer:
    email = normalize_email(email)
    check_password(password)
    existing = session.scalar(select(Customer).where(Customer.email == email))
    if existing is not None:
        if existing.password_hash is not None:
            raise conflict("account_exists", "An account with this email already exists. Please sign in.")
        # An agent has already logged tickets for this email.  Without email verification
        # we must not hand those tickets to whoever types the address, so a person has to
        # contact support instead.
        raise conflict(
            "email_in_use",
            "Support has already spoken with this email address. Please contact support to "
            "get access, or use a different email.",
        )
    customer = Customer(name=name.strip(), email=email, password_hash=security.hash_password(password, iterations))
    session.add(customer)
    session.flush()
    audit.record(
        session, customer_actor(customer), "customer.signed_up", occurred_at=now,
        details={"customer_id": customer.id},
    )
    session.flush()
    return customer


def change_password(
    session: Session,
    account: Agent | Customer,
    actor: Actor,
    *,
    current: str,
    new: str,
    iterations: int,
    now: datetime,
) -> None:
    if not account.password_hash or not security.verify_password(current, account.password_hash):
        raise bad_request("wrong_password", "Your current password is not correct.")
    check_password(new)
    account.password_hash = security.hash_password(new, iterations)
    audit.record(session, actor, "account.password_changed", occurred_at=now)
    session.flush()


# ------------------------------------------------------------------ agents
def list_agents_for_admin(session: Session) -> list[tuple[Agent, int]]:
    counts = dict(
        session.execute(
            select(Ticket.assignee_id, func.count(Ticket.id))
            .where(Ticket.status.in_(ACTIVE_STATUSES), Ticket.assignee_id.is_not(None))
            .group_by(Ticket.assignee_id)
        ).all()
    )
    agents = session.scalars(select(Agent).order_by(Agent.is_active.desc(), Agent.name)).all()
    return [(a, counts.get(a.id, 0)) for a in agents]


def create_agent(
    session: Session,
    lead: Agent,
    *,
    name: str,
    email: str,
    password: str,
    role: str,
    iterations: int,
    now: datetime,
) -> Agent:
    email = normalize_email(email)
    check_password(password)
    if role not in ROLES:
        raise bad_request("bad_role", "Role must be agent or lead.")
    if session.scalar(select(Agent.id).where(Agent.email == email)) is not None:
        raise conflict("email_in_use", "An agent with this email already exists.")
    agent = Agent(
        name=name.strip(), email=email, role=role, is_active=True,
        password_hash=security.hash_password(password, iterations),
    )
    session.add(agent)
    session.flush()
    audit.record(
        session, agent_actor(lead), "agent.created", occurred_at=now,
        details={"agent_id": agent.id, "role": role},
    )
    session.flush()
    return agent


def _get_agent(session: Session, agent_id: int) -> Agent:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise not_found("Agent")
    return agent


def set_agent_active(session: Session, lead: Agent, agent_id: int, active: bool, now: datetime) -> Agent:
    agent = _get_agent(session, agent_id)
    if agent.is_active == active:
        return agent
    if not active:
        if agent.id == lead.id:
            raise bad_request("cannot_deactivate_self", "You cannot deactivate your own account.")
        owned = session.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.assignee_id == agent.id, Ticket.status.in_(ACTIVE_STATUSES)
            )
        )
        if owned:
            raise conflict(
                "has_active_tickets",
                f"{agent.name} still owns {owned} active ticket(s). Reassign them first.",
                active_tickets=owned,
            )
        if agent.role == "lead":
            other_leads = session.scalar(
                select(func.count(Agent.id)).where(
                    Agent.role == "lead", Agent.is_active, Agent.id != agent.id
                )
            )
            if not other_leads:
                raise conflict("last_lead", "There must always be at least one active lead.")
    agent.is_active = active
    audit.record(
        session, agent_actor(lead), "agent.activated" if active else "agent.deactivated",
        occurred_at=now, details={"agent_id": agent.id},
    )
    session.flush()
    return agent


def reset_agent_password(
    session: Session, lead: Agent, agent_id: int, password: str, iterations: int, now: datetime
) -> Agent:
    check_password(password)
    agent = _get_agent(session, agent_id)
    agent.password_hash = security.hash_password(password, iterations)
    audit.record(
        session, agent_actor(lead), "agent.password_reset", occurred_at=now,
        details={"agent_id": agent.id},
    )
    session.flush()
    return agent


def find_agent_by_email(session: Session, email: str) -> Optional[Agent]:
    return session.scalar(select(Agent).where(Agent.email == email.strip().lower()))
