import sys
from pathlib import Path

import pytest

from regcon.util.pan_prefix_index import PanPrefixIndex
from regcon.util.paths import normalize_file_path, path_lookup_key


def test_path_lookup_windows_case(tmp_path, monkeypatch):
    if sys.platform != "win32":
        pytest.skip("casefold paths")
    a = tmp_path / "File.LOG"
    b = tmp_path / "file.log"
    try:
        b.hardlink_to(a)
    except OSError:
        pytest.skip("hardlink unsupported")
    assert path_lookup_key(a) == path_lookup_key(b)


def test_normalize_file_path(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("x", encoding="utf-8")
    assert normalize_file_path(p).endswith("a.log")


def test_use_luhn_false_accepts_invalid_luhn():
    idx = PanPrefixIndex(["41111111"], use_luhn=False)
    line = "n 4111111111111112 end"
    hits = idx.iter_pan_candidates(line)
    assert len(hits) >= 1
