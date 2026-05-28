from __future__ import annotations

import ipaddress
import re
from typing import Iterator

from regcon.models import Finding

IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)(?:\.|$)){4}\b"
)
IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\b")


class IpDetector:
    def __init__(self, config: dict) -> None:
        ip_cfg = config.get("ip", {})
        self.enabled = ip_cfg.get("enabled", True)
        self.whitelist = {item.strip() for item in ip_cfg.get("whitelist", [])}

    def _allowed(self, ip_text: str) -> bool:
        if ip_text in self.whitelist:
            return False
        try:
            ip = ipaddress.ip_address(ip_text)
            if ip.is_loopback:
                return False
        except ValueError:
            return False
        return True

    def scan_line(
        self,
        line: str,
        file_path: str,
        line_no: int,
        context_len: int = 40,
    ) -> Iterator[Finding]:
        if not self.enabled:
            return
        seen: set[tuple[int, int]] = set()
        for pattern in (IPV4_RE, IPV6_RE):
            for match in pattern.finditer(line):
                span = (match.start(), match.end())
                if span in seen:
                    continue
                text = match.group(0).rstrip(".")
                if not self._allowed(text):
                    continue
                seen.add(span)
                start = max(0, match.start() - context_len)
                end = min(len(line), match.end() + context_len)
                yield Finding.create(
                    file_path=file_path,
                    line_no=line_no,
                    column=match.start(),
                    match_type="IP",
                    matched_text=text,
                    context=line[start:end].strip(),
                )
