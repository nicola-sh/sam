from __future__ import annotations

from pathlib import Path
from typing import Any

from regcon.models import Finding
from regcon.services.audit import write_audit
from regcon.services.converter import csv_to_excel
from regcon.services.processor import FileProcessor
from regcon.services.scanner import FileScanner

try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:  # pragma: no cover
    from PyQt5.QtCore import QThread, pyqtSignal  # type: ignore


class Worker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)
    scan_done = pyqtSignal(list)

    def __init__(
        self,
        files: list[str],
        mode: str,
        config: dict[str, Any],
        output_dir: str,
        findings: list[dict[str, Any]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.files = [Path(f) for f in files]
        self.mode = mode
        self.config = config
        self.output_dir = Path(output_dir)
        self.findings = [Finding.from_dict(item) for item in (findings or [])]

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
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001 — показать пользователю
            self.error.emit(str(exc))

    def _emit_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.progress.emit(0)
            return
        self.progress.emit(int(current / total * 100))

    def _run_scan(self) -> None:
        scanner = FileScanner(self.config)
        all_findings: list[Finding] = []
        total = len(self.files)
        for idx, path in enumerate(self.files, start=1):
            self.log.emit(f"Сканирование: {path.name}")
            findings = scanner.scan_file(
                path,
                on_line=lambda _ln: None,
            )
            all_findings.extend(findings)
            self.log.emit(f"  найдено: {len(findings)}")
            self._emit_progress(idx, total)
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
            target = processor.mask_file(
                path,
                file_findings,
                self.output_dir,
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
        total = len(self.files)
        for idx, path in enumerate(self.files, start=1):
            if path.suffix.lower() != ".csv":
                self.log.emit(f"Пропуск (не CSV): {path.name}")
                continue
            self.log.emit(f"Конвертация: {path.name}")
            target = csv_to_excel(
                path,
                self.output_dir,
                self.config,
                on_progress=lambda pct: self.progress.emit(
                    int((idx - 1) / total * 100 + pct / total)
                ),
            )
            self.log.emit(f"  Excel: {target.name}")
            self._emit_progress(idx, total)
        write_audit(
            self.output_dir,
            self.config,
            "csv2xlsx",
            {"files": [str(p) for p in self.files]},
        )
        self.progress.emit(100)

    def _run_format_json(self) -> None:
        processor = FileProcessor(self.config)
        indent = int(self.config.get("json", {}).get("indent", 2))
        total = len(self.files)
        for idx, path in enumerate(self.files, start=1):
            self.log.emit(f"JSON: {path.name}")
            target = processor.format_json_in_text_file(
                path, self.output_dir, indent=indent
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
            found = scanner.scan_file(path)
            all_findings.extend(found)
            self.findings = found
            if found:
                processor.mask_file(path, found, self.output_dir)
            if path.suffix.lower() == ".csv":
                csv_to_excel(path, self.output_dir, self.config)
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
