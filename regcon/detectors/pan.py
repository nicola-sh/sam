from __future__ import annotations

import re
from typing import Iterator

from regcon.models import Finding


def luhn_valid(number: str) -> bool:
    digits = [int(ch) for ch in number if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        if i % 2 == parity:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


def _digits_only(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


class PanDetector:
    def __init__(self, config: dict) -> None:
        pan_cfg = config.get("pan", {})
        self.enabled = pan_cfg.get("enabled", True)
        self.use_luhn = pan_cfg.get("use_luhn", True)
        self.generic = pan_cfg.get("generic_16_digit", True)
        patterns = list(pan_cfg.get("regex_list", []))
        if self.generic and r"\b(?:\d[ -]*?){13,19}\b" not in patterns:
            patterns.append(r"\b(?:\d[ -]*?){13,19}\b")
        self._patterns = [re.compile(p) for p in patterns]

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
        for pattern in self._patterns:
            for match in pattern.finditer(line):
                span = (match.start(), match.end())
                if span in seen:
                    continue
                text = match.group(0)
                digits = _digits_only(text)
                if len(digits) < 13:
                    continue
                if self.use_luhn and not luhn_valid(digits):
                    continue
                seen.add(span)
                start = max(0, match.start() - context_len)
                end = min(len(line), match.end() + context_len)
                yield Finding.create(
                    file_path=file_path,
                    line_no=line_no,
                    column=match.start(),
                    match_type="PAN",
                    matched_text=text,
                    context=line[start:end].strip(),
                )
