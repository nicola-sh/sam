from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sam.models.microservice import Microservice
from sam.services.log_fetcher import FetchResult, LogFetcher
from sam.services.ssh_client import SshEndpoint
from sam.util.time_window import TimeWindow
from sam.vault.store import SecretVault

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover
    from PyQt5.QtCore import QThread, pyqtSignal  # type: ignore


@dataclass
class BatchFetchResult:
    """Результат выгрузки одного или нескольких микросервисов."""

    results: list[FetchResult] = field(default_factory=list)

    @property
    def files(self) -> list[Path]:
        out: list[Path] = []
        for r in self.results:
            out.extend(r.files)
        return out

    @property
    def service_ids(self) -> list[str]:
        return [r.service_id for r in self.results]


class FetchWorker(QThread):
    log = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        config: dict[str, Any],
        services: list[Microservice],
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
        time_window: TimeWindow | None = None,
        apply_time_filter: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.services = services
        self.dates = dates
        self.export_dir = Path(export_dir)
        self.grep_value = grep_value
        self.vault = vault
        self.label = label
        self.ssh_endpoint = ssh_endpoint
        self.target_kind = target_kind
        self.target_id = target_id
        self.host_id = host_id
        self.time_window = time_window
        self.apply_time_filter = apply_time_filter

    def run(self) -> None:
        try:
            fetcher = LogFetcher(self.config, self.vault, ssh_endpoint=self.ssh_endpoint)
            batch = BatchFetchResult()
            for svc in self.services:
                if self.isInterruptionRequested():
                    raise InterruptedError("Отменено пользователем")
                self.log.emit(f"─── Микросервис: {svc.display_name} ───")
                result = fetcher.fetch(
                    svc,
                    self.dates,
                    self.export_dir,
                    grep_value=self.grep_value,
                    label=self.label,
                    log=self.log.emit,
                    cancel=self.isInterruptionRequested,
                    target_kind=self.target_kind,
                    target_id=self.target_id,
                    host_id=self.host_id,
                    time_window=self.time_window,
                    apply_time_filter=self.apply_time_filter,
                )
                batch.results.append(result)
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            self.finished_ok.emit(batch)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
