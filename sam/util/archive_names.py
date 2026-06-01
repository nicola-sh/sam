from __future__ import annotations

import re
from datetime import datetime

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def default_archive_basename(when: datetime | None = None) -> str:
    """Имя без расширения: log_MMDD-HHMM, например log_0601-1053."""
    dt = when or datetime.now()
    return f"log_{dt.strftime('%m%d')}-{dt.strftime('%H%M')}"


def sanitize_archive_basename(name: str) -> str:
    text = (name or "").strip()
    if text.lower().endswith(".zip"):
        text = text[:-4]
    text = _INVALID.sub("_", text)
    return text or default_archive_basename()


def archive_filename(basename: str, when: datetime | None = None) -> str:
    return f"{sanitize_archive_basename(basename or default_archive_basename(when))}.zip"
