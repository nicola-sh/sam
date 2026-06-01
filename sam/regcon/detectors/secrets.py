from __future__ import annotations

import re
from typing import Iterator

from sam.regcon.models import Finding


class SecretDetector:
    def __init__(self, config: dict) -> None:
        pwd_cfg = config.get("passwords", {})
        self.enabled = pwd_cfg.get("enabled", True)
        self._patterns = [re.compile(p) for p in pwd_cfg.get("patterns", [])]
        self.context_radius = int(
            config.get("regcon", {}).get("context_radius", 30)
        )

    def scan_line(
        self,
        line: str,
        file_path: str,
        line_no: int,
        context_len: int = 30,
    ) -> Iterator[Finding]:
        del context_len
        if not self.enabled:
            return
        seen: set[tuple[int, int]] = set()
        for pattern in self._patterns:
            for match in pattern.finditer(line):
                if match.lastindex and match.lastindex >= 2:
                    value = match.group(2)
                    start = match.start(2)
                    end = match.end(2)
                else:
                    value = match.group(0)
                    start = match.start()
                    end = match.end()
                span = (start, end)
                if span in seen or not value:
                    continue
                seen.add(span)
                yield Finding.create(
                    file_path=file_path,
                    line_no=line_no,
                    column=start,
                    match_type="PASSWORD",
                    matched_text=value,
                    line=line,
                    match_start=start,
                    match_end=end,
                    context_radius=self.context_radius,
                )
