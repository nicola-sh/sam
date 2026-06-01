from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class TimeWindow:
    """Интервал «с даты+времени по дату+время» для фильтра строк лога."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            start, end = self.end, self.start
            object.__setattr__(self, "start", start)
            object.__setattr__(self, "end", end)

    def slice_for_day(self, day: date) -> TimeWindow | None:
        """Пересечение окна с календарным днём (или None)."""
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day, time.max)
        start = max(self.start, day_start)
        end = min(self.end, day_end)
        if start > end:
            return None
        return TimeWindow(start=start, end=end)

    @property
    def spans_multiple_days(self) -> bool:
        return self.start.date() != self.end.date()


def build_time_window(
    date_from: date,
    date_to: date,
    time_from: time,
    time_to: time,
) -> TimeWindow:
    start = datetime.combine(date_from, time_from)
    end = datetime.combine(date_to, time_to)
    if end < start:
        end += timedelta(days=1)
    return TimeWindow(start=start, end=end)
