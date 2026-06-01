from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sam.models.microservice import Microservice
from sam.services.log_fetcher import LogFetcher
from sam.services.ssh_client import SshEndpoint
from sam.vault.store import SecretVault

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
        service: Microservice,
        dates: list[date],
        export_dir: str,
        grep_value: str | None,
        vault: SecretVault | None,
        *,
        label: str | None = None,
        ssh_endpoint: SshEndpoint | None = None,
        target_kind: str = "",
        target_id: str = "",
        host_id: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.service = service
        self.dates = dates
        self.export_dir = Path(export_dir)
        self.grep_value = grep_value
        self.vault = vault
        self.label = label
        self.ssh_endpoint = ssh_endpoint
        self.target_kind = target_kind
        self.target_id = target_id
        self.host_id = host_id

    def run(self) -> None:
        try:
            fetcher = LogFetcher(self.config, self.vault, ssh_endpoint=self.ssh_endpoint)
            result = fetcher.fetch(
                self.service,
                self.dates,
                self.export_dir,
                grep_value=self.grep_value,
                label=self.label,
                log=self.log.emit,
                cancel=self.isInterruptionRequested,
                target_kind=self.target_kind,
                target_id=self.target_id,
                host_id=self.host_id,
            )
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            self.finished_ok.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
