from __future__ import annotations

import argparse
import logging
import sys

from sam.audit.app_log import setup_app_logging
from sam.audit.audit_log import AuditLogger
from sam.auth.session import SamSession
from sam.auth.users import UserStore
from sam.bootstrap import create_admin_cli
from sam.config.runtime import audit_dir_from_config, load_runtime_config, logs_dir_from_config
from sam.config.settings import load_config
from sam.ui.login_dialog import LoginDialog
from sam.ui.main_window import MainWindow, run_qt_app
from sam.ui.setup_wizard import FirstSetupDialog
from sam.ui.vault_dialog import VaultUnlockDialog
from sam.util.app_paths import users_db_path
from sam.vault.session import VaultSession

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
except ImportError:  # pragma: no cover
    from PyQt5.QtWidgets import QApplication, QMessageBox  # type: ignore


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] == "users" and len(args) >= 3 and args[1] == "create-admin":
        return create_admin_cli(args[2:])
    if "--create-admin" in args:
        idx = args.index("--create-admin")
        rest = args[idx + 1 :]
        if not rest:
            print("Укажите логин: python -m sam --create-admin LOGIN", file=sys.stderr)
            return 1
        return create_admin_cli(rest)

    public = load_config()
    logger = setup_app_logging(logs_dir_from_config(public))
    audit = AuditLogger(audit_dir_from_config(public))
    audit.record("app.start", user="system", status="ok", message="SAM launch")
    logger.info("SAM application starting")

    VaultSession.reset()
    vault_session = VaultSession(public)

    app = QApplication(sys.argv)
    user_store = UserStore(users_db_path())

    if user_store.count() == 0:
        logger.info("First setup: no users")
        if not vault_session.try_auto_unlock() and not vault_session.vault.exists:
            dlg = FirstSetupDialog(user_store, vault_session)
            if dlg.exec() != dlg.DialogCode.Accepted:
                audit.record("app.exit", user="system", status="cancel", message="setup cancelled")
                return 1
        else:
            if not vault_session.is_unlocked:
                unlock = VaultUnlockDialog(vault_session)
                if unlock.exec() != unlock.DialogCode.Accepted:
                    return 1
            setup = FirstSetupDialog(user_store, vault_session)
            if setup.exec() != setup.DialogCode.Accepted:
                return 1
        audit.record("setup.complete", user="system", status="ok")

    if not vault_session.is_unlocked:
        if not vault_session.try_auto_unlock():
            unlock = VaultUnlockDialog(vault_session)
            if unlock.exec() != unlock.DialogCode.Accepted:
                audit.record("vault.unlock", user="system", status="denied")
                logger.warning("Vault unlock cancelled")
                return 1
    audit.record("vault.unlock", user="system", status="ok")
    logger.info("Vault unlocked")

    try:
        load_runtime_config(vault_session.vault)
    except Exception as exc:
        logger.exception("Failed to load runtime config")
        audit.record("config.load", user="system", status="error", message=str(exc))
        QMessageBox.critical(None, "SAM", str(exc))
        return 1

    login = LoginDialog(user_store)
    if login.exec() != login.DialogCode.Accepted or login.user is None:
        audit.record("auth.login", user="?", status="cancel")
        return 0

    session = SamSession()
    session.login(login.user)
    audit.record(
        "auth.login",
        user=login.user.login,
        status="ok",
        role=login.user.role,
    )
    logger.info("User logged in: %s", login.user.login)

    window = MainWindow(
        login.user,
        public,
        vault_session,
        audit,
        logger,
    )
    window.show()
    code = run_qt_app(app)
    logout_user = session.logout()
    if logout_user:
        audit.record("auth.logout", user=logout_user.login, status="ok")
    audit.record("app.exit", user=logout_user.login if logout_user else "system", status="ok")
    logger.info("SAM exit code %s", code)
    return code


if __name__ == "__main__":
    sys.exit(main())
