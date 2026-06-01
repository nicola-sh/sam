from datetime import date, datetime, time

from sam.util.time_window import TimeWindow, build_time_window


def test_build_time_window_same_day():
    w = build_time_window(
        date(2026, 6, 1),
        date(2026, 6, 1),
        time(10, 0),
        time(12, 30),
    )
    assert w.start == w.start.replace(hour=10, minute=0)
    assert w.end == w.end.replace(hour=12, minute=30)


def test_build_time_window_overnight():
    w = build_time_window(
        date(2026, 6, 1),
        date(2026, 6, 1),
        time(22, 0),
        time(6, 0),
    )
    assert w.end.date() == date(2026, 6, 2)
    assert w.end.hour == 6


def test_slice_for_day_partial():
    w = build_time_window(
        date(2026, 6, 1),
        date(2026, 6, 2),
        time(18, 0),
        time(9, 0),
    )
    day1 = w.slice_for_day(date(2026, 6, 1))
    assert day1 is not None
    assert day1.start.hour == 18
    day2 = w.slice_for_day(date(2026, 6, 2))
    assert day2 is not None
    assert day2.end.hour == 9


def test_window_swaps_if_inverted():
    w = TimeWindow(
        start=datetime(2026, 6, 1, 15, 0),
        end=datetime(2026, 6, 1, 10, 0),
    )
    assert w.start <= w.end
    assert w.start.hour == 10
    assert w.end.hour == 15
