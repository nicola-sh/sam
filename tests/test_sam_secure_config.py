from sam.vault.secure_config import build_runtime_config, migrate_plain_config
from sam.vault.store import SecretVault


def test_migrate_plain_to_secure(tmp_path):
    public = {
        "ssh": {"host": "10.0.0.1", "username": "u", "password": "p"},
        "microservices": [],
    }
    secure = migrate_plain_config(public, {"ssh": {}, "microservices": [], "upload": {}})
    assert secure["ssh"]["host"] == "10.0.0.1"
    runtime = build_runtime_config({"sam": {}}, secure)
    assert runtime["ssh"]["password"] == "p"


def test_secure_roundtrip_in_vault(tmp_path):
    path = tmp_path / "vault.enc"
    v = SecretVault(path)
    v.unlock_with_password("master-password-long")
    from sam.vault.secure_config import load_secure_config, save_secure_config

    data = load_secure_config(v)
    data["ssh"]["host"] = "192.168.1.5"
    save_secure_config(v, data)
    v.lock()
    v2 = SecretVault(path)
    v2.unlock_with_password("master-password-long")
    loaded = load_secure_config(v2)
    assert loaded["ssh"]["host"] == "192.168.1.5"
