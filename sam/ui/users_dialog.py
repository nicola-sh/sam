from __future__ import annotations

from sam.auth.users import ROLES, UserStore
from sam.audit.audit_log import AuditLogger

try:
    from PyQt6.QtWidgets import (
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )
except ImportError:  # pragma: no cover
    from PyQt5.QtWidgets import (  # type: ignore
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )


class UsersDialog(QDialog):
    def __init__(
        self,
        store: UserStore,
        audit: AuditLogger,
        admin_login: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.audit = audit
        self.admin_login = admin_login
        self.setWindowTitle("Пользователи SAM")
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Учётные записи (пароли — только хэш bcrypt)."))
        form = QFormLayout()
        self.login_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.role_combo = QComboBox()
        self.role_combo.addItems(sorted(ROLES))
        form.addRow("Логин:", self.login_edit)
        form.addRow("Имя:", self.name_edit)
        form.addRow("Пароль:", self.password_edit)
        form.addRow("Роль:", self.role_combo)
        root.addLayout(form)
        btn_add = QPushButton("Создать пользователя")
        btn_add.clicked.connect(self._create)
        root.addWidget(btn_add)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        root.addWidget(close)

    def _create(self) -> None:
        try:
            rec = self.store.create_user(
                self.login_edit.text(),
                self.password_edit.text(),
                display_name=self.name_edit.text(),
                role=self.role_combo.currentText(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Пользователи", str(exc))
            self.audit.record(
                "user.create",
                user=self.admin_login,
                status="error",
                message=str(exc),
            )
            return
        self.audit.record(
            "user.create",
            user=self.admin_login,
            status="ok",
            target_login=rec.login,
            target_role=rec.role,
        )
        QMessageBox.information(self, "Пользователи", f"Создан: {rec.login}")
        self.login_edit.clear()
        self.password_edit.clear()
