from datetime import datetime
from pathlib import Path

import pytest

from sam.util.archive_names import (
    archive_filename,
    default_archive_basename,
    sanitize_archive_basename,
)


def test_default_archive_basename():
    assert default_archive_basename(datetime(2026, 6, 1, 10, 53)) == "log_0601-1053"


def test_sanitize_strips_zip():
    assert sanitize_archive_basename("log_0601-1053.zip") == "log_0601-1053"


def test_archive_filename():
    assert archive_filename("log_0601-1053") == "log_0601-1053.zip"


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("pyzipper"),
    reason="pyzipper not installed",
)
def test_create_password_zip(tmp_path: Path):
    from sam.services.zip_archive import create_password_zip

    f1 = tmp_path / "a.txt"
    f1.write_text("line1\n", encoding="utf-8")
    out = tmp_path / "log_0601-1053.zip"
    create_password_zip([f1], output_path=out, password="secret")
    assert out.is_file()
    with __import__("pyzipper").AESZipFile(out) as zf:
        zf.setpassword(b"secret")
        assert zf.namelist() == ["a.txt"]
