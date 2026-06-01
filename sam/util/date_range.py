from __future__ import annotations

from datetime import date, timedelta


def iter_dates(start: date, end: date) -> list[date]:
    if end < start:
        start, end = end, start
    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days
