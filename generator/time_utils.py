"""Date/time helpers for synthetic generation."""

from __future__ import annotations

from datetime import date, datetime, timedelta


SIMULATION_START = date(2023, 1, 1)
SIMULATION_DAYS = 365 * 3
ACTIVE_THRESHOLD_DAYS = 90


def simulation_end() -> date:
    return SIMULATION_START + timedelta(days=SIMULATION_DAYS - 1)


def to_iso(d: date | datetime) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%M:%S")
    return d.isoformat()


def from_iso(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.fromisoformat(value + "T12:00:00")


def growth_curve_join_date(day_index: float, rng) -> date:
    """Slow start, acceleration, plateau over simulation window."""
    t = max(0.0, min(1.0, day_index))
    curved = t**1.8
    offset = int(curved * (SIMULATION_DAYS - 1))
    return SIMULATION_START + timedelta(days=offset)


def random_date_after(start: date, end: date, rng) -> date:
    if start >= end:
        return start
    delta = (end - start).days
    return start + timedelta(days=int(rng.integers(0, delta + 1)))


def random_datetime_after(start: date, end: date, rng) -> datetime:
    d = random_date_after(start, end, rng)
    hour = int(rng.integers(8, 23))
    minute = int(rng.integers(0, 60))
    return datetime(d.year, d.month, d.day, hour, minute, 0)
