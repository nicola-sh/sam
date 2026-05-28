from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Iterator

from regcon.detectors import IpDetector, PanDetector, SecretDetector
from regcon.models import Finding
from regcon.services.scan_line import scan_line_with_detectors
from regcon.util.cancel import CancelCallback, check_cancelled
from regcon.util.job_progress import JobProgress

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None  # type: ignore

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


class FileScanner:
    def __init__(self, config: dict) -> None:
        self.config = config
        self._pan = PanDetector(config)
        self._ip = IpDetector(config)
        self._secrets = SecretDetector(config)
        rc = config.get("regcon", {})
        self.encoding = rc.get("encoding", "utf-8")
        self.fallback_encoding = rc.get("fallback_encoding", "cp1251")
    def _scan_cell(
        self,
        cell_text: str,
        file_path: str,
        line_no: int,
        col_idx: int,
        cell_label: str,
        findings: list[Finding],
    ) -> None:
        for item in scan_line_with_detectors(
            cell_text, file_path, line_no, self._pan, self._ip, self._secrets
        ):
            item.column = col_idx
            item.cell = cell_label
            findings.append(item)

    def _tick(
        self,
        line: str,
        cancel: CancelCallback,
        progress: JobProgress | None = None,
    ) -> None:
        check_cancelled(cancel)
        if progress is not None:
            progress.add_bytes(len(line.encode("utf-8", errors="replace")))
            progress.tick_line()

    def _open_text(self, path: Path):
        try:
            return path.open(encoding=self.encoding, errors="replace")
        except OSError:
            return path.open(encoding=self.fallback_encoding, errors="replace")

    def scan_text_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        with self._open_text(path) as handle:
            for line_no, line in enumerate(handle, start=1):
                self._tick(line, cancel, progress)
                stripped = line.rstrip("\n\r")
                findings.extend(
                    scan_line_with_detectors(
                        stripped,
                        file_path,
                        line_no,
                        self._pan,
                        self._ip,
                        self._secrets,
                    )
                )
        return findings

    def scan_csv_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> list[Finding]:
        if pd is not None:
            return self._scan_csv_pandas(path, on_line, cancel, progress)
        return self._scan_csv_stdlib(path, on_line, cancel, progress)

    def _scan_csv_stdlib(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        with self._open_text(path) as handle:
            reader = csv.reader(handle)
            for line_no, row in enumerate(reader, start=1):
                row_text = ",".join(row)
                self._tick(row_text + "\n", cancel, progress)
                for col_idx, cell in enumerate(row):
                    label = self._cell_name(col_idx, line_no)
                    self._scan_cell(
                        str(cell), file_path, line_no, col_idx, label, findings
                    )
        return findings

    def _scan_csv_pandas(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        try:
            chunks = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                chunksize=10000,
                encoding=self.encoding,
            )
        except UnicodeDecodeError:
            chunks = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                chunksize=10000,
                encoding=self.fallback_encoding,
            )
        line_no = 0
        for chunk in chunks:
            check_cancelled(cancel)
            values = chunk.to_numpy(dtype=str)
            for row in values:
                line_no += 1
                row_text = "\t".join(str(c) for c in row)
                self._tick(row_text + "\n", cancel, progress)
                for col_idx, cell_text in enumerate(row):
                    label = self._cell_name(col_idx, line_no)
                    self._scan_cell(
                        str(cell_text), file_path, line_no, col_idx, label, findings
                    )
        return findings

    def scan_excel_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> list[Finding]:
        if openpyxl is None:
            raise RuntimeError("openpyxl не установлен — нужен для Excel")
        findings: list[Finding] = []
        file_path = str(path)
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        line_no = 0
        try:
            for sheet in workbook.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    line_no += 1
                    row_text = "\t".join("" if v is None else str(v) for v in row)
                    self._tick(row_text + "\n", cancel, progress)
                    for col_idx, value in enumerate(row):
                        if value is None:
                            continue
                        label = f"{sheet.title}!{self._cell_name(col_idx, line_no)}"
                        self._scan_cell(
                            str(value),
                            file_path,
                            line_no,
                            col_idx,
                            label,
                            findings,
                        )
        finally:
            workbook.close()
        return findings

    def scan_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> list[Finding]:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".log", ".json"}:
            return self.scan_text_file(path, on_line, cancel, progress)
        if suffix == ".csv":
            return self.scan_csv_file(path, on_line, cancel, progress)
        if suffix in {".xlsx", ".xlsm"}:
            return self.scan_excel_file(path, on_line, cancel, progress)
        if suffix == ".xls" and pd is not None:
            return self._scan_legacy_xls(path, on_line, cancel, progress)
        return self.scan_text_file(path, on_line, cancel, progress)

    def _scan_legacy_xls(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        frame = pd.read_excel(path, dtype=str, header=None)
        for line_no, row in enumerate(frame.itertuples(index=False), start=1):
            row_text = "\t".join(str(v) for v in row)
            self._tick(row_text + "\n", cancel, progress)
            for col_idx, value in enumerate(row):
                label = self._cell_name(col_idx, line_no)
                self._scan_cell(
                    str(value), file_path, line_no, col_idx, label, findings
                )
        return findings

    @staticmethod
    def _cell_name(col: int, row: int) -> str:
        name = ""
        col_num = col + 1
        while col_num:
            col_num, rem = divmod(col_num - 1, 26)
            name = chr(65 + rem) + name
        return f"{name}{row}"
