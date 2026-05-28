from __future__ import annotations

from pathlib import Path
from typing import Callable

from regcon.config.settings import regcon_cfg
from regcon.formatters.excel_styler import style_workbook

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def csv_to_excel(
    csv_path: Path,
    output_dir: Path,
    config: dict,
    on_progress: Callable[[int], None] | None = None,
) -> Path:
    if pd is None:
        raise RuntimeError("pandas не установлен — нужен для CSV → Excel")
    rc = regcon_cfg(config)
    encoding = rc.get("encoding", "utf-8")
    fallback = rc.get("fallback_encoding", "cp1251")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{csv_path.stem}.xlsx"
    try:
        frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False, encoding=encoding)
    except UnicodeDecodeError:
        frame = pd.read_csv(
            csv_path, dtype=str, keep_default_na=False, encoding=fallback
        )
    if on_progress:
        on_progress(50)
    frame.to_excel(target, index=False, engine="openpyxl")
    if on_progress:
        on_progress(80)
    style_workbook(target, config.get("excel", {}))
    if on_progress:
        on_progress(100)
    return target
