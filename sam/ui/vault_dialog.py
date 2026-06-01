from __future__ import annotations

from sam.vault.session import VaultSession
from sam.vault.store import VaultError

try:
    from PyQt6.QtWidgets import (
        QCheckBox,
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
        QCheckBox,
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


class VaultUnlockDialog(QDialog):
    def __init__(self, session: VaultSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("SAM — хранилище секретов")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Пароли SSH хранятся в зашифрованном vault.\n"
                "Введите master-пароль для разблокировки."
            )
        )
        form = QFormLayout()
        self.pw_edit = QLineEdit()
        self.pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Master-пароль:", self.pw_edit)
        layout.addLayout(form)
        self.save_key = QCheckBox("Сохранить ключ на этом ПК (master.key)")
        layout.addWidget(self.save_key)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        try:
            self.session.unlock_with_password(
                self.pw_edit.text(),
                save_key_file=self.save_key.isChecked(),
            )
            self.accept()
        except VaultError as exc:
            QMessageBox.warning(self, "Vault", str(exc))


class VaultSecretsDialog(QDialog):
    def __init__(self, session: VaultSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Секреты (vault)")
        self.setMinimumWidth(480)
        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "Имена секретов указываются в config.yaml как password_secret.\n"
                "Пример: password_secret: ssh_password"
            )
        )
        form = QFormLayout()
        self.name_edit = QLineEdit("ssh_password")
        self.value_edit = QLineEdit()
        self.value_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Имя:", self.name_edit)
        form.addRow("Значение:", self.value_edit)
        root.addLayout(form)
        row = QHBoxLayout()
        btn_save = QPushButton("Сохранить секрет")
        btn_save.clicked.connect(self._save_secret)
        row.addWidget(btn_save)
        row.addStretch()
        root.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        close.accepted.connect(self.accept)
        root.addWidget(close)

    def _save_secret(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Vault", "Укажите имя секрета")
            return
        if not self.session.is_unlocked:
            QMessageBox.warning(self, "Vault", "Сначала разблокируйте vault")
            return
        self.session.vault.set(name, self.value_edit.text())
        self.session.save_vault()
        self.value_edit.clear()
        QMessageBox.information(self, "Vault", f"Секрет «{name}» сохранён")
