from __future__ import annotations


def split_context(line: str, start: int, end: int, radius: int = 30) -> tuple[str, str]:
    """30 символов до и после совпадения (как в строке файла)."""
    before = line[max(0, start - radius) : start]
    after = line[end : min(len(line), end + radius)]
    return before, after
