from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from sam.vault.store import SecretVault, VaultError

SECURE_CONFIG_KEY = "secure_config_v1"

DEFAULT_SECURE: dict[str, Any] = {
    "ssh": {
        "host": "",
        "port": 22,
        "username": "",
        "password": "",
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
        "host": "",
        "port": 22,
        "username": "",
        "password": "",
        "remote_dir": "",
    },
}


def load_secure_config(vault: SecretVault) -> dict[str, Any]:
    if not vault.is_unlocked:
        raise VaultError("Vault заблокирован")
    if SECURE_CONFIG_KEY not in vault.list_names():
        return deepcopy(DEFAULT_SECURE)
    raw = vault.get(SECURE_CONFIG_KEY)
    data = json.loads(raw)
    return _merge_secure(deepcopy(DEFAULT_SECURE), data)


def save_secure_config(vault: SecretVault, data: dict[str, Any]) -> None:
    if not vault.is_unlocked:
        raise VaultError("Vault заблокирован")
    vault.set(SECURE_CONFIG_KEY, json.dumps(data, ensure_ascii=False))
    vault.save()


def _merge_secure(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            base[key] = _merge_secure(base[key], value)
        else:
            base[key] = value
    return base


def migrate_plain_config(public: dict[str, Any], secure: dict[str, Any]) -> dict[str, Any]:
    """Переносит открытые ssh/microservices/upload из config.yaml в secure blob."""
    out = deepcopy(secure)
    for section in ("ssh", "upload"):
        plain = public.get(section)
        if isinstance(plain, dict) and plain.get("host"):
            out[section] = {**out.get(section, {}), **plain}
    if public.get("microservices"):
        out["microservices"] = public["microservices"]
    if public.get("atm_ddc"):
        from sam.models.microservice import parse_microservices

        svcs = parse_microservices(public)
        out["microservices"] = [
            {
                "id": s.id,
                "name": s.name,
                "service_dir": s.service_dir,
                "arch_subdir": s.arch_subdir,
                "main_subdir": s.main_subdir,
                "outputs": [
                    {
                        "id": o.id,
                        "arch_prefix": o.arch_prefix,
                        "main_name": o.main_name,
                        "main_only_today": o.main_only_today,
                    }
                    for o in s.outputs
                ],
            }
            for s in svcs
        ]
    return out


def build_runtime_config(public: dict[str, Any], secure: dict[str, Any]) -> dict[str, Any]:
    runtime = deepcopy(public)
    runtime["ssh"] = deepcopy(secure.get("ssh", {}))
    runtime["microservices"] = deepcopy(secure.get("microservices", []))
    runtime["upload"] = deepcopy(secure.get("upload", {}))
    return runtime


def strip_sensitive_from_public(public: dict[str, Any]) -> dict[str, Any]:
    safe = deepcopy(public)
    for key in ("ssh", "upload", "microservices", "atm_ddc"):
        safe.pop(key, None)
    return safe
