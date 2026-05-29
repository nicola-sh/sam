from __future__ import annotations

import os
import sys
from pathlib import Path

PAN_PREFIX_FILE = "pan_prefix.yaml"
UI_LOG_FILE = "regcon_ui.log"
OUTPUT_SUBDIR = "regcon-output"
USER_CONFIG_FILE = "config.yaml"


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".regcon_write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _windows_user_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "RegCon"
    return Path.home() / "AppData" / "Local" / "RegCon"


def app_data_dir() -> Path:
    """
    Каталог данных RegCon.
    Frozen: рядом с exe, если каталог доступен для записи;
    иначе %LOCALAPPDATA%\\RegCon (Windows) или ~/.regcon.
    Dev: regcon_app_data в корне репозитория.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if _is_writable_dir(exe_dir):
            base = exe_dir
        elif sys.platform == "win32":
            base = _windows_user_data_dir()
        else:
            base = Path.home() / ".regcon"
    else:
        base = Path(__file__).resolve().parent.parent.parent / "regcon_app_data"
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
    """config.yaml внутри пакета (defaults при первом запуске)."""
    return Path(__file__).resolve().parent.parent / "config.yaml"
