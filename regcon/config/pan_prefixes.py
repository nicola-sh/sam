from __future__ import annotations

from regcon.util.pan_prefix_store import load_prefixes as load_stored_prefixes
from regcon.util.pan_prefix_store import save_prefixes as save_stored_prefixes
from regcon.util.pan_prefix_text import (
    DEFAULT_PREFIX_LEN,
    load_prefixes_from_file,
    load_prefixes_from_text,
    normalize_prefix,
    prefixes_to_text,
)

__all__ = [
    "DEFAULT_PREFIX_LEN",
    "load_prefixes",
    "load_prefixes_from_file",
    "load_prefixes_from_text",
    "normalize_prefix",
    "prefixes_to_text",
    "save_prefixes",
]


def load_prefixes(config: dict) -> list[str]:
    """Список префиксов из зашифрованного pan_prefix.yaml рядом с exe."""
    del config
    return load_stored_prefixes()


def save_prefixes(config: dict, prefixes: list[str]) -> None:
    prefix_len = int(config.get("pan", {}).get("prefix_digits", DEFAULT_PREFIX_LEN))
    save_stored_prefixes(prefixes, prefix_len)
    config.setdefault("pan", {})["prefix_list"] = prefixes
