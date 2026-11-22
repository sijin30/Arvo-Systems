"""First-run data: the nine agents, a starter holiday list and a few demo tickets."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from . import clock, security, service
from .config import Settings
from .models import Agent, Holiday

AGENTS = [
    ("Meera Nair", "meera", "lead"),
    ("Arjun Menon", "arjun", "agent"),
    ("Anjali Krishnan", "anjali", "agent"),
    ("Rahul Varma", "rahul", "agent"),
    ("Sneha Thomas", "sneha", "agent"),
    ("Vishnu Das", "vishnu", "agent"),
    ("Neha George", "neha", "agent"),
    ("Kiran Joseph", "kiran", "agent"),
    ("Fathima Rahman", "fathima", "agent"),
]
EMAIL_DOMAIN = "arvosystems.example"

# Only dates that never move.  Festival dates that change every year (Onam, Vishu,
# Eid, Diwali ...) are added by the support lead on the Holidays page.
HOLIDAYS = [
    (date(2026, 1, 26), "Republic Day"),
    (date(2026, 4, 3), "Good Friday"),
    (date(2026, 5, 1), "May Day"),
    (date(2026, 8, 15), "Independence Day"),
    (date(2026, 10, 2), "Gandhi Jayanti"),
    (date(2026, 12, 25), "Christmas"),
    (date(2027, 1, 26), "Republic Day"),
    (date(2027, 3, 26), "Good Friday"),
    (date(2027, 5, 1), "May Day"),
    (date(2027, 8, 15), "Independence Day"),
    (date(2027, 10, 2), "Gandhi Jayanti"),
    (date(2027, 12, 25), "Christmas"),
]


def seed_if_empty(factory: sessionmaker[Session], settings: Settings) -> None:
    with factory() as session:
        if session.scalar(select(func.count(Agent.id))):
            return
        for name, handle, role in AGENTS:
            session.add(
                Agent(
                    name=name,
                    email=f"{handle}@{EMAIL_DOMAIN}",
                    password_hash=security.hash_password(settings.demo_password, settings.password_iterations),
                    role=role,
                )
            )
        for day, name in HOLIDAYS:
            session.add(Holiday(day=day, name=name))
        session.commit()
        _demo_tickets(session)
        session.commit()


def _demo_tickets(session: Session) -> None:
    """A handful of tickets that show late, waiting and reopenable states.

    Times are backdated through the service layer, so the history is genuine.
    """
    now = clock.now()
    agents = {a.email.split("@")[0]: a for a in session.scalars(select(Agent))}
    arjun, meera = agents["arjun"], agents["meera"]

    def make(subject, body, priority, who, email, created):
        ticket = service.create_ticket(
            session, meera, subject=subject, description=body, priority=priority,
            customer_name=who, customer_email=email, related_ticket_id=None, now=created,
        )
        session.flush()
        return ticket.id

    # 1. Urgent and nobody has picked it up: late.
    make(
        "Entire finance team locked out of the portal",
        "Nobody in our finance team can sign in since this morning. We cannot process salaries.",
        "urgent", "Priya Raghavan", "priya@brightfin.example", now - timedelta(days=5),
    )

    # 2. Fresh urgent ticket, still inside its deadline.
    make(
        "Invoices are not downloading",
        "The download button on the invoices page does nothing.",
        "urgent", "Thomas Kurian", "thomas@keralaspice.example", now - timedelta(minutes=10),
    )

    # 3. Waiting on the customer (clock paused), with a private team note on it.
    t = make(
        "Export fails for large reports",
        "Exporting more than 5,000 rows to Excel ends with an error.",
        "medium", "Divya Shankar", "divya@harbourlogistics.example", now - timedelta(days=4),
    )
    service.claim_ticket(session, arjun, t, now - timedelta(days=4) + timedelta(minutes=20))
    service.add_message(
        session, arjun, t, kind="internal_note", set_waiting=False,
        body="Long-standing customer, been with us since 2019. Keep the tone warm and avoid jargon.",
        now=now - timedelta(days=4) + timedelta(minutes=25),
    )
    service.add_message(
        session, arjun, t, kind="public_reply", set_waiting=True,
        body="Thanks for reporting this. Could you tell us which browser you use and share the report name?",
        now=now - timedelta(days=4) + timedelta(minutes=40),
    )

    # 4. Being worked on, but already past its fix deadline.
    t = make(
        "Dashboard totals look wrong",
        "The monthly totals on the dashboard do not match our own sheet.",
        "medium", "Suresh Iyer", "suresh@coastalmart.example", now - timedelta(days=12),
    )
    service.claim_ticket(session, meera, t, now - timedelta(days=12) + timedelta(minutes=30))
    service.add_message(
        session, meera, t, kind="public_reply", set_waiting=False,
        body="We are looking into the totals and will update you shortly.",
        now=now - timedelta(days=12) + timedelta(hours=1),
    )

    # 5. Resolved yesterday: the customer can still reopen it.
    t = make(
        "How do I add a new user?",
        "Where can I add a colleague to our account?",
        "low", "Aisha Khan", "aisha@seabreeze.example", now - timedelta(days=3),
    )
    service.claim_ticket(session, arjun, t, now - timedelta(days=3) + timedelta(minutes=15))
    service.resolve_ticket(
        session, arjun, t,
        "Go to Settings > Team > Invite user. We have also emailed you a short guide.",
        now - timedelta(days=1),
    )
