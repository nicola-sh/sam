from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_PREFIX_LEN = 8


def regcon_root() -> Path:
    """Корень пакета regcon (учёт запуска из exe / PyInstaller)."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        meipass = Path(getattr(sys, "_MEIPASS", exe_dir))
        for base in (exe_dir, meipass, meipass / "regcon"):
            candidate = base if (base / "config").is_dir() else base / "regcon"
            if (candidate / "config").is_dir():
                return candidate
        return exe_dir
    return Path(__file__).resolve().parent.parent


def resolve_prefix_path(config: dict) -> Path | None:
    pan_cfg = config.get("pan", {})
    rel = pan_cfg.get("prefix_file")
    if not rel:
        return None
    path = Path(rel)
    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        root = regcon_root()
        candidates.append(root / path)
        candidates.append(root / "config" / path.name)
        candidates.append(Path.cwd() / path)
        candidates.append(Path.cwd() / "config" / path.name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[0].resolve() if candidates else None


def load_prefix_lines(path: Path, prefix_len: int = DEFAULT_PREFIX_LEN) -> list[str]:
    """
    Загружает первые N цифр PAN из txt (по одной записи на строку).
    """
    if not path.is_file():
        return []
    prefixes: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            digits = "".join(ch for ch in line if ch.isdigit())
            if len(digits) < prefix_len:
                continue
            key = digits[:prefix_len]
            if key not in seen:
                seen.add(key)
                prefixes.append(key)
    return prefixes
