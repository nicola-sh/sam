from __future__ import annotations

import sys
from pathlib import Path

PAN_PREFIX_FILE = "pan_prefix.yaml"
UI_LOG_FILE = "regcon_ui.log"
OUTPUT_SUBDIR = "regcon-output"


def app_data_dir() -> Path:
    """Каталог рядом с exe (или regcon_app_data при запуске из исходников)."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent.parent / "regcon_app_data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def pan_prefix_path() -> Path:
    return app_data_dir() / PAN_PREFIX_FILE


def ui_log_path() -> Path:
    return app_data_dir() / UI_LOG_FILE


def default_output_dir() -> Path:
    path = app_data_dir() / OUTPUT_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path
