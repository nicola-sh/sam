from __future__ import annotations

import re
from typing import Any

from sam.regcon.models import Finding

# Полные PAN (13–19 цифр подряд, допускаются пробелы/дефисы между группами)
_PAN_LIKE = re.compile(
    r"(?<!\d)(?:\d[ \t\-]?){12,18}\d(?!\d)"
)

_SENSITIVE_DETAIL_KEYS = frozenset(
    {
        "matched_text",
        "context",
        "context_before",
        "context_after",
        "findings",
        "payload",
        "line",
        "replacement",
        "secret",
        "pan",
        "password",
    }
)


def redact_sensitive_text(text: str) -> str:
    """Убрать из строки полные номера карт (для логов и аудита)."""

    def _mask(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 13:
            return match.group(0)
        keep = min(6, len(digits))
        tail = min(4, len(digits) - keep)
        mid = max(len(digits) - keep - tail, 0)
        return digits[:keep] + "*" * mid + digits[-tail:] if tail else digits[:keep] + "*" * mid

    return _PAN_LIKE.sub(_mask, text)


def sanitize_audit_details(details: dict[str, Any]) -> dict[str, Any]:
    """Только безопасные поля аудита — без фрагментов карт и паролей."""
    safe: dict[str, Any] = {}
    for key, value in details.items():
        if key.lower() in _SENSITIVE_DETAIL_KEYS:
            continue
        if isinstance(value, str):
            safe[key] = redact_sensitive_text(value)
        elif isinstance(value, list):
            safe[key] = [
                redact_sensitive_text(v) if isinstance(v, str) else v
                for v in value
                if not isinstance(v, dict)
            ]
        elif isinstance(value, dict):
            continue
        else:
            safe[key] = value
    return safe


def wipe_findings(findings: list[Finding]) -> None:
    """Очистить список находок из памяти процесса (после маски / закрытия)."""
    for item in findings:
        item.matched_text = ""
        item.context = ""
        item.context_before = ""
        item.context_after = ""
        item.file_path = ""
    findings.clear()
