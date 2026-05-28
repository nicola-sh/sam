from __future__ import annotations

from pathlib import Path
from typing import Any

from regcon.models import Finding
from regcon.services.audit import write_audit
from regcon.services.converter import csv_to_excel
from regcon.services.processor import FileProcessor
from regcon.services.scanner import FileScanner
from regcon.util.cancel import CancelledError

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover
    from PyQt5.QtCore import QThread, pyqtSignal  # type: ignore


class Worker(QThread):
    progress = pyqtSignal(int)
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

    def _cancel_check(self) -> bool:
        return self.isInterruptionRequested()

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

    def _emit_progress(self, current: int, total: int) -> None:
        if self._cancel_check():
            raise CancelledError()
        if total <= 0:
            self.progress.emit(0)
            return
        self.progress.emit(int(current / total * 100))

    def _on_line_progress(self, file_idx: int, total_files: int, line_no: int) -> None:
        if line_no % 5000 == 0:
            self.log.emit(f"  … строка {line_no:,}")
        self._emit_progress(file_idx, total_files)

    def _run_scan(self) -> None:
        scanner = FileScanner(self.config)
        all_findings: list[Finding] = []
        total = len(self.files)
        for idx, path in enumerate(self.files, start=1):
            self.log.emit(f"Сканирование: {path.name}")

            def on_line(ln: int) -> None:
                if ln % 5000 == 0:
                    self.log.emit(f"  … строка {ln:,}")

            findings = scanner.scan_file(
                path,
                on_line=on_line,
                cancel=self._cancel_check,
            )
            all_findings.extend(findings)
            self.log.emit(f"  найдено: {len(findings)}")
            self._emit_progress(idx, total)
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
        self.progress.emit(100)

    def _run_mask(self) -> None:
        processor = FileProcessor(self.config)
        selected = [f for f in self.findings if f.selected]
        if not selected:
            raise ValueError("Нет отмеченных совпадений для маскирования")
        by_file: dict[str, list[Finding]] = {}
        for item in selected:
            by_file.setdefault(item.file_path, []).append(item)
        total = len(self.files)
        outputs: list[str] = []
        for idx, path in enumerate(self.files, start=1):
            self.log.emit(f"Маскирование: {path.name}")
            file_findings = by_file.get(str(path), [])
            if not file_findings:
                self.log.emit("  пропуск (нет отмеченных совпадений)")
                self._emit_progress(idx, total)
                continue

            def on_line(ln: int) -> None:
                if ln % 5000 == 0:
                    self.log.emit(f"  … строка {ln:,}")

            target = processor.mask_file(
                path,
                file_findings,
                self.output_dir,
                on_line=on_line,
                cancel=self._cancel_check,
            )
            outputs.append(str(target))
            self.log.emit(f"  записано: {target.name}")
            self._emit_progress(idx, total)
        write_audit(
            self.output_dir,
            self.config,
            "mask",
            {
                "files": [str(p) for p in self.files],
                "replacements": len(selected),
                "outputs": outputs,
            },
        )
        self.progress.emit(100)

    def _run_csv2xlsx(self) -> None:
        mask_first = bool(self.job_options.get("mask_before", False))
        format_json = bool(self.job_options.get("format_json_cells", False))
        use_existing_findings = bool(self.job_options.get("use_existing_findings", False))

        csv_files = [p for p in self.files if p.suffix.lower() == ".csv"]
        if not csv_files:
            raise ValueError("Нет CSV-файлов для конвертации.")

        scanner = FileScanner(self.config)
        processor = FileProcessor(self.config)
        total = len(csv_files)

        for idx, path in enumerate(csv_files, start=1):
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
                    self.log.emit("  поиск чувствительных данных…")
                    file_findings = scanner.scan_file(
                        path, cancel=self._cancel_check
                    )
                    for item in file_findings:
                        item.selected = True
                if file_findings:
                    self.log.emit(f"  обезличивание: {len(file_findings)} замен")
                    source = processor.mask_file(
                        path,
                        file_findings,
                        self.output_dir,
                        cancel=self._cancel_check,
                    )
                else:
                    self.log.emit("  чувствительные данные не найдены")

            if format_json:
                self.log.emit("  форматирование JSON в ячейках")

            target = csv_to_excel(
                source,
                self.output_dir,
                self.config,
                on_progress=lambda pct, i=idx, t=total: self.progress.emit(
                    int((i - 1) / t * 100 + pct / t)
                ),
                cancel=self._cancel_check,
                format_json_cells=format_json,
                output_name=f"{path.stem}.xlsx",
            )
            self.log.emit(f"  готово: {target.name}")
            self._emit_progress(idx, total)

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
        self.progress.emit(100)

    def _run_format_json(self) -> None:
        processor = FileProcessor(self.config)
        indent = int(self.config.get("json", {}).get("indent", 2))
        total = len(self.files)
        every = int(self.config.get("regcon", {}).get("progress_every_lines", 5000))
        for idx, path in enumerate(self.files, start=1):
            self.log.emit(f"JSON: {path.name}")

            def on_line(ln: int) -> None:
                if ln % every == 0:
                    self.log.emit(f"  … строка {ln:,}")
                check = self._cancel_check
                if check():
                    raise CancelledError()

            target = processor.format_json_in_text_file(
                path,
                self.output_dir,
                indent=indent,
                on_line=on_line,
                cancel=self._cancel_check,
            )
            self.log.emit(f"  → {target.name}")
            self._emit_progress(idx, total)
        write_audit(
            self.output_dir,
            self.config,
            "format_json",
            {"files": [str(p) for p in self.files]},
        )
        self.progress.emit(100)

    def _run_full(self) -> None:
        scanner = FileScanner(self.config)
        processor = FileProcessor(self.config)
        all_findings: list[Finding] = []
        total = len(self.files)
        for idx, path in enumerate(self.files, start=1):
            self.log.emit(f"Полный цикл: {path.name}")
            found = scanner.scan_file(path, cancel=self._cancel_check)
            all_findings.extend(found)
            if found:
                processor.mask_file(
                    path, found, self.output_dir, cancel=self._cancel_check
                )
            if path.suffix.lower() == ".csv":
                csv_to_excel(
                    path, self.output_dir, self.config, cancel=self._cancel_check
                )
            if path.suffix.lower() in {".txt", ".log", ".json"}:
                indent = int(self.config.get("json", {}).get("indent", 2))
                processor.format_json_in_text_file(
                    path, self.output_dir, indent=indent
                )
            self._emit_progress(idx, total)
        write_audit(
            self.output_dir,
            self.config,
            "full",
            {"files": [str(p) for p in self.files], "count": len(all_findings)},
        )
        self.scan_done.emit([f.to_dict() for f in all_findings])
        self.progress.emit(100)
