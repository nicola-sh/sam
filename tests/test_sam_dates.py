from datetime import date

import pytest

from sam.util.date_range import iter_dates
from sam.util.dates import formats_for_day, parse_day
from sam.util.output_names import output_file_path


def test_formats_for_day():
    d = date(2026, 5, 28)
    f = formats_for_day(d, today=date(2026, 6, 1))
    assert f.date_dash == "2026-05-28"
    assert f.date_plain == "20260528"
    assert f.date_exit_file == "0528"
    assert f.is_today is False


def test_iter_dates():
    assert len(iter_dates(date(2026, 5, 28), date(2026, 5, 30))) == 3


def test_output_with_grep(tmp_path):
    f = formats_for_day(date(2026, 5, 28), today=date(2026, 6, 1))
    p = output_file_path(tmp_path, "atm-ddc", "M6768022", f, "DDC", grep_value="M6768022")
    assert p.name == "M6768022_0528_DDC.txt"


def test_output_without_grep(tmp_path):
    f = formats_for_day(date(2026, 5, 28), today=date(2026, 6, 1))
    p = output_file_path(tmp_path, "atm-ddc", "all", f, "DDC", grep_value=None)
    assert p.name == "atm-ddc_0528_DDC_full.txt"


def test_parse_day_invalid():
    with pytest.raises(ValueError):
        parse_day("not-a-date")
