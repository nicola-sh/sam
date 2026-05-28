from __future__ import annotations

import re
from typing import Iterator

from regcon.detectors.pan_bulk import iter_bulk_digit_runs, skip_obvious_non_pan_line
from regcon.detectors.pan_luhn import luhn_valid_digits
from regcon.models import Finding
from regcon.config.pan_prefixes import resolve_prefix_path
from regcon.util.digit_scan import PanLineFlags, precheck_pan_line
from regcon.util.pan_prefix_index import PanPrefixIndex, build_prefix_index

PAN_GROUPED_RE = re.compile(
    r"\b(?:\d{4}[ -]){2,4}\d{1,4}\b|\b\d{13,19}\b"
)
DATE_IN_LINE_RE = re.compile(
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{2}:\d{2}:\d{2}"
)
TIME_TAIL_RE = re.compile(r":\d{2}(?::\d{2})?\s*$")
_PAN_LENGTHS = (19, 18, 17, 16, 15, 14, 13)


def luhn_valid(number: str) -> bool:
    digits = "".join(ch for ch in number if ch.isdigit())
    return luhn_valid_digits(digits) if len(digits) >= 13 else False


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


def _all_same_digit(digits: str) -> bool:
    return len(digits) > 0 and len(set(digits)) == 1


def _allowed_pan_chars_only(text: str) -> bool:
    return all(ch.isdigit() or ch in " -" for ch in text)


def _overlaps_date_spans(
    start: int, end: int, date_spans: list[tuple[int, int]]
) -> bool:
    for abs_start, abs_end in date_spans:
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
    *,
    date_spans: list[tuple[int, int]] | None = None,
    check_dates: bool = True,
) -> bool:
    if len(digits) < 13 or len(digits) > 19:
        return False
    if _all_same_digit(digits):
        return False
    if _looks_like_date_digits(digits):
        return False
    if _is_year_prefix_16(digits):
        return False
    if check_dates and date_spans is not None:
        if _overlaps_date_spans(start, end, date_spans):
            return False
    if _time_suffix_false_positive(line, start, digits):
        return False
    return True


def _format_pan_display(digits: str) -> str:
    if len(digits) == 16:
        return f"{digits[0:4]} {digits[4:8]} {digits[8:12]} {digits[12:16]}"
    return digits


def _parse_bin_hints(regex_list: list[str], configured: list[str]) -> tuple[str, ...]:
    hints: list[str] = list(configured)
    for pattern in regex_list:
        for match in re.finditer(r"(?<!\\)\d{4,}", pattern):
            hints.append(match.group(0))
    return tuple(dict.fromkeys(h for h in hints if h))


def _group_digit_segments(
    indices: list[int], max_gap: int
) -> list[list[int]]:
    if len(indices) < 13:
        return []
    segments: list[list[int]] = []
    seg = [indices[0]]
    for k in range(1, len(indices)):
        if indices[k] - indices[k - 1] <= max_gap:
            seg.append(indices[k])
        else:
            if len(seg) >= 13:
                segments.append(seg)
            seg = [indices[k]]
    if len(seg) >= 13:
        segments.append(seg)
    return segments


def _scan_digit_segment(
    line: str,
    indices: list[int],
    date_spans: list[tuple[int, int]] | None,
    seen_digits: set[str],
    check_dates: bool,
    prefix_index: PanPrefixIndex | None = None,
) -> Iterator[tuple[int, int, str]]:
    digits_joined = "".join(line[i] for i in indices)
    dlen = len(digits_joined)
    if dlen < 13:
        return
    for length in _PAN_LENGTHS:
        if length > dlen:
            continue
        for offset in range(dlen - length + 1):
            chunk = digits_joined[offset : offset + length]
            if chunk in seen_digits:
                continue
            if prefix_index is not None and not prefix_index.digits_allowed(chunk):
                continue
            if not luhn_valid_digits(chunk):
                continue
            pos_start = indices[offset]
            pos_end = indices[offset + length - 1] + 1
            if not is_plausible_pan(
                chunk,
                line,
                pos_start,
                pos_end,
                date_spans=date_spans,
                check_dates=check_dates,
            ):
                continue
            seen_digits.add(chunk)
            yield pos_start, pos_end, chunk


def _iter_pan_from_digit_runs(
    line: str,
    max_gap: int,
    date_spans: list[tuple[int, int]] | None,
    check_dates: bool,
    prefix_index: PanPrefixIndex | None = None,
) -> Iterator[tuple[int, int, str]]:
    indices = [i for i, ch in enumerate(line) if ch.isdigit()]
    if len(indices) < 13:
        return
    seen_digits: set[str] = set()
    for segment in _group_digit_segments(indices, max_gap):
        yield from _scan_digit_segment(
            line, segment, date_spans, seen_digits, check_dates, prefix_index
        )


def _iter_pan_from_line_spans(
    line: str,
    date_spans: list[tuple[int, int]] | None,
    check_dates: bool,
    prefix_index: PanPrefixIndex | None = None,
) -> Iterator[tuple[int, int, str]]:
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
                if prefix_index is not None and not prefix_index.digits_allowed(digits):
                    continue
                if luhn_valid_digits(digits) and is_plausible_pan(
                    digits,
                    line,
                    i,
                    j,
                    date_spans=date_spans,
                    check_dates=check_dates,
                ):
                    yield i, j, digits
        i = j if j > i else i + 1


class PanDetector:
    """
    Профили:
    - bulk: regex + сплошные 13–19 цифр; без O(n²) embedded (10M+ строк)
    - normal: regex + spans + embedded auto
    - thorough: всё включено
    - auto: bulk если файл >= auto_bulk_file_mb
    """

    def __init__(self, config: dict) -> None:
        pan_cfg = config.get("pan", {})
        self.enabled = pan_cfg.get("enabled", True)
        self.use_luhn = pan_cfg.get("use_luhn", True)
        self.context_radius = int(pan_cfg.get("context_radius", 30))
        regex_list = list(pan_cfg.get("regex_list", []))
        self._patterns = [re.compile(p) for p in regex_list]
        if pan_cfg.get("use_grouped_scan", True):
            self._patterns.append(PAN_GROUPED_RE)
        embedded = pan_cfg.get("scan_embedded_digits", "auto")
        if embedded is True:
            self._embedded_mode = "always"
        elif embedded is False:
            self._embedded_mode = "never"
        else:
            self._embedded_mode = "auto"
        self._embedded_max_gap = int(pan_cfg.get("embedded_max_digit_gap", 4))
        self._deep_scan_max_digits = int(pan_cfg.get("deep_scan_max_digits", 96))
        self._profile_setting = str(pan_cfg.get("scan_profile", "auto")).lower()
        self._auto_bulk_bytes = int(pan_cfg.get("auto_bulk_file_mb", 20)) * 1024 * 1024
        self._bulk_digit_run = bool(pan_cfg.get("bulk_digit_run", True))
        extra_hints = tuple(
            _parse_bin_hints(regex_list, list(pan_cfg.get("bin_line_hints", [])))
        )
        prefix_path = resolve_prefix_path(config)
        self._prefix_index = build_prefix_index(prefix_path, extra_hints)
        self._prefix_line_filter = bool(
            pan_cfg.get("prefix_line_filter", True)
        ) and self._prefix_index.enabled
        self._prefix_require_match = bool(
            pan_cfg.get("prefix_require_match", True)
        ) and self._prefix_index.enabled
        # Устаревшее имя опции — то же, что prefix_line_filter
        if pan_cfg.get("bin_line_filter") is False:
            self._prefix_line_filter = False
        self._active_profile = "normal"
        workers = pan_cfg.get("parallel_workers", "auto")
        if workers == "auto":
            import os

            cpu = os.cpu_count() or 2
            workers = min(8, max(2, cpu - 1))
        self._parallel_workers = int(workers)
        self._parallel_chunk = int(pan_cfg.get("parallel_chunk_lines", 250_000))
        self._parallel_min_bytes = int(
            pan_cfg.get("parallel_min_file_mb", 50)
        ) * 1024 * 1024

    def begin_file(self, file_size_bytes: int) -> None:
        if self._profile_setting == "auto":
            self._active_profile = (
                "bulk" if file_size_bytes >= self._auto_bulk_bytes else "normal"
            )
        else:
            self._active_profile = self._profile_setting

    @property
    def active_profile(self) -> str:
        return self._active_profile

    def wants_parallel_scan(self, file_size_bytes: int) -> bool:
        if self._parallel_workers <= 0:
            return False
        return file_size_bytes >= self._parallel_min_bytes

    @property
    def prefix_count(self) -> int:
        return self._prefix_index.count

    def parallel_workers(self) -> int:
        return self._parallel_workers

    def parallel_chunk_lines(self) -> int:
        return self._parallel_chunk

    def parallel_min_bytes(self) -> int:
        return self._parallel_min_bytes

    def _use_embedded(self, has_alpha: bool) -> bool:
        if self._active_profile == "bulk":
            return False
        if self._active_profile == "thorough":
            return True
        if self._embedded_mode == "never":
            return False
        if self._embedded_mode == "always":
            return True
        return has_alpha

    def _emit_findings(
        self,
        line: str,
        file_path: str,
        line_no: int,
        candidates: Iterator[tuple[int, int, str]],
        seen: set[tuple[int, int]],
    ) -> Iterator[Finding]:
        for start, end, digits in candidates:
            span = (start, end)
            if span in seen:
                continue
            if self._prefix_require_match and not self._prefix_index.digits_allowed(
                digits
            ):
                continue
            if self.use_luhn and not luhn_valid_digits(digits):
                continue
            seen.add(span)
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

    def _scan_patterns(self, line: str) -> Iterator[tuple[int, int, str]]:
        for pattern in self._patterns:
            for match in pattern.finditer(line):
                text = match.group(0)
                if not _allowed_pan_chars_only(text):
                    continue
                digits = _digits_only(text)
                if len(digits) >= 13 and (
                    not self._prefix_require_match
                    or self._prefix_index.digits_allowed(digits)
                ):
                    yield match.start(), match.end(), digits

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
        if self._prefix_line_filter and not self._prefix_index.line_may_contain(line):
            return

        flags = precheck_pan_line(line)
        if flags is None:
            return

        if self._active_profile == "bulk":
            yield from self._scan_line_bulk(line, file_path, line_no, flags)
            return

        yield from self._scan_line_normal(line, file_path, line_no, flags)

    def _scan_line_bulk(
        self,
        line: str,
        file_path: str,
        line_no: int,
        flags: PanLineFlags,
    ) -> Iterator[Finding]:
        if skip_obvious_non_pan_line(line, flags):
            return

        seen: set[tuple[int, int]] = set()
        check_dates = flags.has_date_markers
        date_spans: list[tuple[int, int]] | None = None

        def with_plausible(
            items: Iterator[tuple[int, int, str]],
        ) -> Iterator[tuple[int, int, str]]:
            nonlocal date_spans
            for start, end, digits in items:
                if check_dates:
                    if date_spans is None:
                        date_spans = [
                            (m.start(), m.end())
                            for m in DATE_IN_LINE_RE.finditer(line)
                        ]
                    if not is_plausible_pan(
                        digits,
                        line,
                        start,
                        end,
                        date_spans=date_spans,
                        check_dates=True,
                    ):
                        continue
                elif not is_plausible_pan(
                    digits, line, start, end, check_dates=False
                ):
                    continue
                yield start, end, digits

        yield from self._emit_findings(
            line,
            file_path,
            line_no,
            with_plausible(self._scan_patterns(line)),
            seen,
        )

        if self._bulk_digit_run:
            yield from self._emit_findings(
                line,
                file_path,
                line_no,
                with_plausible(
                    iter_bulk_digit_runs(
                        line,
                        digits_allowed=self._prefix_index.digits_allowed
                        if self._prefix_require_match
                        else None,
                    )
                ),
                seen,
            )

    def _scan_line_normal(
        self,
        line: str,
        file_path: str,
        line_no: int,
        flags: PanLineFlags,
    ) -> Iterator[Finding]:
        check_dates = flags.has_date_markers
        date_spans: list[tuple[int, int]] | None = None
        if check_dates:
            date_spans = [
                (m.start(), m.end()) for m in DATE_IN_LINE_RE.finditer(line)
            ]

        seen: set[tuple[int, int]] = set()

        def plausible(items: Iterator[tuple[int, int, str]]) -> Iterator[tuple[int, int, str]]:
            for start, end, digits in items:
                if is_plausible_pan(
                    digits,
                    line,
                    start,
                    end,
                    date_spans=date_spans,
                    check_dates=check_dates,
                ):
                    yield start, end, digits

        yield from self._emit_findings(
            line, file_path, line_no, plausible(self._scan_patterns(line)), seen
        )

        deep_ok = flags.digit_count <= self._deep_scan_max_digits or flags.has_sep
        if deep_ok and (flags.has_sep or not flags.has_alpha):
            yield from self._emit_findings(
                line,
                file_path,
                line_no,
                plausible(
                    _iter_pan_from_line_spans(
                        line, date_spans, check_dates, self._prefix_index
                    )
                ),
                seen,
            )

        if deep_ok and self._use_embedded(flags.has_alpha):
            yield from self._emit_findings(
                line,
                file_path,
                line_no,
                plausible(
                    _iter_pan_from_digit_runs(
                        line,
                        self._embedded_max_gap,
                        date_spans,
                        check_dates,
                        self._prefix_index,
                    )
                ),
                seen,
            )
