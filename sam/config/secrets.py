from __future__ import annotations

from typing import Any

from sam.services.ssh_client import SshEndpoint
from sam.vault.store import SecretVault, VaultError


def resolve_password(
    section: dict[str, Any],
    vault: SecretVault | None,
    *,
    plain_key: str = "password",
    secret_key: str = "password_secret",
) -> str:
    ref = str(section.get(secret_key) or "").strip()
    if ref:
        if vault is None or not vault.is_unlocked:
            raise VaultError(
                f"Нужен разблокированный vault для секрета «{ref}» "
                f"(поле {secret_key})"
            )
        return vault.get(ref)
    return str(section.get(plain_key) or "")


def resolve_ssh_endpoint(
    section: dict[str, Any],
    vault: SecretVault | None,
    *,
    timeout_sec: float = 30.0,
) -> SshEndpoint:
    data = dict(section)
    data["password"] = resolve_password(data, vault)
    return SshEndpoint.from_mapping(data, timeout_sec=timeout_sec)
