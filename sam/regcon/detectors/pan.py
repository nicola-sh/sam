from __future__ import annotations

import re
from typing import Iterator

from sam.regcon.config.pan_prefixes import DEFAULT_PREFIX_LEN
from sam.regcon.util.pan_prefix_store import load_prefixes as load_stored_prefixes
from sam.regcon.util.pan_luhn import luhn_valid_digits
from sam.regcon.models import Finding
from sam.regcon.util.pan_prefix_index import PanPrefixIndex

DATE_IN_LINE_RE = re.compile(
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{2}:\d{2}:\d{2}"
)
TIME_TAIL_RE = re.compile(r":\d{2}(?::\d{2})?\s*$")


def luhn_valid(number: str) -> bool:
    digits = "".join(ch for ch in number if ch.isdigit())
    return luhn_valid_digits(digits) if len(digits) >= 13 else False


def _valid_calendar(y: int, m: int, d: int) -> bool:
    if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
        return False
    if m in {4, 6, 9, 11} and d > 30:
        return False
    if m == 2 and d > 29:
        return False
    return True


def _looks_like_date_digits(digits: str) -> bool:
    n = len(digits)
    if n == 8:
        y, m, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _valid_calendar(y, m, d):
            return True
        d, m, y = int(digits[0:2]), int(digits[2:4]), int(digits[4:8])
        if _valid_calendar(y, m, d):
            return True
    if n in {14, 16}:
        y, m, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _valid_calendar(y, m, d):
            return True
    return False


def _is_year_prefix_16(digits: str) -> bool:
    if len(digits) != 16:
        return False
    y, m, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
    if not _valid_calendar(y, m, d):
        return False
    tail = digits[8:]
    return tail in {"00000000", "0000000"} or tail.endswith("0000")


def _all_same_digit(digits: str) -> bool:
    return len(digits) > 0 and len(set(digits)) == 1


def _overlaps_date_spans(
    start: int, end: int, date_spans: list[tuple[int, int]]
) -> bool:
    for abs_start, abs_end in date_spans:
        if abs_start < end and abs_end > start:
            return True
    return False


def _time_suffix_false_positive(line: str, start: int, digits: str) -> bool:
    if not digits.endswith("0000"):
        return False
    before = line[max(0, start - 16) : start]
    return bool(TIME_TAIL_RE.search(before) or DATE_IN_LINE_RE.search(before))


def is_plausible_pan(
    digits: str,
    line: str,
    start: int,
    end: int,
    *,
    date_spans: list[tuple[int, int]] | None = None,
) -> bool:
    if len(digits) < 13 or len(digits) > 19:
        return False
    if _all_same_digit(digits):
        return False
    if _looks_like_date_digits(digits):
        return False
    if _is_year_prefix_16(digits):
        return False
    if date_spans and _overlaps_date_spans(start, end, date_spans):
        return False
    if _time_suffix_false_positive(line, start, digits):
        return False
    return True


def _format_pan_display(digits: str) -> str:
    if len(digits) == 16:
        return f"{digits[0:4]} {digits[4:8]} {digits[8:12]} {digits[12:16]}"
    return digits


class PanDetector:
    """Поиск PAN по справочнику первых 8 цифр (pan_prefix.yaml) + Luhn."""

    def __init__(self, config: dict) -> None:
        pan_cfg = config.get("pan", {})
        self.enabled = pan_cfg.get("enabled", True)
        self.use_luhn = pan_cfg.get("use_luhn", True)
        self.context_radius = int(pan_cfg.get("context_radius", 30))
        self._prefix_len = int(pan_cfg.get("prefix_digits", DEFAULT_PREFIX_LEN))
        self._prefix_index = PanPrefixIndex(
            load_stored_prefixes(self._prefix_len),
            self._prefix_len,
            use_luhn=self.use_luhn,
        )
        self._prefix_line_filter = bool(pan_cfg.get("prefix_line_filter", True))

    @property
    def prefix_count(self) -> int:
        return self._prefix_index.count

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
        if not self._prefix_index.enabled:
            return
        if self._prefix_line_filter and not self._prefix_index.line_may_contain(line):
            return

        date_spans: list[tuple[int, int]] | None = None
        if "/" in line or "-" in line or "." in line or ":" in line:
            date_spans = [
                (m.start(), m.end()) for m in DATE_IN_LINE_RE.finditer(line)
            ]

        for start, end, digits in self._prefix_index.iter_pan_candidates(line):
            if not is_plausible_pan(
                digits, line, start, end, date_spans=date_spans
            ):
                continue
            yield Finding.create(
                file_path=file_path,
                line_no=line_no,
                column=start,
                match_type="PAN",
                matched_text=_format_pan_display(digits),
                line=line,
                match_start=start,
                match_end=end,
                context_radius=self.context_radius,
            )
