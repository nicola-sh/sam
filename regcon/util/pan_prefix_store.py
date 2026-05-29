from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

import yaml

from regcon.util.pan_prefix_text import (
    DEFAULT_PREFIX_LEN,
    load_prefixes_from_text,
    prefixes_to_text,
)
from regcon.util.app_paths import pan_prefix_path

_MAGIC = b"RCENC1"
_KEY_MATERIAL = b"RegCon.PAN.Prefix.Store.v2"


def _fernet():
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(hashlib.sha256(_KEY_MATERIAL).digest())
    return Fernet(key)


def _encrypt(plain: bytes) -> bytes:
    return _MAGIC + _fernet().encrypt(plain)


def _decrypt(data: bytes) -> bytes:
    if data.startswith(_MAGIC):
        return _fernet().decrypt(data[len(_MAGIC) :])
    return data


def save_prefixes(prefixes: list[str], prefix_len: int = DEFAULT_PREFIX_LEN) -> Path:
    path = pan_prefix_path()
    doc: dict[str, Any] = {
        "prefix_digits": prefix_len,
        "prefix_list": prefixes,
    }
    plain = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False).encode("utf-8")
    path.write_bytes(_encrypt(plain))
    return path


def load_prefixes(prefix_len: int = DEFAULT_PREFIX_LEN) -> list[str]:
    path = pan_prefix_path()
    if not path.is_file():
        return _migrate_from_legacy_plaintext(path, prefix_len)
    raw = path.read_bytes()
    if not raw.startswith(_MAGIC):
        return _migrate_from_legacy_plaintext(path, prefix_len)
    try:
        plain = _decrypt(raw)
        doc = yaml.safe_load(plain.decode("utf-8")) or {}
        if isinstance(doc, list):
            raw_list = doc
        else:
            raw_list = doc.get("prefix_list", [])
        return _normalize_list(raw_list, prefix_len)
    except Exception:
        if raw.startswith(_MAGIC):
            return []
        return _migrate_from_legacy_plaintext(path, prefix_len)


def load_prefixes_as_text() -> str:
    items = load_prefixes()
    return prefixes_to_text(items)


def save_prefixes_from_text(text: str, prefix_len: int = DEFAULT_PREFIX_LEN) -> int:
    items = load_prefixes_from_text(text, prefix_len)
    save_prefixes(items, prefix_len)
    return len(items)


def _normalize_list(raw_list: Any, prefix_len: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    if not isinstance(raw_list, list):
        return result
    for item in raw_list:
        digits = "".join(ch for ch in str(item) if ch.isdigit())
        if len(digits) < prefix_len:
            continue
        key = digits[:prefix_len]
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _migrate_from_legacy_plaintext(path: Path, prefix_len: int) -> list[str]:
    """Старый открытый yaml/txt или pan.prefix_list в config.yaml."""
    if path.is_file():
        try:
            raw = path.read_bytes()
            if not raw.startswith(_MAGIC):
                doc = yaml.safe_load(raw.decode("utf-8", errors="replace")) or {}
                if isinstance(doc, list):
                    items = _normalize_list(doc, prefix_len)
                else:
                    items = _normalize_list(doc.get("prefix_list", []), prefix_len)
                if items:
                    save_prefixes(items, prefix_len)
                    return items
        except Exception:
            pass
    from regcon.config.settings import default_config_path, load_config

    cfg = load_config(default_config_path())
    items = _normalize_list(cfg.get("pan", {}).get("prefix_list", []), prefix_len)
    if items:
        save_prefixes(items, prefix_len)
    return items
