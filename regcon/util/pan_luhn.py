from __future__ import annotations

# Удвоение цифры по Luhn (значение после сложения разрядов)
_LUHN_DOUBLE = (0, 2, 4, 6, 8, 1, 3, 5, 7, 9)


def luhn_valid_digits(digits: str) -> bool:
    n = len(digits)
    if n < 13 or n > 19:
        return False
    total = 0
    parity = n % 2
    for i, ch in enumerate(digits):
        d = ord(ch) - 48
        if i % 2 == parity:
            total += _LUHN_DOUBLE[d]
        else:
            total += d
    return total % 10 == 0
