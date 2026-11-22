from datetime import date, datetime, timedelta

import pytest

from app import worktime as wt

NO_HOLIDAYS: set[date] = set()


def ist(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=wt.IST)


# 2026-11-20 is a Friday, 21 Saturday, 22 Sunday, 23 Monday.
def test_calendar_assumptions():
    assert date(2026, 11, 20).weekday() == 4
    assert date(2026, 11, 23).weekday() == 0


def test_workday_is_nine_hours():
    assert wt.WORKDAY == timedelta(hours=9)


def test_between_inside_one_day():
    a, b = ist(2026, 11, 23, 10, 0), ist(2026, 11, 23, 12, 30)
    assert wt.working_time_between(a, b, NO_HOLIDAYS) == timedelta(hours=2, minutes=30)


def test_between_ignores_before_open_and_after_close():
    a, b = ist(2026, 11, 23, 7, 0), ist(2026, 11, 23, 22, 0)
    assert wt.working_time_between(a, b, NO_HOLIDAYS) == timedelta(hours=9)


def test_friday_6pm_ticket_is_not_late_on_sunday():
    """The exact example from the brief."""
    created = ist(2026, 11, 20, 18, 0)  # Friday 6 PM
    sunday_morning = ist(2026, 11, 22, 9, 0)
    assert wt.working_time_between(created, sunday_morning, NO_HOLIDAYS) == timedelta(minutes=30)


def test_weekend_contributes_nothing():
    a, b = ist(2026, 11, 20, 18, 30), ist(2026, 11, 23, 9, 30)
    assert wt.working_time_between(a, b, NO_HOLIDAYS) == timedelta(0)


def test_holiday_is_skipped():
    hol = {date(2026, 11, 23)}  # pretend Monday is a holiday
    a, b = ist(2026, 11, 20, 18, 0), ist(2026, 11, 24, 10, 30)
    # 30 min Friday + 1 h Tuesday
    assert wt.working_time_between(a, b, hol) == timedelta(hours=1, minutes=30)


def test_between_reversed_is_zero():
    a, b = ist(2026, 11, 23, 12), ist(2026, 11, 23, 10)
    assert wt.working_time_between(a, b, NO_HOLIDAYS) == timedelta(0)


def test_add_within_day():
    out = wt.add_working_time(ist(2026, 11, 23, 10, 0), timedelta(hours=2), NO_HOLIDAYS)
    assert out == ist(2026, 11, 23, 12, 0)


def test_add_rolls_over_weekend():
    out = wt.add_working_time(ist(2026, 11, 20, 18, 0), timedelta(hours=2), NO_HOLIDAYS)
    # 30 min left Friday, 90 min on Monday starting 09:30
    assert out == ist(2026, 11, 23, 11, 0)


def test_add_from_non_working_time_starts_at_next_open():
    out = wt.add_working_time(ist(2026, 11, 21, 14, 0), timedelta(hours=1), NO_HOLIDAYS)  # Saturday
    assert out == ist(2026, 11, 23, 10, 30)


def test_add_ending_exactly_at_close_stays_at_close():
    out = wt.add_working_time(ist(2026, 11, 23, 9, 30), timedelta(hours=9), NO_HOLIDAYS)
    assert out == ist(2026, 11, 23, 18, 30)


def test_add_skips_holiday():
    hol = {date(2026, 11, 24)}
    out = wt.add_working_time(ist(2026, 11, 23, 18, 0), timedelta(hours=1), hol)
    assert out == ist(2026, 11, 25, 10, 0)  # 30 min Mon, skip Tue, 30 min Wed


def test_add_zero_returns_start():
    t = ist(2026, 11, 21, 14, 0)
    assert wt.add_working_time(t, timedelta(0), NO_HOLIDAYS) == t


def test_add_and_between_are_inverse():
    start = ist(2026, 11, 19, 15, 17)
    for hours in (0.5, 3, 9, 20, 45, 100):
        end = wt.add_working_time(start, timedelta(hours=hours), NO_HOLIDAYS)
        assert wt.working_time_between(start, end, NO_HOLIDAYS) == timedelta(hours=hours)


def test_next_working_instant():
    assert wt.next_working_instant(ist(2026, 11, 21, 12), NO_HOLIDAYS) == ist(2026, 11, 23, 9, 30)
    assert wt.next_working_instant(ist(2026, 11, 23, 12), NO_HOLIDAYS) == ist(2026, 11, 23, 12)


def test_is_working_time():
    assert wt.is_working_time(ist(2026, 11, 23, 9, 30), NO_HOLIDAYS)
    assert not wt.is_working_time(ist(2026, 11, 23, 18, 30), NO_HOLIDAYS)
    assert not wt.is_working_time(ist(2026, 11, 22, 12), NO_HOLIDAYS)


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        wt.working_time_between(datetime(2026, 11, 23, 10), datetime(2026, 11, 23, 11), NO_HOLIDAYS)
