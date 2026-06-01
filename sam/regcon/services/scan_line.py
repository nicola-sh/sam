from __future__ import annotations

import re
from typing import Iterator

from sam.regcon.detectors import IpDetector, PanDetector, SecretDetector
from sam.regcon.models import Finding
_PWD_HINT_RE = re.compile(
    r"password|passwd|pwd|secret|token",
    re.IGNORECASE,
)


def scan_line_with_detectors(
    line: str,
    file_path: str,
    line_no: int,
    pan: PanDetector | None,
    ip: IpDetector | None,
    secrets: SecretDetector | None,
) -> Iterator[Finding]:
    if pan is not None and pan.enabled:
        yield from pan.scan_line(line, file_path, line_no)

    if ip is not None and ip.enabled:
        if "." in line or ":" in line:
            yield from ip.scan_line(line, file_path, line_no)

    if secrets is not None and secrets.enabled:
        if _PWD_HINT_RE.search(line):
            yield from secrets.scan_line(line, file_path, line_no)
