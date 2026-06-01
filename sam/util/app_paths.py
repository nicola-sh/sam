from __future__ import annotations

import os
import sys
from pathlib import Path

USER_CONFIG_FILE = "config.yaml"
UI_LOG_FILE = "sam_ui.log"
EXPORT_SUBDIR = "sam-exports"
USERS_FILE = "users.json"


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".sam_write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _windows_user_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "SAM"
    return Path.home() / "AppData" / "Local" / "SAM"


def app_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if _is_writable_dir(exe_dir):
            base = exe_dir
        elif sys.platform == "win32":
            base = _windows_user_data_dir()
        else:
            base = Path.home() / ".sam"
    else:
        base = Path(__file__).resolve().parent.parent.parent / "sam_app_data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def user_config_path() -> Path:
    return app_data_dir() / USER_CONFIG_FILE


def users_db_path() -> Path:
    return app_data_dir() / USERS_FILE


def default_export_dir() -> Path:
    path = app_data_dir() / EXPORT_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config.yaml"
