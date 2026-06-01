from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from sam.util.app_paths import bundled_config_path, user_config_path

DEFAULT_CONFIG: dict[str, Any] = {
    "sam": {
        "window_title": "SAM — выгрузка логов",
        "last_export_dir": "",
        "ssh_timeout_sec": 30,
        "command_timeout_sec": 3600,
    },
    "vault": {
        "path": "vault.enc",
    },
    "ssh": {
        "host": "10.11.44.10",
        "port": 22,
        "username": "",
        "password": "",
        "password_secret": "",
        "key_filename": "",
        "look_for_keys": True,
        "allow_agent": True,
    },
    "microservices": [
        {
            "id": "atm-ddc",
            "name": "ATM DDC Service",
            "service_dir": "/srv_mproc/mproc/services/atm-ddc-service",
            "arch_subdir": "/log_arch",
            "main_subdir": "/log",
            "outputs": [
                {"id": "DDC", "arch_prefix": "atm-ddc", "main_name": "atm-ddc"},
                {
                    "id": "DDC5556",
                    "arch_prefix": "atm-ddc5556",
                    "main_name": "atm-ddc5556",
                },
            ],
        },
    ],
    "upload": {
        "enabled": False,
        "host": "10.11.44.10",
        "port": 22,
        "username": "",
        "password": "",
        "password_secret": "",
        "remote_dir": "/home/BELINVESTBANK/shirnin_nv",
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
    safe = deepcopy(cfg)
    for section in ("ssh", "upload"):
        block = safe.get(section)
        if isinstance(block, dict) and block.get("password_secret"):
            block["password"] = ""
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            safe,
            fh,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


def sam_cfg(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("sam", DEFAULT_CONFIG["sam"])
