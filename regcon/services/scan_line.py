from __future__ import annotations

from typing import Iterator

from regcon.detectors import IpDetector, PanDetector, SecretDetector
from regcon.models import Finding

_PWD_HINTS = ("password", "passwd", "pwd", "secret", "token")


def scan_line_with_detectors(
    line: str,
    file_path: str,
    line_no: int,
    pan: PanDetector | None,
    ip: IpDetector | None,
    secrets: SecretDetector | None,
) -> Iterator[Finding]:
    if pan is not None and pan.enabled:
        if sum(ch.isdigit() for ch in line) >= 13:
            yield from pan.scan_line(line, file_path, line_no)
    if ip is not None and ip.enabled:
        if "." in line or ":" in line:
            yield from ip.scan_line(line, file_path, line_no)
    if secrets is not None and secrets.enabled:
        lower = line.lower()
        if any(hint in lower for hint in _PWD_HINTS):
            yield from secrets.scan_line(line, file_path, line_no)
