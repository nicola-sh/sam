from __future__ import annotations

from pathlib import Path

from sam.util.app_paths import app_data_dir as sam_app_data_dir

PAN_PREFIX_FILE = "pan_prefix.yaml"
UI_LOG_FILE = "regcon_ui.log"
OUTPUT_SUBDIR = "output"
USER_CONFIG_FILE = "regcon.yaml"


def app_data_dir() -> Path:
    """Данные RegCon внутри каталога SAM: sam_app_data/regcon/."""
    base = sam_app_data_dir() / "regcon"
    base.mkdir(parents=True, exist_ok=True)
    return base


def pan_prefix_path() -> Path:
    return app_data_dir() / PAN_PREFIX_FILE


def ui_log_path() -> Path:
    return app_data_dir() / UI_LOG_FILE


def user_config_path() -> Path:
    return app_data_dir() / USER_CONFIG_FILE


def default_output_dir() -> Path:
    path = app_data_dir() / OUTPUT_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config.yaml"
