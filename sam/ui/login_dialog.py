from __future__ import annotations

from sam.auth.session import SamUser
from sam.auth.users import UserStore

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


class LoginDialog(QDialog):
    def __init__(self, user_store: UserStore, parent=None) -> None:
        super().__init__(parent)
        self.user_store = user_store
        self.user: SamUser | None = None
        self.setWindowTitle("SAM — вход")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Вход в System Admin Management"))
        form = QFormLayout()
        self.login_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Логин:", self.login_edit)
        form.addRow("Пароль:", self.password_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _try_login(self) -> None:
        user = self.user_store.verify(
            self.login_edit.text(),
            self.password_edit.text(),
        )
        if user is None:
            QMessageBox.warning(self, "SAM", "Неверный логин или пароль.")
            return
        self.user = user
        self.accept()
