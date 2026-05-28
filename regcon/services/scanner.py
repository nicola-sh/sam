from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Iterator

from regcon.detectors import IpDetector, PanDetector, SecretDetector
from regcon.models import Finding

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
        self._detectors = [
            PanDetector(config),
            IpDetector(config),
            SecretDetector(config),
        ]
        rc = config.get("regcon", {})
        self.encoding = rc.get("encoding", "utf-8")
        self.fallback_encoding = rc.get("fallback_encoding", "cp1251")

    def _open_text(self, path: Path):
        try:
            return path.open(encoding=self.encoding, errors="replace")
        except OSError:
            return path.open(encoding=self.fallback_encoding, errors="replace")

    def scan_text_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        with self._open_text(path) as handle:
            for line_no, line in enumerate(handle, start=1):
                if on_line:
                    on_line(line_no)
                for detector in self._detectors:
                    findings.extend(
                        detector.scan_line(line.rstrip("\n\r"), file_path, line_no)
                    )
        return findings

    def scan_csv_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
    ) -> list[Finding]:
        if pd is not None:
            return self._scan_csv_pandas(path, on_line)
        return self._scan_csv_stdlib(path, on_line)

    def _scan_csv_stdlib(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        with self._open_text(path) as handle:
            reader = csv.reader(handle)
            for line_no, row in enumerate(reader, start=1):
                if on_line:
                    on_line(line_no)
                for col_idx, cell in enumerate(row):
                    cell_text = str(cell)
                    for detector in self._detectors:
                        for item in detector.scan_line(
                            cell_text, file_path, line_no
                        ):
                            item.column = col_idx
                            item.cell = self._cell_name(col_idx, line_no)
                            findings.append(item)
        return findings

    def _scan_csv_pandas(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        try:
            chunks = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                chunksize=5000,
                encoding=self.encoding,
            )
        except UnicodeDecodeError:
            chunks = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                chunksize=5000,
                encoding=self.fallback_encoding,
            )
        line_no = 0
        for chunk in chunks:
            for _, row in chunk.iterrows():
                line_no += 1
                if on_line:
                    on_line(line_no)
                for col_idx, value in enumerate(row.tolist()):
                    cell_text = str(value)
                    for detector in self._detectors:
                        for item in detector.scan_line(
                            cell_text, file_path, line_no
                        ):
                            item.column = col_idx
                            item.cell = self._cell_name(col_idx, line_no)
                            findings.append(item)
        return findings

    def scan_excel_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
    ) -> list[Finding]:
        if openpyxl is None:
            raise RuntimeError("openpyxl не установлен — нужен для Excel")
        findings: list[Finding] = []
        file_path = str(path)
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        line_no = 0
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                line_no += 1
                if on_line:
                    on_line(line_no)
                for col_idx, value in enumerate(row):
                    if value is None:
                        continue
                    cell_text = str(value)
                    for detector in self._detectors:
                        for item in detector.scan_line(
                            cell_text, file_path, line_no
                        ):
                            item.column = col_idx
                            item.cell = f"{sheet.title}!{self._cell_name(col_idx, line_no)}"
                            findings.append(item)
        workbook.close()
        return findings

    def scan_file(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
    ) -> list[Finding]:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".log", ".json"}:
            return self.scan_text_file(path, on_line)
        if suffix == ".csv":
            return self.scan_csv_file(path, on_line)
        if suffix in {".xlsx", ".xlsm"}:
            return self.scan_excel_file(path, on_line)
        if suffix == ".xls" and pd is not None:
            return self._scan_legacy_xls(path, on_line)
        return self.scan_text_file(path, on_line)

    def _scan_legacy_xls(
        self,
        path: Path,
        on_line: Callable[[int], None] | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        file_path = str(path)
        frame = pd.read_excel(path, dtype=str, header=None)
        for line_no, row in enumerate(frame.itertuples(index=False), start=1):
            if on_line:
                on_line(line_no)
            for col_idx, value in enumerate(row):
                cell_text = str(value)
                for detector in self._detectors:
                    for item in detector.scan_line(cell_text, file_path, line_no):
                        item.column = col_idx
                        item.cell = self._cell_name(col_idx, line_no)
                        findings.append(item)
        return findings

    @staticmethod
    def _cell_name(col: int, row: int) -> str:
        name = ""
        col_num = col + 1
        while col_num:
            col_num, rem = divmod(col_num - 1, 26)
            name = chr(65 + rem) + name
        return f"{name}{row}"
