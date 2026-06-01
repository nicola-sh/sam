from __future__ import annotations

import re
from datetime import datetime, time

from sam.util.time_window import TimeWindow

_BUILTIN = [
    (re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})"), "%Y-%m-%d", "%H:%M:%S"),
    (re.compile(r"(\d{2}\.\d{2}\.\d{4})[ T](\d{2}:\d{2}:\d{2})"), "%d.%m.%Y", "%H:%M:%S"),
    (re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})"), "%Y-%m-%d", "%H:%M"),
]


def _parse_line_ts(line: str) -> datetime | None:
    text = line.strip()
    if not text:
        return None
    for rx, dfmt, tfmt in _BUILTIN:
        m = rx.search(text)
        if m:
            try:
                d = datetime.strptime(m.group(1), dfmt)
                tpart = m.group(2)
                t = (
                    datetime.strptime(tpart, "%H:%M").time()
                    if len(tpart) == 5
                    else datetime.strptime(tpart, "%H:%M:%S").time()
                )
                return datetime.combine(d.date(), t)
            except ValueError:
                continue
    return None


def filter_log_bytes(
    data: bytes,
    window: TimeWindow,
    *,
    encoding: str = "utf-8",
) -> bytes:
    if not data:
        return data
    text = data.decode(encoding, errors="replace")
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        ts = _parse_line_ts(line)
        if ts is None:
            kept.append(line)
            continue
        if window.start <= ts <= window.end:
            kept.append(line)
    return "".join(kept).encode(encoding)


def needs_time_filter(time_from: time, time_to: time) -> bool:
    """Пользователь задал не весь день."""
    return time_from != time(0, 0) or time_to < time(23, 59, 0)
