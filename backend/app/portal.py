"""The customer-facing API: sign up, sign in, raise tickets, follow and answer them.

Everything here is scoped to the signed-in customer's own tickets, and every message
is read through the `customer_messages` view, so private team notes cannot appear.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import accounts, clock, security, service, throttle, views
from . import schemas as s
from .config import Settings
from .deps import current_customer, get_session, get_settings
from .errors import DomainError, not_found
from .models import Customer, Ticket

portal = APIRouter(prefix="/portal", tags=["customer portal"])

_DUMMY_HASH = security.hash_password("not-a-real-password", 1000)


def _out(c: Customer) -> s.CustomerOut:
    return s.CustomerOut(id=c.id, name=c.name, email=c.email)


def _login_out(settings: Settings, c: Customer) -> s.CustomerLoginOut:
    return s.CustomerLoginOut(token=security.create_token(settings, security.CUSTOMER, c.id), customer=_out(c))


@portal.post("/signup", response_model=s.CustomerLoginOut, status_code=201)
def signup(
    body: s.SignupIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    customer = accounts.signup_customer(
        session, name=body.name, email=body.email, password=body.password,
        iterations=settings.password_iterations, now=clock.now(),
    )
    session.commit()
    return _login_out(settings, customer)


@portal.post("/login", response_model=s.CustomerLoginOut)
def login(
    body: s.LoginIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    email = body.email.strip().lower()
    if throttle.customer_logins.blocked(email):
        raise DomainError(429, "too_many_attempts", "Too many failed logins. Try again in a few minutes.")
    customer = session.scalar(select(Customer).where(Customer.email == email))
    stored = customer.password_hash if customer and customer.password_hash else _DUMMY_HASH
    ok = security.verify_password(body.password, stored)
    if not (customer and customer.password_hash and ok):
        throttle.customer_logins.record_failure(email)
        raise DomainError(401, "bad_credentials", "Incorrect email or password.")
    throttle.customer_logins.reset(email)
    return _login_out(settings, customer)


@portal.get("/me", response_model=s.CustomerOut)
def me(customer: Customer = Depends(current_customer)):
    return _out(customer)


@portal.post("/password", status_code=204)
def change_password(
    body: s.PasswordChangeIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    customer: Customer = Depends(current_customer),
):
    accounts.change_password(
        session, customer, service.customer_actor(customer),
        current=body.current_password, new=body.new_password,
        iterations=settings.password_iterations, now=clock.now(),
    )
    session.commit()


def _own(session: Session, customer: Customer, ticket_id: int) -> Ticket:
    ticket = session.get(Ticket, ticket_id, populate_existing=True)
    if ticket is None or ticket.customer_id != customer.id:
        raise not_found()
    return ticket


def _view(session: Session, customer: Customer, ticket_id: int) -> s.PortalTicketView:
    session.expire_all()
    ticket = _own(session, customer, ticket_id)
    return views.portal_view(session, ticket, service.get_holidays(session), clock.now())


@portal.get("/tickets", response_model=list[s.PortalTicketSummary])
def my_tickets(session: Session = Depends(get_session), customer: Customer = Depends(current_customer)):
    return views.list_portal_tickets(session, customer)


@portal.post("/tickets", response_model=s.PortalTicketView, status_code=201)
def create_ticket(
    body: s.PortalTicketCreateIn,
    session: Session = Depends(get_session),
    customer: Customer = Depends(current_customer),
):
    ticket = service.create_ticket_as_customer(
        session, customer, subject=body.subject, description=body.description,
        priority=body.priority, now=clock.now(),
    )
    ticket_id = ticket.id
    session.commit()
    return _view(session, customer, ticket_id)


@portal.get("/tickets/{ticket_id}", response_model=s.PortalTicketView)
def get_ticket(
    ticket_id: int, session: Session = Depends(get_session), customer: Customer = Depends(current_customer)
):
    return _view(session, customer, ticket_id)


@portal.post("/tickets/{ticket_id}/messages", response_model=s.PortalTicketView, status_code=201)
def reply(
    ticket_id: int,
    body: s.ReplyIn,
    session: Session = Depends(get_session),
    customer: Customer = Depends(current_customer),
):
    service.customer_reply(session, customer, ticket_id, body.body, clock.now())
    session.commit()
    return _view(session, customer, ticket_id)


@portal.post("/tickets/{ticket_id}/reopen", response_model=s.PortalTicketView)
def reopen(
    ticket_id: int,
    body: s.ReopenIn,
    session: Session = Depends(get_session),
    customer: Customer = Depends(current_customer),
):
    service.customer_reopen_ticket(session, customer, ticket_id, body.message, clock.now())
    session.commit()
    return _view(session, customer, ticket_id)


@portal.get("/tickets/{ticket_id}/transcript")
def transcript(
    ticket_id: int, session: Session = Depends(get_session), customer: Customer = Depends(current_customer)
):
    from fastapi.responses import PlainTextResponse

    ticket = _own(session, customer, ticket_id)
    return PlainTextResponse(views.transcript_text(session, ticket))
