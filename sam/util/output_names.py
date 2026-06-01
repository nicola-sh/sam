from __future__ import annotations

from pathlib import Path

from sam.util.dates import AtmLogDateFormats


def normalize_atm_id(atm_id: str) -> str:
    text = atm_id.strip().upper()
    if not text:
        raise ValueError("Укажите номер АТМ")
    return text


def target_dir(download_root: Path, atm_id: str) -> Path:
    return download_root / normalize_atm_id(atm_id)


def output_file_path(
    download_root: Path,
    atm_id: str,
    formats: AtmLogDateFormats,
    log_kind: str,
) -> Path:
    """Имя как в скрипте: {ATM}_{MMDD}_{KIND}.txt"""
    atm = normalize_atm_id(atm_id)
    suffix = log_kind.strip().upper()
    name = f"{atm}_{formats.date_exit_file}_{suffix}.txt"
    return target_dir(download_root, atm) / name
