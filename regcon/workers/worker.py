from __future__ import annotations

from pathlib import Path
from typing import Any

from regcon.models import Finding
from regcon.services.audit import write_audit
from regcon.services.converter import csv_to_excel
from regcon.services.line_count import count_file_lines, count_files_lines
from regcon.services.processor import FileProcessor
from regcon.services.scanner import FileScanner
from regcon.util.cancel import CancelledError
from regcon.util.line_progress import LineProgressTracker

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover
    from PyQt5.QtCore import QThread, pyqtSignal  # type: ignore


class Worker(QThread):
    progress = pyqtSignal(int)
    progress_lines = pyqtSignal(int, int, int)
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
        findings: list[dict[str, Any]] | None = None,
        job_options: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.files = [Path(f) for f in files]
        self.mode = mode
        self.config = config
        self.output_dir = Path(output_dir)
        self.findings = [Finding.from_dict(item) for item in (findings or [])]
        self.job_options = job_options or {}
        rc = config.get("regcon", {})
        self._encoding = rc.get("encoding", "utf-8")
        self._fallback = rc.get("fallback_encoding", "cp1251")
        self._line_progress: LineProgressTracker | None = None

    def _cancel_check(self) -> bool:
        return self.isInterruptionRequested()

    def _emit_line_progress(self, percent: int, done: int, total: int) -> None:
        self.progress.emit(percent)
        self.progress_lines.emit(percent, done, total)

    def _prepare_line_progress(
        self, paths: list[Path], line_multiplier: int = 1
    ) -> LineProgressTracker:
        self.log.emit("Подсчёт строк…")
        base = 0
        for path in paths:
            lines = count_file_lines(path, self._encoding, self._fallback)
            base += lines
            self.log.emit(f"  {path.name}: {lines:,} строк")
        total = base * max(line_multiplier, 1)
        self.log.emit(f"Всего к обработке: {total:,} строк")
        tracker = LineProgressTracker(total, self._emit_line_progress)
        self._line_progress = tracker
        return tracker

    def run(self) -> None:
        try:
            if self.mode == "scan":
                self._run_scan()
            elif self.mode == "mask":
                self._run_mask()
            elif self.mode == "csv2xlsx":
                self._run_csv2xlsx()
            elif self.mode == "format_json":
                self._run_format_json()
            elif self.mode == "full":
                self._run_full()
            else:
                raise ValueError(f"Неизвестный режим: {self.mode}")
            if self._line_progress:
                self._line_progress.finish()
            elif not self._cancel_check():
                self.progress.emit(100)
            if self._cancel_check():
                self.cancelled.emit()
            else:
                self.finished_ok.emit()
        except CancelledError:
            self.log.emit("Операция остановлена пользователем.")
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            if self._cancel_check():
                self.cancelled.emit()
            else:
                self.error.emit(str(exc))

    def _run_scan(self) -> None:
        tracker = self._prepare_line_progress(self.files)
        scanner = FileScanner(self.config)
        all_findings: list[Finding] = []
        for path in self.files:
            if self._cancel_check():
                raise CancelledError()
            self.log.emit(f"Сканирование: {path.name}")
            findings = scanner.scan_file(
                path,
                cancel=self._cancel_check,
                progress=tracker,
            )
            all_findings.extend(findings)
            self.log.emit(f"  найдено: {len(findings)}")
        if self._cancel_check():
            raise CancelledError()
        write_audit(
            self.output_dir,
            self.config,
            "scan",
            {"files": [str(p) for p in self.files], "count": len(all_findings)},
        )
        self.log.emit(f"Итого совпадений: {len(all_findings)}")
        self.scan_done.emit([f.to_dict() for f in all_findings])

    def _run_mask(self) -> None:
        selected = [f for f in self.findings if f.selected]
        if not selected:
            raise ValueError("Нет отмеченных совпадений для маскирования")
        by_file: dict[str, list[Finding]] = {}
        for item in selected:
            by_file.setdefault(item.file_path, []).append(item)
        paths = [p for p in self.files if by_file.get(str(p))]
        tracker = self._prepare_line_progress(paths)
        processor = FileProcessor(self.config)
        outputs: list[str] = []
        for path in paths:
            if self._cancel_check():
                raise CancelledError()
            self.log.emit(f"Маскирование: {path.name}")
            file_findings = by_file.get(str(path), [])
            target = processor.mask_file(
                path,
                file_findings,
                self.output_dir,
                cancel=self._cancel_check,
                progress=tracker,
            )
            outputs.append(str(target))
            self.log.emit(f"  записано: {target.name}")
        write_audit(
            self.output_dir,
            self.config,
            "mask",
            {
                "files": [str(p) for p in paths],
                "replacements": len(selected),
                "outputs": outputs,
            },
        )

    def _run_csv2xlsx(self) -> None:
        mask_first = bool(self.job_options.get("mask_before", False))
        format_json = bool(self.job_options.get("format_json_cells", False))
        use_existing_findings = bool(self.job_options.get("use_existing_findings", False))

        csv_files = [p for p in self.files if p.suffix.lower() == ".csv"]
        if not csv_files:
            raise ValueError("Нет CSV-файлов для конвертации.")

        scanner = FileScanner(self.config)
        processor = FileProcessor(self.config)
        mult = 2 if mask_first else 1
        tracker = self._prepare_line_progress(csv_files, line_multiplier=mult)

        for path in csv_files:
            if self._cancel_check():
                raise CancelledError()
            self.log.emit(f"CSV → Excel: {path.name}")
            source = path

            if mask_first:
                if use_existing_findings and self.findings:
                    file_findings = [
                        f
                        for f in self.findings
                        if f.selected and f.file_path == str(path)
                    ]
                else:
                    self.log.emit("  поиск…")
                    file_findings = scanner.scan_file(
                        path,
                        cancel=self._cancel_check,
                        progress=tracker,
                    )
                    for item in file_findings:
                        item.selected = True
                if file_findings:
                    self.log.emit(f"  обезличивание: {len(file_findings)}")
                    source = processor.mask_file(
                        path,
                        file_findings,
                        self.output_dir,
                        cancel=self._cancel_check,
                        progress=tracker,
                    )

            if format_json:
                self.log.emit("  JSON в ячейках")

            target = csv_to_excel(
                source,
                self.output_dir,
                self.config,
                cancel=self._cancel_check,
                format_json_cells=format_json,
                output_name=f"{path.stem}.xlsx",
            )
            self.log.emit(f"  → {target.name}")
            if not mask_first:
                lines = count_file_lines(path, self._encoding, self._fallback)
                tracker.tick(lines)

        write_audit(
            self.output_dir,
            self.config,
            "csv2xlsx",
            {
                "files": [str(p) for p in csv_files],
                "mask_before": mask_first,
                "format_json_cells": format_json,
            },
        )

    def _run_format_json(self) -> None:
        processor = FileProcessor(self.config)
        indent = int(self.config.get("json", {}).get("indent", 2))
        tracker = self._prepare_line_progress(self.files)
        for path in self.files:
            self.log.emit(f"JSON: {path.name}")
            target = processor.format_json_in_text_file(
                path,
                self.output_dir,
                indent=indent,
                cancel=self._cancel_check,
                progress=tracker,
            )
            self.log.emit(f"  → {target.name}")

    def _run_full(self) -> None:
        self._run_scan()
