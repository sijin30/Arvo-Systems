"""Database tables.

History tables (messages, audit_log, sla_pauses) are protected by database
triggers (see db.py) so that no application bug, and no one with a SQL prompt
who is not a superuser, can quietly rewrite what happened.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

TS = DateTime(timezone=True)

ROLES = ("agent", "lead")
STATUSES = ("new", "open", "waiting_customer", "resolved", "closed")
ACTIVE_STATUSES = ("new", "open", "waiting_customer")
PRIORITIES = ("urgent", "medium", "low")
MESSAGE_KINDS = ("public_reply", "internal_note", "customer_message")
CLOSE_REASONS = ("customer_inactive", "reopen_window_expired")
PAUSE_REASONS = ("waiting_customer", "resolved")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (CheckConstraint(_in("role", ROLES), name="agents_role_ck"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), default="agent")
    is_active: Mapped[bool] = mapped_column(default=True)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)


class Holiday(Base):
    __tablename__ = "holidays"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(_in("priority", PRIORITIES), name="tickets_priority_ck"),
        CheckConstraint(_in("status", STATUSES), name="tickets_status_ck"),
        CheckConstraint(
            "closed_reason IS NULL OR " + _in("closed_reason", CLOSE_REASONS),
            name="tickets_closed_reason_ck",
        ),
        # An unassigned ticket must be "new"; a ticket being worked must have an owner.
        CheckConstraint(
            "(status = 'new') = (assignee_id IS NULL) OR status IN ('closed', 'resolved')",
            name="tickets_owner_ck",
        ),
        Index("tickets_status_idx", "status"),
        Index("tickets_assignee_idx", "assignee_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(
        String(20), Computed("'FD-' || lpad(id::text, 4, '0')", persisted=True), unique=True
    )
    subject: Mapped[str] = mapped_column(String(200))
    priority: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="new")
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"))
    related_ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"))
    public_token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(TS)
    updated_at: Mapped[datetime] = mapped_column(TS)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(TS)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TS)
    closed_at: Mapped[Optional[datetime]] = mapped_column(TS)
    closed_reason: Mapped[Optional[str]] = mapped_column(String(30))
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    response_breach_logged_at: Mapped[Optional[datetime]] = mapped_column(TS)
    resolution_breach_logged_at: Mapped[Optional[datetime]] = mapped_column(TS)

    customer: Mapped[Customer] = relationship(lazy="joined")
    assignee: Mapped[Optional[Agent]] = relationship(lazy="joined")
    related_ticket: Mapped[Optional["Ticket"]] = relationship(remote_side=[id], lazy="joined")
    pauses: Mapped[list["SlaPause"]] = relationship(
        order_by="SlaPause.started_at", lazy="selectin", back_populates="ticket"
    )


class Message(Base):
    """Every reply and note.  Rows can never be updated or deleted."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(_in("kind", MESSAGE_KINDS), name="messages_kind_ck"),
        CheckConstraint(_in("visibility", ("public", "internal")), name="messages_visibility_ck"),
        CheckConstraint(
            "(kind = 'internal_note') = (visibility = 'internal')", name="messages_visibility_kind_ck"
        ),
        CheckConstraint(
            "(kind = 'customer_message') = (author_type = 'customer')", name="messages_author_ck"
        ),
        CheckConstraint("length(btrim(body)) > 0", name="messages_body_ck"),
        Index("messages_ticket_idx", "ticket_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    kind: Mapped[str] = mapped_column(String(20))
    visibility: Mapped[str] = mapped_column(String(10))
    author_type: Mapped[str] = mapped_column(String(10))  # 'agent' | 'customer'
    # The agent who wrote the message, or who logged it on the customer's behalf.
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS)
    # Written by the database itself, independent of the application's clock.
    recorded_at: Mapped[datetime] = mapped_column(TS, server_default=text("clock_timestamp()"))

    agent: Mapped[Optional[Agent]] = relationship(lazy="joined")


class SlaPause(Base):
    """A stretch of time during which a ticket's SLA clock is stopped."""

    __tablename__ = "sla_pauses"
    __table_args__ = (
        CheckConstraint(_in("reason", PAUSE_REASONS), name="sla_pauses_reason_ck"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="sla_pauses_order_ck"),
        Index(
            "sla_pauses_one_open_idx",
            "ticket_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    reason: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(TS)
    ended_at: Mapped[Optional[datetime]] = mapped_column(TS)

    ticket: Mapped[Ticket] = relationship(back_populates="pauses")


class AuditLog(Base):
    """Append-only, hash-chained record of everything that happens.

    `seq`, `prev_hash`, `row_hash` and `recorded_at` are filled in by a database
    trigger; the application cannot choose them.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, unique=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"))
    actor_type: Mapped[str] = mapped_column(String(10))  # agent | system
    actor_id: Mapped[Optional[int]] = mapped_column(Integer)
    actor_name: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(TS)
    recorded_at: Mapped[datetime] = mapped_column(TS)
    prev_hash: Mapped[str] = mapped_column(String(64))
    row_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(_in("actor_type", ("agent", "system")), name="audit_actor_type_ck"),
        Index("audit_ticket_idx", "ticket_id", "seq"),
    )


# A read-only window onto messages that a customer is allowed to see.  Anything that
# builds a customer-facing response must read from this view and never from `messages`.
_view_metadata = MetaData()
customer_messages = Table(
    "customer_messages",
    _view_metadata,
    Column("id", Integer),
    Column("ticket_id", Integer),
    Column("kind", String),
    Column("author_type", String),
    Column("body", Text),
    Column("created_at", TS),
)
