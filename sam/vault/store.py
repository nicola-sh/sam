from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT_VERSION = 1
KDF_ITERATIONS = 480_000


class VaultError(Exception):
    pass


class SecretVault:
    """Зашифрованное хранилище паролей SSH/FTP (AES-GCM, ключ из master-пароля или файла)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._secrets: dict[str, str] = {}
        self._key: bytes | None = None
        self._salt: bytes | None = None

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def lock(self) -> None:
        self._key = None
        self._secrets = {}

    def unlock_with_password(self, password: str) -> None:
        if not self.exists:
            self._salt = os.urandom(16)
            self._key = _derive_key(password, self._salt)
            self._secrets = {}
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("v") != VAULT_VERSION:
            raise VaultError("Неподдерживаемая версия vault")
        salt = base64.b64decode(payload["salt"])
        key = _derive_key(password, salt)
        try:
            secrets = _decrypt_blob(base64.b64decode(payload["blob"]), key)
        except Exception as exc:
            raise VaultError("Неверный master-пароль") from exc
        self._salt = salt
        self._key = key
        self._secrets = secrets

    def unlock_with_raw_key(self, key: bytes) -> None:
        if len(key) != 32:
            raise VaultError("Ключ должен быть 32 байта")
        if not self.exists:
            raise VaultError("Vault ещё не создан")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        salt = base64.b64decode(payload["salt"])
        secrets = _decrypt_blob(base64.b64decode(payload["blob"]), key)
        self._salt = salt
        self._key = key
        self._secrets = secrets

    def unlock_with_key_file(self, key_path: Path) -> None:
        raw = key_path.read_bytes().strip()
        try:
            key = base64.urlsafe_b64decode(raw + b"=="[: (4 - len(raw) % 4) % 4])
        except Exception as exc:
            raise VaultError("Некорректный master.key") from exc
        if len(key) != 32:
            raise VaultError("master.key должен содержать 32 байта (base64)")
        if not self.exists:
            raise VaultError("Vault ещё не создан — сначала задайте master-пароль")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        salt = base64.b64decode(payload["salt"])
        secrets = _decrypt_blob(base64.b64decode(payload["blob"]), key)
        self._salt = salt
        self._key = key
        self._secrets = secrets

    def get(self, name: str) -> str:
        if not self.is_unlocked:
            raise VaultError("Vault заблокирован")
        if name not in self._secrets:
            raise VaultError(f"Секрет «{name}» не найден")
        return self._secrets[name]

    def set(self, name: str, value: str) -> None:
        if not self.is_unlocked:
            raise VaultError("Vault заблокирован")
        self._secrets[name] = value

    def delete(self, name: str) -> None:
        if not self.is_unlocked:
            raise VaultError("Vault заблокирован")
        self._secrets.pop(name, None)

    def list_names(self) -> list[str]:
        return sorted(self._secrets)

    def save(self) -> None:
        if not self.is_unlocked or self._key is None or self._salt is None:
            raise VaultError("Vault заблокирован")
        blob = _encrypt_blob(self._secrets, self._key)
        payload = {
            "v": VAULT_VERSION,
            "salt": base64.b64encode(self._salt).decode("ascii"),
            "blob": base64.b64encode(blob).decode("ascii"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def export_master_key(self) -> bytes:
        if not self.is_unlocked or self._key is None:
            raise VaultError("Vault заблокирован")
        return self._key


def vault_path_from_config(config: dict[str, Any], app_data: Path) -> Path:
    rel = str(config.get("vault", {}).get("path") or "vault.enc")
    p = Path(rel)
    if p.is_absolute():
        return p
    return app_data / p


def master_key_path(app_data: Path) -> Path:
    return app_data / "master.key"


def write_master_key_file(path: Path, key: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base64.urlsafe_b64encode(key).decode("ascii"), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def try_load_master_key_from_env() -> bytes | None:
    raw = os.environ.get("SAM_MASTER_KEY", "").strip()
    if not raw:
        return None
    try:
        key = base64.urlsafe_b64decode(raw + "=="[: (4 - len(raw) % 4) % 4])
    except Exception:
        return None
    return key if len(key) == 32 else None


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _encrypt_blob(secrets: dict[str, str], key: bytes) -> bytes:
    aes = AESGCM(key)
    nonce = os.urandom(12)
    data = json.dumps(secrets, ensure_ascii=False).encode("utf-8")
    return nonce + aes.encrypt(nonce, data, None)


def _decrypt_blob(raw: bytes, key: bytes) -> dict[str, str]:
    if len(raw) < 13:
        raise VaultError("Повреждённый vault")
    nonce, ct = raw[:12], raw[12:]
    aes = AESGCM(key)
    data = aes.decrypt(nonce, ct, None)
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise VaultError("Некорректное содержимое vault")
    return {str(k): str(v) for k, v in parsed.items()}
