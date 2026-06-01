from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from sam.vault.store import SecretVault, VaultError

SECURE_CONFIG_KEY = "secure_config_v1"

_DEFAULT_HOST = {
    "id": "node-01",
    "host": "",
    "port": 22,
    "username": "",
    "password": "",
}

DEFAULT_SECURE: dict[str, Any] = {
    "clusters": [
        {
            "id": "fo",
            "name": "Front Office (FO)",
            "hosts": [
                {**_DEFAULT_HOST, "id": "fo-01"},
                {**_DEFAULT_HOST, "id": "fo-02"},
            ],
        },
        {
            "id": "bo",
            "name": "Back Office (BO)",
            "hosts": [
                {**_DEFAULT_HOST, "id": "bo-01"},
                {**_DEFAULT_HOST, "id": "bo-02"},
            ],
        },
    ],
    "servers": [
        {
            "id": "atm",
            "name": "ATM",
            "host": "",
            "port": 22,
            "username": "",
            "password": "",
        },
    ],
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
            "target_type": "server",
            "target_id": "atm",
            "log_layout": "daily",
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
        data = deepcopy(DEFAULT_SECURE)
    else:
        raw = vault.get(SECURE_CONFIG_KEY)
        data = _merge_secure(deepcopy(DEFAULT_SECURE), json.loads(raw))
    return migrate_secure_topology(data)


def save_secure_config(vault: SecretVault, data: dict[str, Any]) -> None:
    if not vault.is_unlocked:
        raise VaultError("Vault заблокирован")
    vault.set(SECURE_CONFIG_KEY, json.dumps(data, ensure_ascii=False))
    vault.save()


def _merge_secure(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = _merge_secure(base[key], value)
        else:
            base[key] = value
    return base


def migrate_secure_topology(secure: dict[str, Any]) -> dict[str, Any]:
    """Старый единый ssh → сервер atm, если clusters/servers пусты."""
    out = deepcopy(secure)
    ssh = out.get("ssh") or {}
    servers = list(out.get("servers") or [])
    if ssh.get("host") and not any(s.get("host") for s in servers if isinstance(s, dict)):
        atm = next((s for s in servers if isinstance(s, dict) and s.get("id") == "atm"), None)
        if atm is None:
            servers.append({"id": "atm", "name": "ATM", **{k: ssh.get(k, "") for k in (
                "host", "port", "username", "password", "key_filename"
            )}})
        else:
            for key in ("host", "port", "username", "password"):
                if ssh.get(key) and not atm.get(key):
                    atm[key] = ssh[key]
        out["servers"] = servers
    for ms in out.get("microservices") or []:
        if isinstance(ms, dict) and not ms.get("target_type"):
            ms["target_type"] = "server"
            ms["target_id"] = ms.get("target_id") or "atm"
    return out


def migrate_plain_config(public: dict[str, Any], secure: dict[str, Any]) -> dict[str, Any]:
    out = migrate_secure_topology(deepcopy(secure))
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
                "target_type": s.target_type,
                "target_id": s.target_id,
                "log_layout": s.log_layout,
                "service_dir": s.service_dir,
                "arch_subdir": s.arch_subdir,
                "main_subdir": s.main_subdir,
                "outputs": [
                    {
                        "id": o.id,
                        "arch_prefix": o.arch_prefix,
                        "main_name": o.main_name,
                        "main_only_today": o.main_only_today,
                        "arch_glob": o.arch_glob,
                    }
                    for o in s.outputs
                ],
            }
            for s in svcs
        ]
    return out


def build_runtime_config(public: dict[str, Any], secure: dict[str, Any]) -> dict[str, Any]:
    runtime = deepcopy(public)
    sec = migrate_secure_topology(secure)
    runtime["clusters"] = deepcopy(sec.get("clusters", []))
    runtime["servers"] = deepcopy(sec.get("servers", []))
    runtime["ssh"] = deepcopy(sec.get("ssh", {}))
    runtime["microservices"] = deepcopy(sec.get("microservices", []))
    runtime["upload"] = deepcopy(sec.get("upload", {}))
    return runtime


def strip_sensitive_from_public(public: dict[str, Any]) -> dict[str, Any]:
    safe = deepcopy(public)
    for key in ("ssh", "upload", "microservices", "atm_ddc", "clusters", "servers"):
        safe.pop(key, None)
    return safe
