from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from regcon.util.app_paths import bundled_config_path, user_config_path

DEFAULT_CONFIG: dict[str, Any] = {
    "regcon": {
        "output_suffix": "_masked",
        "encoding": "utf-8",
        "fallback_encoding": "cp1251",
        "audit_log": "regcon_actions.log",
        "progress_every_lines": 5000,
        "progress_heartbeat_sec": 5.0,
        "progress_batch_bytes": 65536,
        "read_buffer_bytes": 1048576,
        "max_table_rows": 5000,
        "max_findings": 200000,
        "context_radius": 30,
        "last_output_dir": "",
        "mask_sensitive_ui_log": False,
    },
    "pan": {
        "enabled": True,
        "use_luhn": True,
        "mask_keep_first": 6,
        "mask_keep_last": 4,
        "prefix_digits": 8,
        "prefix_line_filter": True,
        "context_radius": 30,
    },
    "ip": {
        "enabled": True,
        "mask_mode": "last_two",
        "whitelist": ["127.0.0.1", "::1"],
    },
    "passwords": {
        "enabled": True,
        "patterns": [
            r"(?i)(password|pwd|passwd|secret|token)\s*[=:]\s*(\S+)",
        ],
    },
    "excel": {
        "auto_filter": True,
        "freeze_header": True,
        "max_column_width": 60,
    },
    "json": {
        "enabled": True,
        "indent": 2,
        "format_on_csv_export": True,
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


def default_config_path() -> Path:
    """Путь для сохранения настроек пользователя."""
    return user_config_path()


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


def regcon_cfg(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("regcon", DEFAULT_CONFIG["regcon"])
