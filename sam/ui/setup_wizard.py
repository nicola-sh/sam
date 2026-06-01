from __future__ import annotations

from sam.auth.users import UserStore
from sam.vault.session import VaultSession

try:
    from PyQt6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QVBoxLayout,
    )
except ImportError:  # pragma: no cover
    from PyQt5.QtWidgets import (  # type: ignore
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QVBoxLayout,
    )


class FirstSetupDialog(QDialog):
    """Первый запуск: master vault + администратор SAM."""

    def __init__(self, user_store: UserStore, vault_session: VaultSession, parent=None) -> None:
        super().__init__(parent)
        self.user_store = user_store
        self.vault_session = vault_session
        self.setWindowTitle("SAM — первоначальная настройка")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Создайте master-пароль vault (шифрование IP, SSH, паролей)\n"
                "и учётную запись администратора SAM."
            )
        )
        form = QFormLayout()
        self.master_edit = QLineEdit()
        self.master_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.master_confirm = QLineEdit()
        self.master_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_edit = QLineEdit("admin")
        self.name_edit = QLineEdit("Администратор")
        self.user_pass = QLineEdit()
        self.user_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Master vault:", self.master_edit)
        form.addRow("Повтор vault:", self.master_confirm)
        form.addRow("Логин admin:", self.login_edit)
        form.addRow("Имя:", self.name_edit)
        form.addRow("Пароль admin:", self.user_pass)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._finish)
        layout.addWidget(buttons)

    def _finish(self) -> None:
        if self.master_edit.text() != self.master_confirm.text():
            QMessageBox.warning(self, "Настройка", "Master-пароли не совпадают.")
            return
        if len(self.master_edit.text()) < 8:
            QMessageBox.warning(self, "Настройка", "Master-пароль не короче 8 символов.")
            return
        if len(self.user_pass.text()) < 6:
            QMessageBox.warning(self, "Настройка", "Пароль пользователя не короче 6 символов.")
            return
        try:
            self.vault_session.unlock_with_password(self.master_edit.text())
            self.vault_session.save_vault()
            self.user_store.create_user(
                self.login_edit.text(),
                self.user_pass.text(),
                display_name=self.name_edit.text(),
                role="admin",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Настройка", str(exc))
            return
        self.accept()
