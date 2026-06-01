from __future__ import annotations

import json
from typing import Any

from sam.audit.audit_log import AuditLogger
from sam.config.runtime import load_runtime_config
from sam.util.masking import mask_ipv4
from sam.vault.secure_config import load_secure_config, save_secure_config
from sam.vault.session import VaultSession

try:
    from PyQt6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover
    from PyQt5.QtWidgets import (  # type: ignore
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )


class InfrastructureDialog(QDialog):
    """Редактор критичных данных (IP, пути, пароли) — только в vault."""

    def __init__(
        self,
        vault_session: VaultSession,
        audit: AuditLogger,
        user_login: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.vault_session = vault_session
        self.audit = audit
        self.user_login = user_login
        self.setWindowTitle("Подключения — серверы, микросервисы, пути к логам")
        self.resize(560, 480)
        self._secure = load_secure_config(vault_session.vault)

        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "Хосты, IP и пароли хранятся в vault. "
                f"SSH: {mask_ipv4(str(self._secure.get('ssh', {}).get('host', '')))}"
            )
        )
        tabs = QTabWidget()
        tabs.addTab(self._ssh_tab(), "Откуда скачивать (SSH)")
        tabs.addTab(self._microservices_tab(), "Микросервисы и пути")
        tabs.addTab(self._upload_tab(), "Куда загрузить копию")
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _ssh_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        ssh = self._secure.setdefault("ssh", {})
        self.ssh_host = QLineEdit(str(ssh.get("host", "")))
        self.ssh_port = QLineEdit(str(ssh.get("port", 22)))
        self.ssh_user = QLineEdit(str(ssh.get("username", "")))
        self.ssh_pass = QLineEdit(str(ssh.get("password", "")))
        self.ssh_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Host (IP):", self.ssh_host)
        form.addRow("Port:", self.ssh_port)
        form.addRow("User:", self.ssh_user)
        form.addRow("Password:", self.ssh_pass)
        return w

    def _upload_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        up = self._secure.setdefault("upload", {})
        self.up_enabled = QLineEdit("true" if up.get("enabled") else "false")
        self.up_host = QLineEdit(str(up.get("host", "")))
        self.up_user = QLineEdit(str(up.get("username", "")))
        self.up_pass = QLineEdit(str(up.get("password", "")))
        self.up_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.up_dir = QLineEdit(str(up.get("remote_dir", "")))
        form.addRow("enabled (true/false):", self.up_enabled)
        form.addRow("Host:", self.up_host)
        form.addRow("User:", self.up_user)
        form.addRow("Password:", self.up_pass)
        form.addRow("remote_dir:", self.up_dir)
        return w

    def _microservices_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.ms_edit = QTextEdit()
        self.ms_edit.setPlainText(
            json.dumps(self._secure.get("microservices", []), ensure_ascii=False, indent=2)
        )
        layout.addWidget(self.ms_edit)
        return w

    def _save(self) -> None:
        try:
            self._secure["ssh"] = {
                "host": self.ssh_host.text().strip(),
                "port": int(self.ssh_port.text().strip() or "22"),
                "username": self.ssh_user.text().strip(),
                "password": self.ssh_pass.text(),
                "key_filename": self._secure.get("ssh", {}).get("key_filename", ""),
                "look_for_keys": True,
                "allow_agent": True,
            }
            self._secure["upload"] = {
                "enabled": self.up_enabled.text().strip().lower() == "true",
                "host": self.up_host.text().strip(),
                "port": 22,
                "username": self.up_user.text().strip(),
                "password": self.up_pass.text(),
                "remote_dir": self.up_dir.text().strip(),
            }
            self._secure["microservices"] = json.loads(self.ms_edit.toPlainText())
        except Exception as exc:
            QMessageBox.warning(self, "Инфраструктура", str(exc))
            self.audit.record(
                "config.save",
                user=self.user_login,
                status="error",
                message=str(exc),
            )
            return
        save_secure_config(self.vault_session.vault, self._secure)
        self.audit.record(
            "config.save",
            user=self.user_login,
            status="ok",
            ssh_host=mask_ipv4(self._secure["ssh"]["host"]),
        )
        self.accept()
