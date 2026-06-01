from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class AtmLogDateFormats:
    """Форматы даты, как в atm-ddc-logs.sh."""

    date_dash: str
    date_plain: str
    date_exit_file: str
    is_today: bool


def formats_for_day(day: date, *, today: date | None = None) -> AtmLogDateFormats:
    ref = today or date.today()
    return AtmLogDateFormats(
        date_dash=day.strftime("%Y-%m-%d"),
        date_plain=day.strftime("%Y%m%d"),
        date_exit_file=day.strftime("%m%d"),
        is_today=day == ref,
    )


def parse_day(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Не удалось разобрать дату: {value!r}")
