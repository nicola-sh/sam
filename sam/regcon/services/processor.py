from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable

from sam.regcon.maskers.masker import apply_replacements, findings_to_replacements
from sam.regcon.models import Finding
from sam.regcon.services.scanner import FileScanner
from sam.regcon.util.cancel import CancelCallback, check_cancelled
from sam.regcon.util.job_progress import JobProgress

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None  # type: ignore

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


JSON_LIKE = re.compile(r"(\{.*\}|\[.*\])")


class FileProcessor(FileScanner):
    def output_path(self, source: Path, output_dir: Path) -> Path:
        rc = self.config.get("regcon", {})
        suffix = rc.get("output_suffix", "_masked")
        name = source.stem + suffix + source.suffix
        return output_dir / name

    def mask_text_file(
        self,
        path: Path,
        findings_by_line: dict[int, list[Finding]],
        output_dir: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> Path:
        target = self.output_path(path, output_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        every = int(self.config.get("regcon", {}).get("progress_every_lines", 5000))
        with self._open_text(path) as src, target.open(
            "w", encoding=self.encoding, newline=""
        ) as dst:
            for line_no, line in enumerate(src, start=1):
                self._tick(line, cancel, progress)
                if on_line and (line_no == 1 or line_no % every == 0):
                    on_line(line_no)
                raw = line.rstrip("\n\r")
                newline = line[len(raw) :]
                items = findings_by_line.get(line_no, [])
                if items:
                    replacements = findings_to_replacements(raw, items, self.config)
                    raw = apply_replacements(raw, replacements)
                dst.write(raw + newline)
        return target

    def mask_csv_file(
        self,
        path: Path,
        findings_by_line: dict[int, list[Finding]],
        output_dir: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> Path:
        if pd is not None:
            return self._mask_csv_pandas(
                path, findings_by_line, output_dir, on_line, cancel, progress
            )
        return self._mask_csv_stdlib(
            path, findings_by_line, output_dir, on_line, cancel, progress
        )

    def _mask_csv_stdlib(
        self,
        path: Path,
        findings_by_line: dict[int, list[Finding]],
        output_dir: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> Path:
        target = self.output_path(path, output_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._open_text(path) as src, target.open(
            "w", encoding=self.encoding, newline=""
        ) as dst:
            reader = csv.reader(src)
            writer = csv.writer(dst)
            for line_no, row in enumerate(reader, start=1):
                self._tick(",".join(row) + "\n", cancel, progress)
                if on_line:
                    on_line(line_no)
                items = findings_by_line.get(line_no, [])
                by_col: dict[int, list[Finding]] = defaultdict(list)
                for item in items:
                    by_col[item.column].append(item)
                new_row = []
                for col_idx, cell in enumerate(row):
                    cell_text = str(cell)
                    col_items = by_col.get(col_idx, [])
                    if col_items:
                        replacements = findings_to_replacements(
                            cell_text, col_items, self.config
                        )
                        cell_text = apply_replacements(cell_text, replacements)
                    new_row.append(cell_text)
                writer.writerow(new_row)
        return target

    def _mask_csv_pandas(
        self,
        path: Path,
        findings_by_line: dict[int, list[Finding]],
        output_dir: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> Path:
        target = self.output_path(path, output_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            frame = pd.read_csv(
                path, dtype=str, keep_default_na=False, encoding=self.encoding
            )
        except UnicodeDecodeError:
            frame = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                encoding=self.fallback_encoding,
            )
        for line_no in range(1, len(frame) + 1):
            self._tick("\n", cancel, progress)
            if on_line:
                on_line(line_no)
            items = findings_by_line.get(line_no, [])
            by_col: dict[int, list[Finding]] = defaultdict(list)
            for item in items:
                by_col[item.column].append(item)
            for col_idx in by_col:
                if col_idx >= len(frame.columns):
                    continue
                col_name = frame.columns[col_idx]
                value = str(frame.at[line_no - 1, col_name])
                replacements = findings_to_replacements(
                    value, by_col[col_idx], self.config
                )
                frame.at[line_no - 1, col_name] = apply_replacements(
                    value, replacements
                )
        frame.to_csv(target, index=False, encoding=self.encoding)
        return target

    def mask_excel_file(
        self,
        path: Path,
        findings_by_line: dict[int, list[Finding]],
        output_dir: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> Path:
        if openpyxl is None:
            raise RuntimeError("openpyxl не установлен")
        target = self.output_path(path, output_dir)
        if target.suffix.lower() != ".xlsx":
            target = target.with_suffix(".xlsx")
        target.parent.mkdir(parents=True, exist_ok=True)
        workbook = openpyxl.load_workbook(path)
        line_no = 0
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                line_no += 1
                self._tick("\n", cancel, progress)
                if on_line:
                    on_line(line_no)
                items = findings_by_line.get(line_no, [])
                by_col: dict[int, list[Finding]] = defaultdict(list)
                for item in items:
                    by_col[item.column].append(item)
                for cell in row:
                    col_items = by_col.get(cell.column - 1, [])
                    if not col_items or cell.value is None:
                        continue
                    value = str(cell.value)
                    replacements = findings_to_replacements(
                        value, col_items, self.config
                    )
                    cell.value = apply_replacements(value, replacements)
        workbook.save(target)
        return target

    def mask_file(
        self,
        path: Path,
        findings: list[Finding],
        output_dir: Path,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> Path:
        selected = [f for f in findings if f.selected]
        by_line: dict[int, list[Finding]] = defaultdict(list)
        for item in selected:
            by_line[item.line_no].append(item)
        suffix = path.suffix.lower()
        if suffix in {".txt", ".log", ".json"}:
            return self.mask_text_file(
                path, by_line, output_dir, on_line, cancel, progress
            )
        if suffix == ".csv":
            return self.mask_csv_file(
                path, by_line, output_dir, on_line, cancel, progress
            )
        if suffix in {".xlsx", ".xlsm", ".xls"}:
            return self.mask_excel_file(
                path, by_line, output_dir, on_line, cancel, progress
            )
        return self.mask_text_file(
            path, by_line, output_dir, on_line, cancel, progress
        )

    def format_json_in_text_file(
        self,
        path: Path,
        output_dir: Path,
        indent: int = 2,
        on_line: Callable[[int], None] | None = None,
        cancel: CancelCallback = None,
        progress: JobProgress | None = None,
    ) -> Path:
        target = output_dir / f"{path.stem}_jsonfmt{path.suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        every = int(self.config.get("regcon", {}).get("progress_every_lines", 5000))
        with self._open_text(path) as src, target.open(
            "w", encoding=self.encoding, newline=""
        ) as dst:
            for line_no, line in enumerate(src, start=1):
                self._tick(line, cancel, progress)
                if on_line and (line_no == 1 or line_no % every == 0):
                    on_line(line_no)
                raw = line.rstrip("\n\r")
                newline = line[len(raw) :]
                formatted = self._format_json_fragments(raw, indent)
                dst.write(formatted + newline)
        return target

    def _format_json_fragments(self, text: str, indent: int) -> str:
        def replacer(match: re.Match[str]) -> str:
            fragment = match.group(1)
            try:
                parsed = json.loads(fragment)
                return json.dumps(parsed, ensure_ascii=False, indent=indent)
            except json.JSONDecodeError:
                return fragment

        return JSON_LIKE.sub(replacer, text)
