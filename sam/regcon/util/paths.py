from __future__ import annotations

import sys
from pathlib import Path


def normalize_file_path(path: str | Path) -> str:
    """Канонический путь для хранения в Finding (маска/группировка)."""
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(Path(path))


def path_lookup_key(path: str | Path) -> str:
    """Ключ для сопоставления путей (регистр на Windows)."""
    key = normalize_file_path(path)
    if sys.platform == "win32":
        return key.casefold()
    return key
