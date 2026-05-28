from __future__ import annotations

import re
from typing import Iterator

from regcon.detectors.pan_luhn import luhn_valid_digits
from regcon.util.digit_scan import PanLineFlags, line_has_bin_hint

# Сплошной блок 13–19 цифр (без перебора всех подстрок)
BULK_DIGIT_RUN_RE = re.compile(r"(?<!\d)(\d{13,19})(?!\d)")

# Типичная строка access-log: дата в начале, без PAN
_LOG_DATE_PREFIX_RE = re.compile(
    r"^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}"
)


def skip_obvious_non_pan_line(line: str, flags: PanLineFlags) -> bool:
    """Быстрый отсев строк, где PAN заведомо не ищем (bulk, 10M+ строк)."""
    if not flags.has_alpha and _LOG_DATE_PREFIX_RE.match(line):
        return True
    return False


def iter_bulk_digit_runs(line: str) -> Iterator[tuple[int, int, str]]:
    for match in BULK_DIGIT_RUN_RE.finditer(line):
        digits = match.group(1)
        if luhn_valid_digits(digits):
            yield match.start(1), match.end(1), digits
