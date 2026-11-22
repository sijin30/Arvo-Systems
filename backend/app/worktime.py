"""Working-time arithmetic for Arvo's support desk.

Arvo works 09:30-18:30 (India Standard Time), Monday to Friday, excluding
festival holidays.  Every SLA number in Frontdesk is measured in this
"working time", never in wall-clock time.  This module is pure (no database,
no clock) so it can be tested exhaustively.

Convention used everywhere: when a span of working time ends exactly at the end
of a working day, the resulting instant is that end of day (18:30), not the next
morning (09:30).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Collection

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

WORK_START = time(9, 30)
WORK_END = time(18, 30)
WORKDAY = timedelta(hours=9)  # 09:30 -> 18:30

_ONE_DAY = timedelta(days=1)
_MAX_DAYS = 3700  # ~10 years; guards against runaway loops


def _ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime is not allowed; use timezone-aware values")
    return dt.astimezone(IST)


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


def is_working_day(day: date, holidays: Collection[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Opening and closing instant (IST) of the working day `day`."""
    return (
        datetime.combine(day, WORK_START, tzinfo=IST),
        datetime.combine(day, WORK_END, tzinfo=IST),
    )


def is_working_time(moment: datetime, holidays: Collection[date]) -> bool:
    m = _ist(moment)
    if not is_working_day(m.date(), holidays):
        return False
    start, end = day_bounds(m.date())
    return start <= m < end


def working_time_between(a: datetime, b: datetime, holidays: Collection[date]) -> timedelta:
    """Working time that elapses between instants `a` and `b` (0 if b <= a)."""
    a, b = _ist(a), _ist(b)
    if b <= a:
        return timedelta(0)
    if (b.date() - a.date()).days > _MAX_DAYS:
        raise ValueError("time span too large")
    total = timedelta(0)
    day = a.date()
    last = b.date()
    while day <= last:
        if is_working_day(day, holidays):
            start, end = day_bounds(day)
            lo, hi = max(a, start), min(b, end)
            if hi > lo:
                total += hi - lo
        day += _ONE_DAY
    return total


def add_working_time(start: datetime, amount: timedelta, holidays: Collection[date]) -> datetime:
    """Earliest instant at which `amount` of working time has passed since `start`."""
    if amount <= timedelta(0):
        return _utc(start)
    t = _ist(start)
    remaining = amount
    day = t.date()
    for _ in range(_MAX_DAYS):
        if is_working_day(day, holidays):
            opens, closes = day_bounds(day)
            cursor = max(t, opens)
            if cursor < closes:
                available = closes - cursor
                if remaining <= available:
                    return _utc(cursor + remaining)
                remaining -= available
        day += _ONE_DAY
    raise ValueError("could not place working time within range")


def next_working_instant(moment: datetime, holidays: Collection[date]) -> datetime:
    """`moment` if it is inside working time, else the next opening time."""
    t = _ist(moment)
    day = t.date()
    for _ in range(_MAX_DAYS):
        if is_working_day(day, holidays):
            opens, closes = day_bounds(day)
            if t < closes:
                return _utc(max(t, opens))
        day += _ONE_DAY
    raise ValueError("no working day found within range")
