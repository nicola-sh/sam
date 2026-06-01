from __future__ import annotations

from pathlib import Path
from typing import Any

from sam.util.app_paths import app_data_dir
from sam.vault.store import (
    SecretVault,
    VaultError,
    master_key_path,
    try_load_master_key_from_env,
    vault_path_from_config,
    write_master_key_file,
)


class VaultSession:
    """Singleton-подобная сессия vault на время работы приложения."""

    _instance: VaultSession | None = None

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._app_data = app_data_dir()
        self._vault_path = vault_path_from_config(config, self._app_data)
        self._vault = SecretVault(self._vault_path)
        self._unlocked = False

    @classmethod
    def get(cls, config: dict[str, Any]) -> VaultSession:
        if cls._instance is None:
            cls._instance = VaultSession(config)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    @property
    def vault(self) -> SecretVault:
        return self._vault

    @property
    def path(self) -> Path:
        return self._vault_path

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked and self._vault.is_unlocked

    def needs_unlock(self) -> bool:
        if not self._config_needs_vault():
            return False
        return not self.is_unlocked

    def _config_needs_vault(self) -> bool:
        for section in ("ssh", "upload"):
            ref = str(self._config.get(section, {}).get("password_secret") or "")
            if ref:
                return True
        return False

    def try_auto_unlock(self) -> bool:
        if self.is_unlocked:
            return True
        env_key = try_load_master_key_from_env()
        if env_key:
            try:
                self._unlock_with_raw_key(env_key)
                return True
            except VaultError:
                pass
        mk = master_key_path(self._app_data)
        if mk.is_file():
            try:
                self._vault.unlock_with_key_file(mk)
                self._unlocked = True
                return True
            except VaultError:
                pass
        if not self._vault.exists and not self._config_needs_vault():
            self._vault.unlock_with_password("")
            self._unlocked = True
            return True
        return False

    def unlock_with_password(self, password: str, *, save_key_file: bool = False) -> None:
        self._vault.unlock_with_password(password)
        self._unlocked = True
        if save_key_file:
            write_master_key_file(master_key_path(self._app_data), self._vault.export_master_key())

    def _unlock_with_raw_key(self, key: bytes) -> None:
        self._vault.unlock_with_raw_key(key)
        self._unlocked = True

    def save_vault(self) -> None:
        self._vault.save()
