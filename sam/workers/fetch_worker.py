from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sam.services.atm_ddc_fetcher import AtmDdcFetcher

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover
    from PyQt5.QtCore import QThread, pyqtSignal  # type: ignore


class FetchWorker(QThread):
    log = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        config: dict[str, Any],
        atm_id: str,
        day: date,
        export_dir: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.atm_id = atm_id
        self.day = day
        self.export_dir = Path(export_dir)

    def run(self) -> None:
        try:
            fetcher = AtmDdcFetcher(self.config)
            result = fetcher.fetch(
                self.atm_id,
                self.day,
                self.export_dir,
                log=self.log.emit,
                cancel=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            self.finished_ok.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 — показать оператору
            self.error.emit(str(exc))
