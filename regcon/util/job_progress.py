from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

StatusCallback = Callable[[int, str], None]


class JobProgress:
    """Прогресс по объёму файлов + статус каждые N секунд (без предподсчёта строк)."""

    def __init__(
        self,
        files: list[Path],
        emit: StatusCallback,
        heartbeat_sec: float = 5.0,
    ) -> None:
        self.files = files
        self.emit = emit
        self.heartbeat_sec = heartbeat_sec
        self.file_sizes = [max(p.stat().st_size, 1) if p.exists() else 1 for p in files]
        self.total_bytes = sum(self.file_sizes) or 1
        self.bytes_done = 0
        self.file_index = 0
        self.lines_done = 0
        self._last_beat = time.monotonic()
        self._current_name = ""

    def start_file(self, index: int, name: str) -> None:
        self.file_index = index
        self.lines_done = 0
        self._current_name = name
        self._pulse(force=True)

    def add_bytes(self, count: int) -> None:
        if count > 0:
            self.bytes_done = min(self.total_bytes, self.bytes_done + count)
        self._pulse()

    def tick_line(self) -> None:
        self.lines_done += 1
        self._pulse()

    def finish(self) -> None:
        self.bytes_done = self.total_bytes
        self.emit(100, "Готово")

    def _pulse(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_beat) < self.heartbeat_sec:
            return
        self._last_beat = now
        pct = min(99, int(self.bytes_done * 100 / self.total_bytes))
        msg = f"{self._current_name} · {self.lines_done:,} стр."
        if len(self.files) > 1:
            msg = f"[{self.file_index + 1}/{len(self.files)}] {msg}"
        self.emit(pct, msg)
