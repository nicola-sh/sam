from datetime import date, datetime, time

from sam.services.time_filter import filter_log_bytes, needs_time_filter
from sam.util.time_window import build_time_window


def test_needs_time_filter_full_day_false():
    assert needs_time_filter(time(0, 0), time(23, 59)) is False


def test_needs_time_filter_partial_true():
    assert needs_time_filter(time(10, 0), time(23, 59)) is True


def test_filter_log_bytes_keeps_in_window():
    window = build_time_window(
        date(2026, 6, 1),
        date(2026, 6, 1),
        time(10, 0),
        time(10, 59),
    )
    raw = (
        b"2026-06-01 09:59:00 before\n"
        b"2026-06-01 10:15:00 inside\n"
        b"2026-06-01 11:00:00 after\n"
    )
    out = filter_log_bytes(raw, window).decode()
    assert "before" not in out
    assert "inside" in out
    assert "after" not in out


def test_filter_log_bytes_keeps_unparsed_lines():
    window = build_time_window(
        date(2026, 6, 1),
        date(2026, 6, 1),
        time(10, 0),
        time(11, 0),
    )
    raw = b"no timestamp here\n2026-06-01 10:30:00 ok\n"
    out = filter_log_bytes(raw, window).decode()
    assert "no timestamp here" in out
    assert "ok" in out
