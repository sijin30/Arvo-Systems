"""Background housekeeping: auto-close and SLA breach logging.

Safe to run as often as you like, and safe if two copies run at once: each ticket is
re-checked under its own row lock before anything is changed.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from . import audit, clock, sla
from .models import Ticket
from .schemas import HousekeepingOut
from .service import get_holidays, lock_ticket, open_pause, sync_breaches

log = logging.getLogger("frontdesk.jobs")


def _auto_close(session: Session, ticket: Ticket, reason: str, now: datetime, detail: dict) -> None:
    previous = ticket.status
    ticket.status = "closed"
    ticket.closed_reason = reason
    ticket.closed_at = now
    ticket.updated_at = now
    audit.record(
        session, audit.SYSTEM, "ticket.auto_closed", occurred_at=now, ticket_id=ticket.id,
        details={"from": previous, "reason": reason, **detail},
    )


def run_housekeeping(factory: sessionmaker[Session], now: Optional[datetime] = None) -> HousekeepingOut:
    now = now or clock.now()
    closed_waiting = closed_resolved = breaches = 0

    with factory() as session:
        holidays = get_holidays(session)
        ids = list(
            session.scalars(
                select(Ticket.id).where(Ticket.status.in_(("new", "open", "waiting_customer", "resolved")))
            )
        )
        session.rollback()

    for ticket_id in ids:
        with factory() as session:
            try:
                ticket = lock_ticket(session, ticket_id)
                pause = open_pause(ticket)
                if ticket.status == "waiting_customer" and pause is not None:
                    if sla.should_auto_close_waiting(pause.started_at, now, holidays):
                        _auto_close(
                            session, ticket, "customer_inactive", now,
                            {"waiting_since": pause.started_at},
                        )
                        closed_waiting += 1
                elif ticket.status == "resolved" and ticket.resolved_at is not None:
                    if not sla.reopen_window_open(ticket.resolved_at, now, holidays):
                        _auto_close(
                            session, ticket, "reopen_window_expired", now,
                            {"resolved_at": ticket.resolved_at},
                        )
                        closed_resolved += 1
                breaches += sync_breaches(session, ticket, holidays, now)
                session.commit()
            except Exception:  # keep going: one bad ticket must not stop the sweep
                session.rollback()
                log.exception("housekeeping failed for ticket %s", ticket_id)

    return HousekeepingOut(
        auto_closed_waiting=closed_waiting,
        auto_closed_resolved=closed_resolved,
        breaches_logged=breaches,
    )


class Scheduler:
    """Runs housekeeping every `interval` seconds on a background thread."""

    def __init__(self, factory: sessionmaker[Session], interval: float = 60.0):
        self._factory = factory
        self._interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="housekeeping", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_housekeeping(self._factory)
            except Exception:
                log.exception("housekeeping run failed")
            self._stop.wait(self._interval)
