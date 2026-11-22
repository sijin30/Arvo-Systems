"""SLA engine: deadlines, pausing, breach detection.  Pure functions, no I/O.

Rules taken from the support lead's meeting notes:

* urgent  - reply within 2 working hours, fix within one working day
* medium  - reply within half a working day, fix within 3 working days
* low     - reply within 1 working day, fix within 5 working days
* all measured in working time (see worktime.py)
* the clock STOPS while we wait for the customer, and while a ticket is
  resolved; it carries on with the remaining time afterwards
* waiting for ~1 working week of customer silence closes the ticket
* a resolved ticket can be reopened for ~1 working week

Changing priority recomputes the deadlines from the creation time using the new
priority's policy (already-consumed and paused time are kept).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Collection, Optional, Sequence

from . import worktime as wt

PRIORITIES = ("urgent", "medium", "low")


@dataclass(frozen=True)
class Policy:
    response: timedelta
    resolution: timedelta


POLICIES: dict[str, Policy] = {
    # "Same working day" = one full working day (9 working hours) from arrival.
    # Measuring it to 18:30 of the arrival date instead would make a ticket that
    # arrives at 6 PM on Friday late by Sunday, which the brief explicitly forbids.
    "urgent": Policy(response=timedelta(hours=2), resolution=wt.WORKDAY),
    "medium": Policy(response=wt.WORKDAY / 2, resolution=3 * wt.WORKDAY),
    "low": Policy(response=wt.WORKDAY, resolution=5 * wt.WORKDAY),
}

AUTO_CLOSE_AFTER = 5 * wt.WORKDAY  # customer silence while we wait
REOPEN_WINDOW = 5 * wt.WORKDAY  # after a ticket is marked resolved


@dataclass(frozen=True)
class Pause:
    start: datetime
    end: Optional[datetime]  # None = still paused


@dataclass(frozen=True)
class ClockInput:
    priority: str
    status: str
    created_at: datetime
    first_response_at: Optional[datetime]
    closed_reason: Optional[str]
    pauses: Sequence[Pause]


@dataclass(frozen=True)
class Metric:
    state: str  # running | paused | met | breached | stopped
    budget: timedelta
    due_at: Optional[datetime]  # None while the clock is paused and not yet breached
    remaining: timedelta  # negative once late
    breached: bool


@dataclass(frozen=True)
class SlaResult:
    response: Metric
    resolution: Metric
    late: bool
    waiting_on_customer: bool
    next_due_at: Optional[datetime]
    auto_close_at: Optional[datetime]
    reopen_until: Optional[datetime]


def due_before(
    created_at: datetime,
    budget: timedelta,
    pauses: Sequence[Pause],
    ref: datetime,
    holidays: Collection[date],
) -> datetime:
    """Deadline in force at instant `ref`, counting only pauses that began before it.

    A pause that begins after the deadline has already passed cannot rescue the
    ticket, so it does not push the deadline back.
    """
    due = wt.add_working_time(created_at, budget, holidays)
    for pause in sorted(pauses, key=lambda p: p.start):
        if pause.start >= ref or pause.start >= due:
            break
        end = min(pause.end, ref) if pause.end is not None else ref
        if end <= pause.start:
            continue
        paused_work = wt.working_time_between(pause.start, end, holidays)
        due = max(wt.add_working_time(due, paused_work, holidays), end)
    return due


def _metric(
    created_at: datetime,
    budget: timedelta,
    pauses: Sequence[Pause],
    ref: datetime,
    holidays: Collection[date],
    ok_state: str,
) -> Metric:
    due = due_before(created_at, budget, pauses, ref, holidays)
    breached = ref > due
    if breached:
        remaining = -wt.working_time_between(due, ref, holidays)
    else:
        remaining = wt.working_time_between(ref, due, holidays)
    state = "breached" if breached else ok_state
    due_at = None if (state == "paused") else due
    return Metric(state=state, budget=budget, due_at=due_at, remaining=remaining, breached=breached)


def compute_sla(clock: ClockInput, holidays: Collection[date], now: datetime) -> SlaResult:
    policy = POLICIES[clock.priority]
    open_pause = next((p.start for p in clock.pauses if p.end is None), None)

    # --- first response ---------------------------------------------------
    if clock.first_response_at is not None:
        r_ref, r_ok = clock.first_response_at, "met"
    elif open_pause is not None:
        r_ref, r_ok = open_pause, "paused"
    else:
        r_ref, r_ok = now, "running"
    response = _metric(clock.created_at, policy.response, clock.pauses, r_ref, holidays, r_ok)

    # --- resolution -------------------------------------------------------
    s = clock.status
    if s in ("new", "open"):
        x_ref, x_ok = now, "running"
    elif s == "waiting_customer":
        x_ref, x_ok = open_pause or now, "paused"
    elif s == "resolved":
        x_ref, x_ok = open_pause or now, "met"
    else:  # closed
        x_ref = open_pause or now
        x_ok = "met" if clock.closed_reason == "reopen_window_expired" else "stopped"
    budget = policy.resolution
    resolution = _metric(clock.created_at, budget, clock.pauses, x_ref, holidays, x_ok)

    waiting = s == "waiting_customer"
    auto_close_at = (
        wt.add_working_time(open_pause, AUTO_CLOSE_AFTER, holidays)
        if waiting and open_pause is not None
        else None
    )
    reopen_until = (
        wt.add_working_time(open_pause, REOPEN_WINDOW, holidays)
        if s == "resolved" and open_pause is not None
        else None
    )

    pending = []
    if response.state == "running" and response.due_at:
        pending.append(response.due_at)
    if resolution.state == "running" and resolution.due_at:
        pending.append(resolution.due_at)
    return SlaResult(
        response=response,
        resolution=resolution,
        late=response.breached or resolution.breached,
        waiting_on_customer=waiting,
        next_due_at=min(pending) if pending else None,
        auto_close_at=auto_close_at,
        reopen_until=reopen_until,
    )


def should_auto_close_waiting(
    pause_start: datetime, now: datetime, holidays: Collection[date]
) -> bool:
    return wt.working_time_between(pause_start, now, holidays) >= AUTO_CLOSE_AFTER


def reopen_window_open(
    resolved_at: datetime, now: datetime, holidays: Collection[date]
) -> bool:
    return wt.working_time_between(resolved_at, now, holidays) <= REOPEN_WINDOW
