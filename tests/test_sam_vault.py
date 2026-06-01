from pathlib import Path

import pytest

from sam.vault.store import SecretVault, VaultError


def test_vault_roundtrip(tmp_path: Path):
    path = tmp_path / "vault.enc"
    v = SecretVault(path)
    v.unlock_with_password("test-master")
    v.set("ssh_password", "s3cret")
    v.save()
    v.lock()

    v2 = SecretVault(path)
    v2.unlock_with_password("test-master")
    assert v2.get("ssh_password") == "s3cret"


def test_vault_wrong_password(tmp_path: Path):
    path = tmp_path / "vault.enc"
    v = SecretVault(path)
    v.unlock_with_password("one")
    v.set("x", "1")
    v.save()
    v.lock()
    v2 = SecretVault(path)
    with pytest.raises(VaultError):
        v2.unlock_with_password("two")
