from __future__ import annotations

import re
from typing import Iterator

from regcon.models import Finding

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


def _has_date_separators(text: str) -> bool:
    return "/" in text or "." in text


def _all_same_digit(digits: str) -> bool:
    return len(digits) > 0 and len(set(digits)) == 1


def _allowed_pan_chars_only(text: str) -> bool:
    """В совпадении PAN — только цифры, пробел и дефис."""
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
    digits: str,
    line: str,
    start: int,
    end: int,
) -> bool:
    if len(digits) < 13 or len(digits) > 19:
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


def _format_pan_display(digits: str) -> str:
    """Только цифры, без букв (группы по 4 для читаемости)."""
    if len(digits) == 16:
        return f"{digits[0:4]} {digits[4:8]} {digits[8:12]} {digits[12:16]}"
    return digits


def _iter_pan_from_digit_runs(line: str) -> Iterator[tuple[int, int, str]]:
    """
    Ищет PAN по цифрам в строке (буквы между цифрами игнорируются).
    В совпадении — только цифры.
    """
    indices = [i for i, ch in enumerate(line) if ch.isdigit()]
    if len(indices) < 13:
        return
    digits_joined = "".join(line[i] for i in indices)
    seen_digits: set[str] = set()
    for length in range(19, 12, -1):
        if length > len(digits_joined):
            continue
        for offset in range(len(digits_joined) - length + 1):
            chunk = digits_joined[offset : offset + length]
            if chunk in seen_digits:
                continue
            if not luhn_valid(chunk):
                continue
            pos_start = indices[offset]
            pos_end = indices[offset + length - 1] + 1
            if not is_plausible_pan(chunk, line, pos_start, pos_end):
                continue
            seen_digits.add(chunk)
            yield pos_start, pos_end, chunk


def _iter_pan_from_line_spans(line: str) -> Iterator[tuple[int, int, str]]:
    """Фрагменты строки, где только цифры/пробел/дефис."""
    i = 0
    n = len(line)
    while i < n:
        if not line[i].isdigit():
            i += 1
            continue
        j = i
        digit_count = 0
        while j < n:
            ch = line[j]
            if ch.isdigit():
                digit_count += 1
                j += 1
            elif ch in " -" and digit_count > 0:
                j += 1
            else:
                break
        if 13 <= digit_count <= 19:
            span = line[i:j]
            if _allowed_pan_chars_only(span):
                digits = _digits_only(span)
                if luhn_valid(digits) and is_plausible_pan(digits, line, i, j):
                    yield i, j, digits
        i = max(i + 1, j)


class PanDetector:
    def __init__(self, config: dict) -> None:
        pan_cfg = config.get("pan", {})
        self.enabled = pan_cfg.get("enabled", True)
        self.use_luhn = pan_cfg.get("use_luhn", True)
        self.context_radius = int(pan_cfg.get("context_radius", 30))
        self._patterns = [re.compile(p) for p in pan_cfg.get("regex_list", [])]
        if pan_cfg.get("use_grouped_scan", True):
            self._patterns.append(PAN_GROUPED_RE)
        self._scan_embedded = pan_cfg.get("scan_embedded_digits", True)

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
        if sum(ch.isdigit() for ch in line) < 13:
            return
        seen: set[tuple[int, int]] = set()

        def emit(start: int, end: int, digits: str) -> Iterator[Finding]:
            span = (start, end)
            if span in seen:
                return
            if self.use_luhn and not luhn_valid(digits):
                return
            seen.add(span)
            display = _format_pan_display(digits)
            yield Finding.create(
                file_path=file_path,
                line_no=line_no,
                column=start,
                match_type="PAN",
                matched_text=display,
                line=line,
                match_start=start,
                match_end=end,
                context_radius=self.context_radius,
            )

        for pattern in self._patterns:
            for match in pattern.finditer(line):
                text = match.group(0)
                if not _allowed_pan_chars_only(text):
                    continue
                digits = _digits_only(text)
                if len(digits) < 13:
                    continue
                yield from emit(match.start(), match.end(), digits)

        for start, end, digits in _iter_pan_from_line_spans(line):
            yield from emit(start, end, digits)

        if self._scan_embedded:
            for start, end, digits in _iter_pan_from_digit_runs(line):
                yield from emit(start, end, digits)
