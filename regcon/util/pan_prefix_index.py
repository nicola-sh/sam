from __future__ import annotations

from pathlib import Path

from regcon.config.pan_prefixes import DEFAULT_PREFIX_LEN, load_prefix_lines
from regcon.util.pan_luhn import luhn_valid_digits

# Длины PAN после совпадения 8 цифр префикса (сначала типичная 16)
_PAN_LENGTHS = (16, 19, 18, 17, 15, 14, 13)


def _is_digit_gap(ch: str, has_digits: bool) -> bool:
    """Пробел, таб, двоеточие и т.п. между цифрами номера."""
    return has_digits and not ch.isdigit() and not ch.isalpha()


class PanPrefixIndex:
    """
    Справочник первых 8 цифр PAN.
    Поиск: в строке находим начало по префиксу → собираем 13–19 цифр → Luhn.
    """

    __slots__ = ("count", "prefix_len", "_prefixes", "_starters")

    def __init__(
        self, prefixes: list[str], prefix_len: int = DEFAULT_PREFIX_LEN
    ) -> None:
        self.prefix_len = prefix_len
        self._prefixes: frozenset[str] = frozenset()
        self._starters: set[str] = set()
        valid = {
            p[:prefix_len]
            for p in prefixes
            if p.isdigit() and len(p) >= prefix_len
        }
        self._prefixes = frozenset(valid)
        self._starters = {p[0] for p in self._prefixes}
        self.count = len(self._prefixes)

    @classmethod
    def from_file(cls, path: Path, prefix_len: int = DEFAULT_PREFIX_LEN) -> PanPrefixIndex:
        return cls(load_prefix_lines(path, prefix_len), prefix_len)

    @property
    def enabled(self) -> bool:
        return self.count > 0

    def line_may_contain(self, line: str) -> bool:
        if not self.enabled:
            return False
        if not self._starters.intersection(line):
            return False
        n = len(line)
        plen = self.prefix_len
        for i, ch in enumerate(line):
            if ch not in self._starters:
                continue
            digits = self._collect_digits(line, i)
            if len(digits) >= plen and digits[:plen] in self._prefixes:
                return True
        return False

    def iter_pan_candidates(self, line: str) -> list[tuple[int, int, str]]:
        """(start, end, digits_only) для каждого PAN с известным префиксом и Luhn."""
        if not self.enabled:
            return []
        found: list[tuple[int, int, str]] = []
        seen_spans: set[tuple[int, int]] = set()
        n = len(line)
        plen = self.prefix_len
        i = 0
        while i < n:
            if line[i] not in self._starters or not line[i].isdigit():
                i += 1
                continue
            digits, positions = self._collect_digits_with_pos(line, i)
            if len(digits) < plen:
                i += 1
                continue
            if digits[:plen] not in self._prefixes:
                i += 1
                continue
            for length in _PAN_LENGTHS:
                if len(digits) < length:
                    continue
                chunk = digits[:length]
                if not luhn_valid_digits(chunk):
                    continue
                start = positions[0]
                end = positions[length - 1] + 1
                span = (start, end)
                if span in seen_spans:
                    break
                seen_spans.add(span)
                found.append((start, end, chunk))
                break
            i += 1
        return found

    @staticmethod
    def _collect_digits(line: str, start: int) -> str:
        parts: list[str] = []
        j = start
        while j < len(line) and len(parts) < 19:
            ch = line[j]
            if ch.isdigit():
                parts.append(ch)
                j += 1
            elif _is_digit_gap(ch, bool(parts)):
                j += 1
            else:
                break
        return "".join(parts)

    def _collect_digits_with_pos(
        self, line: str, start: int
    ) -> tuple[str, list[int]]:
        digits: list[str] = []
        positions: list[int] = []
        j = start
        while j < len(line) and len(digits) < 19:
            ch = line[j]
            if ch.isdigit():
                digits.append(ch)
                positions.append(j)
                j += 1
            elif _is_digit_gap(ch, bool(digits)):
                j += 1
            else:
                break
        return "".join(digits), positions


def build_prefix_index(
    prefix_file: Path | None,
    extra_hints: tuple[str, ...],
    prefix_len: int = DEFAULT_PREFIX_LEN,
) -> PanPrefixIndex:
    prefixes: list[str] = [h[:prefix_len] for h in extra_hints if h.isdigit()]
    if prefix_file and prefix_file.is_file():
        prefixes.extend(load_prefix_lines(prefix_file, prefix_len))
    return PanPrefixIndex(prefixes, prefix_len)
