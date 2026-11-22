"""Request and response shapes.

Two families of response models exist on purpose:

* Agent models (`AgentMessage`, `TicketDetail`) may carry internal notes.
* Customer models (`CustomerMessage`, `CustomerTicketView`) have no field at all that
  could hold an internal note, its author, or its visibility flag.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Priority = Literal["urgent", "medium", "low"]
Status = Literal["new", "open", "waiting_customer", "resolved", "closed"]
MessageKind = Literal["public_reply", "internal_note", "customer_message"]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean(value: str) -> str:
    return value.strip()


# ---------------------------------------------------------------- inputs
class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)


class TicketCreateIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    priority: Priority
    customer_name: str = Field(min_length=1, max_length=120)
    customer_email: str = Field(max_length=255)
    related_ticket_id: Optional[int] = None

    @field_validator("subject", "description", "customer_name", mode="after")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("customer_email", mode="after")
    @classmethod
    def _email(cls, v: str) -> str:
        v = _clean(v).lower()
        if not _EMAIL.match(v):
            raise ValueError("must be a valid email address")
        return v


class MessageIn(BaseModel):
    kind: MessageKind
    body: str = Field(min_length=1, max_length=10000)
    # Only valid together with kind=public_reply: "I asked a question, now I wait".
    set_waiting: bool = False

    @field_validator("body", mode="after")
    @classmethod
    def _body(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("must not be blank")
        return v


class ResolveIn(BaseModel):
    message: Optional[str] = Field(default=None, max_length=10000)

    @field_validator("message", mode="after")
    @classmethod
    def _msg(cls, v: Optional[str]) -> Optional[str]:
        return _clean(v) or None if v is not None else None


class ReopenIn(ResolveIn):
    pass


class PriorityIn(BaseModel):
    priority: Priority


class AssignIn(BaseModel):
    agent_id: int


class HolidayIn(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=120)


# --------------------------------------------------------------- outputs
class AgentRef(BaseModel):
    id: int
    name: str


class AgentOut(AgentRef):
    email: str
    role: str


class LoginOut(BaseModel):
    token: str
    agent: AgentOut


class CustomerRef(BaseModel):
    id: int
    name: str
    email: str


class MetricOut(BaseModel):
    state: Literal["running", "paused", "met", "breached", "stopped"]
    budget_seconds: int
    due_at: Optional[datetime]
    remaining_seconds: int
    breached: bool


class SlaOut(BaseModel):
    response: MetricOut
    resolution: MetricOut
    late: bool
    waiting_on_customer: bool
    next_due_at: Optional[datetime]
    auto_close_at: Optional[datetime]
    reopen_until: Optional[datetime]


class TicketSummary(BaseModel):
    id: int
    reference: str
    subject: str
    priority: Priority
    status: Status
    customer: CustomerRef
    assignee: Optional[AgentRef]
    created_at: datetime
    updated_at: datetime
    first_response_at: Optional[datetime]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    closed_reason: Optional[str]
    reopen_count: int
    related_ticket_id: Optional[int]
    related_reference: Optional[str]
    late: bool
    sla: SlaOut


class TicketList(BaseModel):
    items: list[TicketSummary]
    total: int


class TicketCounts(BaseModel):
    active: int
    unassigned: int
    late: int
    waiting_on_customer: int


class AgentMessage(BaseModel):
    id: int
    kind: MessageKind
    visibility: Literal["public", "internal"]
    author_type: Literal["agent", "customer"]
    author: Optional[AgentRef]
    body: str
    created_at: datetime


class Actions(BaseModel):
    can_claim: bool
    can_release: bool
    can_assign: bool
    can_reply: bool
    can_note: bool
    can_log_customer_reply: bool
    can_resolve: bool
    can_reopen: bool
    can_change_priority: bool


class TicketDetail(TicketSummary):
    public_token: str
    messages: list[AgentMessage]
    actions: Actions


class AuditEntry(BaseModel):
    seq: int
    action: str
    actor_type: str
    actor_name: str
    occurred_at: datetime
    recorded_at: datetime
    details: dict


class AuditVerifyOut(BaseModel):
    intact: bool
    first_broken_seq: Optional[int]
    entries_checked: int


class HolidayOut(BaseModel):
    day: date
    name: str


class HousekeepingOut(BaseModel):
    auto_closed_waiting: int
    auto_closed_resolved: int
    breaches_logged: int


# ---------------------------------------------------- customer-safe shapes
class CustomerMessage(BaseModel):
    id: int
    sender: Literal["support", "you"]
    body: str
    created_at: datetime


class CustomerTicketView(BaseModel):
    reference: str
    subject: str
    status: Literal["received", "in_progress", "waiting_for_you", "resolved", "closed"]
    created_at: datetime
    messages: list[CustomerMessage]
