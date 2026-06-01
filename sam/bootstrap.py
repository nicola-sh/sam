from __future__ import annotations

import argparse
import getpass
import sys

from sam.auth.users import UserStore
from sam.config.settings import load_config
from sam.util.app_paths import users_db_path
from sam.vault.secure_config import save_secure_config
from sam.vault.session import VaultSession
from sam.vault.store import SecretVault, vault_path_from_config
from sam.util.app_paths import app_data_dir


def create_admin_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Создать администратора SAM")
    parser.add_argument("login", help="Логин")
    parser.add_argument("--display-name", default="", help="Отображаемое имя")
    parser.add_argument("--init-vault", action="store_true", help="Создать vault и secure_config")
    args = parser.parse_args(argv)

    password = getpass.getpass("Пароль SAM: ")
    if len(password) < 6:
        print("Пароль не короче 6 символов", file=sys.stderr)
        return 1

    store = UserStore(users_db_path())
    try:
        store.create_user(
            args.login,
            password,
            display_name=args.display_name or args.login,
            role="admin",
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Пользователь «{args.login}» создан.")

    if args.init_vault:
        master = getpass.getpass("Master-пароль vault: ")
        public = load_config()
        path = vault_path_from_config(public, app_data_dir())
        vault = SecretVault(path)
        vault.unlock_with_password(master)
        from sam.vault.secure_config import DEFAULT_SECURE

        save_secure_config(vault, DEFAULT_SECURE)
        print(f"Vault создан: {path}")

    return 0
