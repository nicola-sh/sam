from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from sam.util.app_paths import bundled_config_path, user_config_path

# Публичный конфиг — без IP, паролей и путей серверов (всё в vault).
DEFAULT_CONFIG: dict[str, Any] = {
    "sam": {
        "window_title": "SAM — выгрузка логов",
        "last_export_dir": "",
        "ssh_timeout_sec": 30,
        "command_timeout_sec": 3600,
        "audit_dir": "audit",
        "logs_dir": "logs",
        "session_timeout_min": 60,
    },
    "vault": {
        "path": "vault.enc",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    if path is not None:
        sources = [path]
    else:
        sources = []
        bundled = bundled_config_path()
        if bundled.is_file():
            sources.append(bundled)
        user = user_config_path()
        if user.is_file() and user not in sources:
            sources.append(user)
    for src in sources:
        if src.exists():
            with src.open(encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
            cfg = _deep_merge(cfg, loaded)
    return cfg


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    if path is None:
        path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            cfg,
            fh,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def sam_cfg(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("sam", DEFAULT_CONFIG["sam"])
