from __future__ import annotations

from pathlib import Path
from typing import Any

from regcon.models import Finding
from regcon.services.audit import write_audit
from regcon.services.converter import csv_to_excel
from regcon.services.processor import FileProcessor
from regcon.services.scanner import FileScanner
from regcon.util.cancel import CancelledError
from regcon.util.job_progress import JobProgress

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover
    from PyQt5.QtCore import QThread, pyqtSignal  # type: ignore


class Worker(QThread):
    progress = pyqtSignal(int)
    progress_status = pyqtSignal(int, str)
    log = pyqtSignal(str)
    finished_ok = pyqtSignal()
    cancelled = pyqtSignal()
    error = pyqtSignal(str)
    scan_done = pyqtSignal(list)

    def __init__(
        self,
        files: list[str],
        mode: str,
        config: dict[str, Any],
        output_dir: str,
        data_dir: str,
        findings: list[dict[str, Any]] | None = None,
        job_options: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.files = [Path(f) for f in files]
        self.mode = mode
        self.config = config
        self.output_dir = Path(output_dir)
        self.data_dir = Path(data_dir)
        self.findings = [Finding.from_dict(item) for item in (findings or [])]
        self.job_options = job_options or {}
        rc = config.get("regcon", {})
        self._heartbeat = float(rc.get("progress_heartbeat_sec", 5.0))
        self._job_progress: JobProgress | None = None

    def _cancel_check(self) -> bool:
        return self.isInterruptionRequested()

    def _emit_status(self, percent: int, message: str) -> None:
        self.progress.emit(percent)
        self.progress_status.emit(percent, message)

    def _make_progress(self, paths: list[Path]) -> JobProgress:
        tracker = JobProgress(paths, self._emit_status, self._heartbeat)
        self._job_progress = tracker
        return tracker

    def run(self) -> None:
        try:
            if self.mode == "scan":
                self._run_scan()
            elif self.mode == "mask":
                self._run_mask()
            elif self.mode == "csv2xlsx":
                self._run_csv2xlsx()
            else:
                raise ValueError(f"Неизвестный режим: {self.mode}")
            if self._job_progress:
                self._job_progress.finish()
            elif not self._cancel_check():
                self.progress.emit(100)
                self.progress_status.emit(100, "Готово")
            if self._cancel_check():
                self.cancelled.emit()
            else:
                self.finished_ok.emit()
        except CancelledError:
            self.log.emit("Остановка.")
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            if self._cancel_check():
                self.cancelled.emit()
            else:
                self.error.emit(str(exc))

    def _run_scan(self) -> None:
        progress = self._make_progress(self.files)
        scanner = FileScanner(self.config)
        all_findings: list[Finding] = []
        for idx, path in enumerate(self.files):
            if self._cancel_check():
                raise CancelledError()
            progress.start_file(idx, path.name)
            self.log.emit(f"Скан: {path.name}")
            found = scanner.scan_file(path, cancel=self._cancel_check, progress=progress)
            if scanner._pan.prefix_count:
                self.log.emit(f"  PAN: префиксов {scanner._pan.prefix_count}")
            elif scanner._pan.enabled:
                self.log.emit("  PAN: справочник пуст (кнопка 8… в окне)")
            all_findings.extend(found)
            self.log.emit(f"  +{len(found)}")
        write_audit(
            self.data_dir,
            self.config,
            "scan",
            {"files": [str(p) for p in self.files], "count": len(all_findings)},
        )
        self.scan_done.emit([f.to_dict() for f in all_findings])

    def _run_mask(self) -> None:
        selected = [f for f in self.findings if f.selected]
        if not selected:
            raise ValueError("Нет отмеченных совпадений")
        by_file: dict[str, list[Finding]] = {}
        for item in selected:
            by_file.setdefault(item.file_path, []).append(item)
        paths = [p for p in self.files if by_file.get(str(p))]
        progress = self._make_progress(paths)
        processor = FileProcessor(self.config)
        for idx, path in enumerate(paths):
            if self._cancel_check():
                raise CancelledError()
            progress.start_file(idx, path.name)
            self.log.emit(f"Маска: {path.name}")
            processor.mask_file(
                path,
                by_file[str(path)],
                self.output_dir,
                cancel=self._cancel_check,
                progress=progress,
            )
        write_audit(
            self.data_dir,
            self.config,
            "mask",
            {"files": [str(p) for p in paths], "replacements": len(selected)},
        )

    def _run_csv2xlsx(self) -> None:
        mask_first = bool(self.job_options.get("mask_before", False))
        format_json = bool(self.job_options.get("format_json_cells", False))
        use_existing = bool(self.job_options.get("use_existing_findings", False))

        csv_files = [p for p in self.files if p.suffix.lower() == ".csv"]
        if not csv_files:
            raise ValueError("Нет CSV-файлов")

        scanner = FileScanner(self.config)
        processor = FileProcessor(self.config)
        progress = self._make_progress(csv_files)

        for idx, path in enumerate(csv_files):
            if self._cancel_check():
                raise CancelledError()
            progress.start_file(idx, path.name)
            source = path

            if mask_first:
                if use_existing and self.findings:
                    file_findings = [
                        f
                        for f in self.findings
                        if f.selected and f.file_path == str(path)
                    ]
                else:
                    file_findings = scanner.scan_file(
                        path, cancel=self._cancel_check, progress=progress
                    )
                    for item in file_findings:
                        item.selected = True
                if file_findings:
                    source = processor.mask_file(
                        path,
                        file_findings,
                        self.output_dir,
                        cancel=self._cancel_check,
                        progress=progress,
                    )

            csv_to_excel(
                source,
                self.output_dir,
                self.config,
                cancel=self._cancel_check,
                format_json_cells=format_json,
                output_name=f"{path.stem}.xlsx",
            )
            progress.add_bytes(max(path.stat().st_size // 4, 1))

        write_audit(
            self.data_dir,
            self.config,
            "csv2xlsx",
            {"files": [str(p) for p in csv_files]},
        )
