from __future__ import annotations

from copy import deepcopy
from typing import Any

from sam.config.settings import load_config, save_config, sam_cfg
from sam.util.app_paths import app_data_dir, user_config_path
from sam.vault.secure_config import (
    build_runtime_config,
    load_secure_config,
    migrate_plain_config,
    save_secure_config,
    strip_sensitive_from_public,
)
from sam.vault.store import SecretVault


def load_runtime_config(vault: SecretVault) -> dict[str, Any]:
    public = load_config()
    secure = load_secure_config(vault)
    if _has_plain_secrets(public):
        secure = migrate_plain_config(public, secure)
        save_secure_config(vault, secure)
        public = strip_sensitive_from_public(public)
        save_config(public, user_config_path())
    return build_runtime_config(public, secure)


def _has_plain_secrets(public: dict[str, Any]) -> bool:
    ssh = public.get("ssh") or {}
    if ssh.get("host") or ssh.get("password"):
        return True
    if public.get("microservices") or public.get("atm_ddc"):
        return True
    upload = public.get("upload") or {}
    if upload.get("host") or upload.get("password"):
        return True
    return False


def audit_dir_from_config(config: dict[str, Any]) -> Path:
    from pathlib import Path

    sam = sam_cfg(config)
    rel = str(sam.get("audit_dir") or "audit")
    p = Path(rel)
    if p.is_absolute():
        return p
    return app_data_dir() / p


def logs_dir_from_config(config: dict[str, Any]) -> Path:
    from pathlib import Path

    sam = sam_cfg(config)
    rel = str(sam.get("logs_dir") or "logs")
    p = Path(rel)
    if p.is_absolute():
        return p
    return app_data_dir() / p
