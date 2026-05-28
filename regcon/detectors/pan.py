from __future__ import annotations

import re
from typing import Iterator

from regcon.models import Finding

# PAN: группы по 4 цифры через пробел/дефис ИЛИ сплошной блок 13–19 цифр (без / и .)
PAN_GROUPED_RE = re.compile(
    r"\b(?:\d{4}[ -]){2,4}\d{1,4}\b|\b\d{13,19}\b"
)
DATE_IN_LINE_RE = re.compile(
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{2}:\d{2}:\d{2}"
)
TIME_TAIL_RE = re.compile(r":\d{2}(?::\d{2})?\s*$")


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


def _valid_calendar(y: int, m: int, d: int) -> bool:
    if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
        return False
    if m in {4, 6, 9, 11} and d > 30:
        return False
    if m == 2 and d > 29:
        return False
    return True


def _looks_like_date_digits(digits: str) -> bool:
    """Цифровая последовательность похожа на дату, а не на PAN."""
    n = len(digits)
    if n == 8:
        y, m, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _valid_calendar(y, m, d):
            return True
        d, m, y = int(digits[0:2]), int(digits[2:4]), int(digits[4:8])
        if _valid_calendar(y, m, d):
            return True
    if n == 14:
        y, m, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _valid_calendar(y, m, d):
            return True
    if n == 16:
        y, m, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
        if _valid_calendar(y, m, d):
            return True
    return False


def _is_year_prefix_16(digits: str) -> bool:
    """Ложный PAN: YYYYMMDD + ещё 8 цифр (часто время 00000000)."""
    if len(digits) != 16:
        return False
    y, m, d = int(digits[0:4]), int(digits[4:6]), int(digits[6:8])
    if not _valid_calendar(y, m, d):
        return False
    tail = digits[8:]
    if tail == "00000000" or tail == "0000000":
        return True
    if tail.endswith("0000"):
        return True
    return False


def _has_date_separators(text: str) -> bool:
    return "/" in text or "." in text


def _all_same_digit(digits: str) -> bool:
    return len(digits) > 0 and len(set(digits)) == 1


def _allowed_chars_only(text: str) -> bool:
    return all(ch.isdigit() or ch in " -" for ch in text)


def _overlaps_date_context(line: str, start: int, end: int) -> bool:
    window_start = max(0, start - 24)
    window_end = min(len(line), end + 12)
    window = line[window_start:window_end]
    for date_match in DATE_IN_LINE_RE.finditer(window):
        abs_start = window_start + date_match.start()
        abs_end = window_start + date_match.end()
        if abs_start < end and abs_end > start:
            return True
        if abs_end == start or abs_start == end:
            return True
    return False


def _time_suffix_false_positive(line: str, start: int, digits: str) -> bool:
    if not digits.endswith("0000"):
        return False
    before = line[max(0, start - 16) : start]
    return bool(TIME_TAIL_RE.search(before) or DATE_IN_LINE_RE.search(before))


def is_plausible_pan(
    matched_text: str,
    digits: str,
    line: str,
    start: int,
    end: int,
) -> bool:
    if len(digits) < 13 or len(digits) > 19:
        return False
    if not _allowed_chars_only(matched_text):
        return False
    if _has_date_separators(matched_text):
        return False
    if _all_same_digit(digits):
        return False
    if _looks_like_date_digits(digits):
        return False
    if _is_year_prefix_16(digits):
        return False
    if _overlaps_date_context(line, start, end):
        return False
    if _time_suffix_false_positive(line, start, digits):
        return False
    return True


class PanDetector:
    def __init__(self, config: dict) -> None:
        pan_cfg = config.get("pan", {})
        self.enabled = pan_cfg.get("enabled", True)
        self.use_luhn = pan_cfg.get("use_luhn", True)
        patterns = [re.compile(p) for p in pan_cfg.get("regex_list", [])]
        if pan_cfg.get("use_grouped_scan", True):
            patterns.append(PAN_GROUPED_RE)
        self._patterns = patterns

    def scan_line(
        self,
        line: str,
        file_path: str,
        line_no: int,
        context_len: int = 40,
    ) -> Iterator[Finding]:
        if not self.enabled:
            return
        digit_count = sum(ch.isdigit() for ch in line)
        if digit_count < 13:
            return
        seen: set[tuple[int, int]] = set()
        for pattern in self._patterns:
            for match in pattern.finditer(line):
                span = (match.start(), match.end())
                if span in seen:
                    continue
                text = match.group(0)
                digits = _digits_only(text)
                if not is_plausible_pan(text, digits, line, span[0], span[1]):
                    continue
                if self.use_luhn and not luhn_valid(digits):
                    continue
                seen.add(span)
                ctx_start = max(0, span[0] - context_len)
                ctx_end = min(len(line), span[1] + context_len)
                yield Finding.create(
                    file_path=file_path,
                    line_no=line_no,
                    column=span[0],
                    match_type="PAN",
                    matched_text=text,
                    context=line[ctx_start:ctx_end].strip(),
                )
