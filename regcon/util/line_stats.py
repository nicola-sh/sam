from __future__ import annotations


def line_digit_stats(line: str) -> tuple[int, bool, bool]:
    """
    digit_count, has_alpha, has_digit_separator (пробел/дефис рядом с цифрами).
    Один проход по строке.
    """
    digit_count = 0
    has_alpha = False
    has_sep = False
    prev_digit = False
    for ch in line:
        if ch.isdigit():
            digit_count += 1
            if prev_digit and not has_sep:
                pass
            prev_digit = True
        else:
            if ch.isalpha():
                has_alpha = True
            elif ch in " -" and prev_digit:
                has_sep = True
            prev_digit = False
    return digit_count, has_alpha, has_sep
