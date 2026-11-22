from datetime import date, datetime, timedelta

from app import sla
from app import worktime as wt

H: set[date] = set()


def ist(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=wt.IST)


def clock(priority="medium", status="open", created=None, first=None, reason=None, pauses=()):
    return sla.ClockInput(
        priority=priority,
        status=status,
        created_at=created or ist(2026, 11, 23, 10, 0),
        first_response_at=first,
        closed_reason=reason,
        pauses=list(pauses),
    )


# ---- policies ---------------------------------------------------------------
def test_policy_budgets():
    assert sla.POLICIES["urgent"].response == timedelta(hours=2)
    assert sla.POLICIES["medium"].response == timedelta(hours=4, minutes=30)  # half a 9h day
    assert sla.POLICIES["medium"].resolution == timedelta(hours=27)  # 3 working days
    assert sla.POLICIES["low"].response == timedelta(hours=9)  # 1 working day
    assert sla.POLICIES["low"].resolution == timedelta(hours=45)  # 5 working days


def test_urgent_fix_budget_is_one_full_working_day():
    assert sla.POLICIES["urgent"].resolution == timedelta(hours=9)
    created = ist(2026, 11, 23, 14, 0)
    r = sla.compute_sla(clock("urgent", status="new", created=created), H, created)
    assert r.resolution.due_at == ist(2026, 11, 24, 14, 0)  # 4.5h Monday + 4.5h Tuesday


# ---- running clock -----------------------------------------------------------
def test_response_running_then_breached():
    c = clock("urgent", status="new", created=ist(2026, 11, 23, 10, 0))
    r = sla.compute_sla(c, H, ist(2026, 11, 23, 11, 0))
    assert r.response.state == "running"
    assert r.response.due_at == ist(2026, 11, 23, 12, 0)
    assert r.response.remaining == timedelta(hours=1)
    assert not r.late
    r = sla.compute_sla(c, H, ist(2026, 11, 23, 12, 30))
    assert r.response.state == "breached"
    assert r.response.remaining == -timedelta(minutes=30)
    assert r.late


def test_friday_evening_ticket_not_late_over_the_weekend():
    c = clock("urgent", status="new", created=ist(2026, 11, 20, 18, 0))
    r = sla.compute_sla(c, H, ist(2026, 11, 22, 9, 0))  # Sunday morning
    assert not r.late
    assert r.response.due_at == ist(2026, 11, 23, 11, 0)
    # 30 working minutes on Friday + 8.5h on Monday = Monday 18:00
    assert r.resolution.due_at == ist(2026, 11, 23, 18, 0)
    assert not r.resolution.breached


def test_response_met_records_how_it_went():
    c = clock("medium", created=ist(2026, 11, 23, 10, 0), first=ist(2026, 11, 23, 12, 0))
    r = sla.compute_sla(c, H, ist(2026, 11, 25, 10, 0))
    assert r.response.state == "met"
    assert not r.response.breached


def test_response_met_late_is_breached():
    c = clock("urgent", created=ist(2026, 11, 23, 10, 0), first=ist(2026, 11, 23, 15, 0))
    r = sla.compute_sla(c, H, ist(2026, 11, 24, 10, 0))
    assert r.response.state == "breached"
    assert r.late


# ---- pausing ---------------------------------------------------------------
def test_waiting_for_customer_pauses_the_clock():
    created = ist(2026, 11, 23, 10, 0)
    first = ist(2026, 11, 23, 10, 30)
    pause = sla.Pause(start=ist(2026, 11, 23, 11, 0), end=None)
    c = clock("medium", status="waiting_customer", created=created, first=first, pauses=[pause])
    for now in (ist(2026, 11, 24, 10, 0), ist(2026, 12, 4, 10, 0)):
        r = sla.compute_sla(c, H, now)
        assert r.resolution.state == "paused"
        assert r.resolution.due_at is None
        assert r.resolution.remaining == timedelta(hours=27) - timedelta(hours=1)
        assert r.waiting_on_customer
        assert not r.late


def test_resume_continues_with_remaining_time_not_a_fresh_start():
    created = ist(2026, 11, 23, 10, 0)
    pause = sla.Pause(ist(2026, 11, 23, 11, 0), ist(2026, 11, 26, 11, 0))  # waited 3 working days
    c = clock("medium", status="open", created=created, first=ist(2026, 11, 23, 10, 30), pauses=[pause])
    # without the pause the resolution due is Wed 25 Nov 19:30 -> 18:30 Wed... compute explicitly:
    no_pause_due = wt.add_working_time(created, timedelta(hours=27), H)
    r = sla.compute_sla(c, H, ist(2026, 11, 26, 12, 0))
    assert r.resolution.due_at > no_pause_due
    # 1h used before pausing, so 26h are left after resume at Thu 11:00
    assert r.resolution.due_at == wt.add_working_time(ist(2026, 11, 26, 11, 0), timedelta(hours=26), H)
    assert r.resolution.state == "running"
    assert not r.late


def test_long_wait_is_not_counted_against_us():
    created = ist(2026, 11, 2, 10, 0)  # Monday
    pause = sla.Pause(ist(2026, 11, 2, 12, 0), ist(2026, 11, 9, 12, 0))  # a week's silence
    c = clock("medium", status="open", created=created, first=ist(2026, 11, 2, 11, 0), pauses=[pause])
    r = sla.compute_sla(c, H, ist(2026, 11, 9, 13, 0))
    assert not r.late


def test_pause_after_breach_does_not_undo_breach():
    created = ist(2026, 11, 23, 10, 0)
    c = clock(
        "urgent",
        status="waiting_customer",
        created=created,
        first=ist(2026, 11, 23, 13, 0),  # 1h late
        pauses=[sla.Pause(ist(2026, 11, 23, 13, 0), None)],
    )
    r = sla.compute_sla(c, H, ist(2026, 11, 30, 10, 0))
    assert r.response.breached
    assert r.late


# ---- priority change -------------------------------------------------------
def test_priority_change_recomputes_from_creation_with_new_policy():
    created = ist(2026, 11, 23, 10, 0)
    now = ist(2026, 11, 23, 14, 0)  # 4h in, no reply yet
    as_medium = sla.compute_sla(clock("medium", status="new", created=created), H, now)
    assert not as_medium.response.breached  # 4.5h budget
    as_urgent = sla.compute_sla(clock("urgent", status="new", created=created), H, now)
    assert as_urgent.response.breached  # 2h budget measured from creation
    assert as_urgent.late


# ---- resolution / close ----------------------------------------------------
def test_resolved_ticket_shows_met_and_reopen_deadline():
    created = ist(2026, 11, 23, 10, 0)
    resolved = ist(2026, 11, 24, 10, 0)
    c = clock(
        "medium",
        status="resolved",
        created=created,
        first=ist(2026, 11, 23, 11, 0),
        pauses=[sla.Pause(resolved, None)],
    )
    r = sla.compute_sla(c, H, ist(2026, 11, 27, 10, 0))
    assert r.resolution.state == "met"
    assert not r.late
    assert r.reopen_until == wt.add_working_time(resolved, timedelta(hours=45), H)


def test_resolved_late_stays_marked_late_for_managers():
    created = ist(2026, 11, 23, 10, 0)
    resolved = ist(2026, 12, 4, 10, 0)
    c = clock(
        "medium",
        status="resolved",
        created=created,
        first=ist(2026, 11, 23, 11, 0),
        pauses=[sla.Pause(resolved, None)],
    )
    r = sla.compute_sla(c, H, ist(2026, 12, 10, 10, 0))
    assert r.resolution.state == "breached"
    assert r.late


def test_closed_for_customer_silence_is_stopped_not_met():
    created = ist(2026, 11, 23, 10, 0)
    c = clock(
        "medium",
        status="closed",
        reason="customer_inactive",
        created=created,
        first=ist(2026, 11, 23, 11, 0),
        pauses=[sla.Pause(ist(2026, 11, 23, 12, 0), None)],
    )
    r = sla.compute_sla(c, H, ist(2026, 12, 20, 10, 0))
    assert r.resolution.state == "stopped"
    assert not r.late


def test_auto_close_after_one_working_week_of_silence():
    start = ist(2026, 11, 23, 12, 0)  # Monday noon
    just_before = wt.add_working_time(start, timedelta(hours=45), H) - timedelta(minutes=1)
    exactly = wt.add_working_time(start, timedelta(hours=45), H)
    assert not sla.should_auto_close_waiting(start, just_before, H)
    assert sla.should_auto_close_waiting(start, exactly, H)


def test_weekend_does_not_count_towards_auto_close():
    start = ist(2026, 11, 20, 12, 0)  # Friday noon
    sunday = ist(2026, 11, 22, 12, 0)
    assert not sla.should_auto_close_waiting(start, sunday, H)


def test_waiting_ticket_reports_auto_close_time():
    pause_start = ist(2026, 11, 23, 12, 0)
    c = clock(
        "low",
        status="waiting_customer",
        first=ist(2026, 11, 23, 11, 0),
        pauses=[sla.Pause(pause_start, None)],
    )
    r = sla.compute_sla(c, H, ist(2026, 11, 24, 10, 0))
    assert r.auto_close_at == wt.add_working_time(pause_start, timedelta(hours=45), H)


def test_reopen_window():
    resolved = ist(2026, 11, 23, 12, 0)
    limit = wt.add_working_time(resolved, timedelta(hours=45), H)
    assert sla.reopen_window_open(resolved, limit, H)
    assert not sla.reopen_window_open(resolved, limit + timedelta(minutes=1), H)


def test_holiday_is_respected_in_deadlines():
    hol = {date(2026, 11, 24)}
    c = clock("medium", status="new", created=ist(2026, 11, 23, 18, 0))
    r = sla.compute_sla(c, hol, ist(2026, 11, 24, 12, 0))
    assert not r.late  # Tuesday is a holiday: nothing elapses
    assert r.response.due_at == wt.add_working_time(
        ist(2026, 11, 23, 18, 0), timedelta(hours=4, minutes=30), hol
    )
    assert r.response.due_at.astimezone(wt.IST).date() == date(2026, 11, 25)
