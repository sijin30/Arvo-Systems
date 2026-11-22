"""The one place the application asks "what time is it?".

Tests (and the demo-data seeder) can replace the source with `use_clock`.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator

_source: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def now() -> datetime:
    value = _source()
    if value.tzinfo is None:
        raise ValueError("clock source must return timezone-aware datetimes")
    return value.astimezone(timezone.utc)


@contextmanager
def use_clock(source: Callable[[], datetime]) -> Iterator[None]:
    global _source
    previous = _source
    _source = source
    try:
        yield
    finally:
        _source = previous
