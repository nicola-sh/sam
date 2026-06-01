from pathlib import Path

import pytest

from sam.regcon.util import pan_prefix_store as store


@pytest.fixture
def prefix_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pan_prefix.yaml"
    monkeypatch.setattr(store, "pan_prefix_path", lambda: path)
    return path


def test_encrypt_roundtrip(prefix_file: Path) -> None:
    store.save_prefixes(["41111111", "55000000"])
    raw = prefix_file.read_bytes()
    assert raw.startswith(b"RCENC1")
    loaded = store.load_prefixes()
    assert loaded == ["41111111", "55000000"]


def test_migrate_plain_yaml(prefix_file: Path) -> None:
    prefix_file.write_text(
        "prefix_list:\n  - '91123912'\n  - '41111111'\n",
        encoding="utf-8",
    )
    loaded = store.load_prefixes()
    assert "91123912" in loaded
    assert prefix_file.read_bytes().startswith(b"RCENC1")
