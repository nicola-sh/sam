from __future__ import annotations

import re
from pathlib import Path

from sam.util.dates import AtmLogDateFormats

_UNSAFE = re.compile(r"[^\w.\-]+", re.ASCII)


def safe_label(text: str, *, max_len: int = 40) -> str:
    cleaned = _UNSAFE.sub("_", text.strip())
    return (cleaned or "log")[:max_len]


def export_subdir(
    download_root: Path,
    service_id: str,
    label: str,
) -> Path:
    return download_root / safe_label(service_id) / safe_label(label)


def output_file_path(
    download_root: Path,
    service_id: str,
    label: str,
    formats: AtmLogDateFormats,
    output_id: str,
    *,
    grep_value: str | None,
) -> Path:
    """
    Имя файла:
    - с grep: {label}_{MMDD}_{OUTPUT}.txt
    - без grep: {service}_{MMDD}_{OUTPUT}_full.txt
    """
    out_dir = export_subdir(download_root, service_id, label)
    suffix = safe_label(output_id).upper()
    if grep_value:
        base = f"{safe_label(label)}_{formats.date_exit_file}_{suffix}.txt"
    else:
        base = (
            f"{safe_label(service_id)}_{formats.date_exit_file}_{suffix}_full.txt"
        )
    return out_dir / base
