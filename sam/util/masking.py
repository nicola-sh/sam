from __future__ import annotations

import re

_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d?\d)){3})\b"
)


def mask_ipv4(host: str) -> str:
    text = (host or "").strip()
    if not text:
        return "—"
    parts = text.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.***.***"
    return "***"


def mask_hosts_in_text(text: str) -> str:
    return _IPV4.sub(lambda m: mask_ipv4(m.group(0)), text)
