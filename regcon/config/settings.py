from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "regcon": {
        "output_suffix": "_masked",
        "encoding": "utf-8",
        "fallback_encoding": "cp1251",
        "audit_log": "regcon_actions.log",
        "progress_every_lines": 5000,
        "progress_heartbeat_sec": 5.0,
        "max_table_rows": 5000,
        "context_radius": 30,
    },
    "pan": {
        "enabled": True,
        "use_luhn": True,
        "mask_keep_first": 6,
        "mask_keep_last": 4,
        "use_grouped_scan": True,
        "scan_embedded_digits": True,
        "context_radius": 30,
        "regex_list": [
            r"9112\s?39[0-9]{2}\s?[0-9]{4}\s?[0-9]{4}",
        ],
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


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config.yaml"
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, loaded)
    return cfg


def regcon_cfg(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("regcon", DEFAULT_CONFIG["regcon"])
