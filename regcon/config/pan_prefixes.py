from __future__ import annotations

from pathlib import Path


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


def load_prefix_lines(path: Path) -> list[str]:
    """Читает префиксы PAN (по одному на строку, только цифры)."""
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
            if len(digits) < 4:
                continue
            if digits not in seen:
                seen.add(digits)
                prefixes.append(digits)
    prefixes.sort(key=len, reverse=True)
    return prefixes
