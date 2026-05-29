from __future__ import annotations

from pathlib import Path

DEFAULT_PREFIX_LEN = 8


def normalize_prefix(value: str, prefix_len: int = DEFAULT_PREFIX_LEN) -> str | None:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) < prefix_len:
        return None
    return digits[:prefix_len]


def load_prefixes_from_text(
    text: str, prefix_len: int = DEFAULT_PREFIX_LEN
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key = normalize_prefix(line, prefix_len)
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def load_prefixes_from_file(
    path: Path, prefix_len: int = DEFAULT_PREFIX_LEN
) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return load_prefixes_from_text(text, prefix_len)


def load_prefixes(config: dict) -> list[str]:
    """Список префиксов из config.yaml (pan.prefix_list)."""
    pan_cfg = config.get("pan", {})
    prefix_len = int(pan_cfg.get("prefix_digits", DEFAULT_PREFIX_LEN))
    seen: set[str] = set()
    result: list[str] = []
    for item in pan_cfg.get("prefix_list", []):
        key = normalize_prefix(str(item), prefix_len)
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def prefixes_to_text(prefixes: list[str]) -> str:
    return "\n".join(prefixes)
