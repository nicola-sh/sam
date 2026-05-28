from __future__ import annotations

import csv
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None  # type: ignore

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def count_file_lines(path: Path, encoding: str = "utf-8", fallback: str = "cp1251") -> int:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".log", ".json"}:
        return _count_text_lines(path, encoding, fallback)
    if suffix == ".csv":
        return _count_csv_lines(path, encoding, fallback)
    if suffix in {".xlsx", ".xlsm"}:
        return _count_xlsx_rows(path)
    if suffix == ".xls" and pd is not None:
        return len(pd.read_excel(path, header=None, dtype=str))
    return _count_text_lines(path, encoding, fallback)


def count_files_lines(
    paths: list[Path], encoding: str = "utf-8", fallback: str = "cp1251"
) -> int:
    return sum(count_file_lines(p, encoding, fallback) for p in paths)


def _count_text_lines(path: Path, encoding: str, fallback: str) -> int:
    for enc in (encoding, fallback):
        try:
            count = 0
            with path.open(encoding=enc, errors="replace") as handle:
                for _ in handle:
                    count += 1
            return max(count, 1)
        except OSError:
            continue
    return 1


def _count_csv_lines(path: Path, encoding: str, fallback: str) -> int:
    for enc in (encoding, fallback):
        try:
            count = 0
            with path.open(encoding=enc, errors="replace", newline="") as handle:
                for _ in csv.reader(handle):
                    count += 1
            return max(count, 1)
        except OSError:
            continue
    return 1


def _count_xlsx_rows(path: Path) -> int:
    if openpyxl is None:
        return 1
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        total = 0
        for sheet in workbook.worksheets:
            total += sheet.max_row or 0
        return max(total, 1)
    finally:
        workbook.close()
