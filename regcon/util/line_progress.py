from __future__ import annotations

from typing import Callable

EmitCallback = Callable[[int, int, int], None]


class LineProgressTracker:
    """Прогресс по строкам: done / total → процент."""

    def __init__(self, total_lines: int, emit: EmitCallback) -> None:
        self.total = max(total_lines, 1)
        self.done = 0
        self._emit = emit
        self._last_percent = -1

    def tick(self, count: int = 1) -> None:
        self.done += count
        percent = min(100, int(self.done * 100 / self.total))
        if percent != self._last_percent or self.done >= self.total:
            self._last_percent = percent
            self._emit(percent, self.done, self.total)

    def finish(self) -> None:
        self.done = self.total
        self._emit(100, self.total, self.total)
