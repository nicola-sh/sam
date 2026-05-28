from __future__ import annotations

from pathlib import Path

from regcon.config.pan_prefixes import load_prefix_lines


class PanPrefixIndex:
    """
    Индекс начальных цифр PAN (BIN/префиксы).
    - line_may_contain: быстрый отсев строки
    - digits_allowed: перед Luhn — номер должен начинаться с известного префикса
    """

    __slots__ = ("count", "min_len", "max_len", "_root", "_starters")

    def __init__(self, prefixes: list[str]) -> None:
        self._root: dict = {}
        self._starters: set[str] = set()
        unique = sorted({p for p in prefixes if p.isdigit() and len(p) >= 4}, key=len)
        self.count = len(unique)
        if not unique:
            self.min_len = 0
            self.max_len = 0
            return
        self.min_len = min(len(p) for p in unique)
        self.max_len = max(len(p) for p in unique)
        for prefix in unique:
            self._starters.add(prefix[0])
            node = self._root
            for ch in prefix:
                node = node.setdefault(ch, {})
            node["$"] = True

    @classmethod
    def from_file(cls, path: Path) -> PanPrefixIndex:
        return cls(load_prefix_lines(path))

    @property
    def enabled(self) -> bool:
        return self.count > 0

    def line_may_contain(self, line: str) -> bool:
        if not self.enabled:
            return True
        if not self._starters.intersection(line):
            return False
        for i, ch in enumerate(line):
            if ch not in self._starters:
                continue
            if self._match_from_position(line, i):
                return True
        return False

    def digits_allowed(self, digits: str) -> bool:
        if not self.enabled:
            return True
        node = self._root
        for ch in digits:
            if ch not in node:
                return False
            node = node[ch]
            if "$" in node:
                return True
        return "$" in node

    def _match_from_position(self, line: str, start: int) -> bool:
        node = self._root
        for j in range(start, len(line)):
            ch = line[j]
            if not ch.isdigit():
                if "$" in node:
                    return True
                return False
            if ch not in node:
                return False
            node = node[ch]
            if "$" in node:
                return True
        return "$" in node


def build_prefix_index(
    prefix_file: Path | None,
    extra_hints: tuple[str, ...],
) -> PanPrefixIndex:
    prefixes: list[str] = list(extra_hints)
    if prefix_file and prefix_file.is_file():
        prefixes.extend(load_prefix_lines(prefix_file))
    return PanPrefixIndex(prefixes)
