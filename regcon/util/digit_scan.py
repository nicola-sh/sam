from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PanLineFlags:
    digit_count: int
    has_alpha: bool
    has_sep: bool
    has_date_markers: bool


def precheck_pan_line(line: str, min_digits: int = 13) -> PanLineFlags | None:
    """
    Один быстрый проход: None, если цифр < min_digits (типичная строка лога).
    """
    digit_count = 0
    has_alpha = False
    has_sep = False
    has_date_markers = False
    prev_digit = False
    for ch in line:
        if ch.isdigit():
            digit_count += 1
            if digit_count >= min_digits and has_alpha:
                # дальше считаем только для has_sep / date_markers
                pass
        elif ch.isalpha():
            has_alpha = True
        elif ch in "-/.:":
            has_date_markers = True
            if ch in " -" and prev_digit:
                has_sep = True
        elif ch == " " and prev_digit:
            has_sep = True
        prev_digit = ch.isdigit()

    if digit_count < min_digits:
        return None
    return PanLineFlags(
        digit_count=digit_count,
        has_alpha=has_alpha,
        has_sep=has_sep,
        has_date_markers=has_date_markers,
    )


def line_has_bin_hint(line: str, hints: tuple[str, ...]) -> bool:
    if not hints:
        return True
    for hint in hints:
        if hint in line:
            return True
    return False
