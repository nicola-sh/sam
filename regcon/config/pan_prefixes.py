from __future__ import annotations

from pathlib import Path

DEFAULT_PREFIX_LEN = 8


def regcon_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_prefix_path(config: dict) -> Path | None:
    pan_cfg = config.get("pan", {})
    rel = pan_cfg.get("prefix_file")
    if not rel:
        return None
    path = Path(rel)
    if not path.is_absolute():
        path = regcon_root() / path
    return path


def load_prefix_lines(path: Path, prefix_len: int = DEFAULT_PREFIX_LEN) -> list[str]:
    """
  Загружает первые N цифр PAN из txt (по одной записи на строку).
  Строка должна содержать не меньше prefix_len цифр (обычно ровно 8).
    """
    if not path.is_file():
        return []
    prefixes: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as handle:
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
