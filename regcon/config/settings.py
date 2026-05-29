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
        "progress_batch_bytes": 65536,
        "read_buffer_bytes": 1048576,
        "max_table_rows": 5000,
        "context_radius": 30,
    },
    "pan": {
        "enabled": True,
        "use_luhn": True,
        "mask_keep_first": 6,
        "mask_keep_last": 4,
        "prefix_digits": 8,
        "prefix_line_filter": True,
        "prefix_list": [],
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
    return Path(__file__).resolve().parent.parent / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)
    if path is None:
        path = default_config_path()
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, loaded)
    _migrate_prefix_file(cfg, path.parent)
    return cfg


def _migrate_prefix_file(cfg: dict[str, Any], base_dir: Path) -> None:
    """Один раз: импорт pan_prefixes.txt → prefix_list, если список пуст."""
    pan = cfg.setdefault("pan", {})
    if pan.get("prefix_list"):
        return
    legacy = pan.pop("prefix_file", None)
    if not legacy:
        legacy_path = base_dir / "config" / "pan_prefixes.txt"
    else:
        legacy_path = Path(legacy)
        if not legacy_path.is_absolute():
            legacy_path = base_dir / legacy_path
    if legacy_path.is_file():
        from regcon.config.pan_prefixes import load_prefixes_from_file

        imported = load_prefixes_from_file(legacy_path)
        if imported:
            pan["prefix_list"] = imported
            save_config(cfg, path if path.exists() else default_config_path())


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    if path is None:
        path = default_config_path()
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
