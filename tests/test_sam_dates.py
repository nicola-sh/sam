from datetime import date

import pytest

from sam.util.dates import formats_for_day, parse_day
from sam.util.output_names import output_file_path


def test_formats_for_day():
    d = date(2026, 5, 28)
    f = formats_for_day(d, today=date(2026, 6, 1))
    assert f.date_dash == "2026-05-28"
    assert f.date_plain == "20260528"
    assert f.date_exit_file == "0528"
    assert f.is_today is False


def test_formats_today():
    d = date(2026, 6, 1)
    f = formats_for_day(d, today=d)
    assert f.is_today is True


def test_parse_day_variants():
    assert parse_day("2026-05-28") == date(2026, 5, 28)
    assert parse_day("28.05.2026") == date(2026, 5, 28)


def test_output_file_path(tmp_path):
    d = date(2026, 5, 28)
    f = formats_for_day(d, today=date(2026, 6, 1))
    p = output_file_path(tmp_path, "m6768022", f, "DDC")
    assert p.name == "M6768022_0528_DDC.txt"
    assert p.parent.name == "M6768022"


def test_parse_day_invalid():
    with pytest.raises(ValueError):
        parse_day("not-a-date")
