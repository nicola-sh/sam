from __future__ import annotations

import json

from sam.audit.audit_log import AuditLogger
from sam.util.masking import mask_ipv4
from sam.vault.secure_config import load_secure_config, save_secure_config
from sam.vault.session import VaultSession

try:
    from PyQt6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QLabel,
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
        QLabel,
        QMessageBox,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )


class InfrastructureDialog(QDialog):
    """Серверы, кластеры FO/BO, микросервисы — только в vault."""

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
        self.setWindowTitle("Подключения — кластеры, серверы, микросервисы")
        self.resize(640, 520)
        self._secure = load_secure_config(vault_session.vault)

        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "Все IP и пароли — в vault.enc (см. вкладку «Подключения» в главном окне).\n"
                "Кластеры FO/BO: одинаковые пути логов на узлах, данные разные — "
                "при выгрузке выбираете один узел."
            )
        )
        tabs = QTabWidget()
        tabs.addTab(self._json_tab("clusters", "Кластеры FO / BO"), "Кластеры")
        tabs.addTab(self._json_tab("servers", "Серверы (ATM и др.)"), "Серверы")
        tabs.addTab(self._json_tab("microservices", "Микросервисы"), "Микросервисы")
        tabs.addTab(self._json_tab("upload", "Upload"), "Куда загрузить копию")
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _json_tab(self, key: str, hint: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(hint))
        edit = QTextEdit()
        edit.setPlainText(
            json.dumps(self._secure.get(key, [] if key != "upload" else {}),
                       ensure_ascii=False,
                       indent=2)
        )
        layout.addWidget(edit)
        setattr(self, f"_edit_{key}", edit)
        return w

    def _save(self) -> None:
        try:
            self._secure["clusters"] = json.loads(self._edit_clusters.toPlainText())
            self._secure["servers"] = json.loads(self._edit_servers.toPlainText())
            self._secure["microservices"] = json.loads(self._edit_microservices.toPlainText())
            self._secure["upload"] = json.loads(self._edit_upload.toPlainText())
        except Exception as exc:
            QMessageBox.warning(self, "Подключения", f"Ошибка JSON: {exc}")
            self.audit.record(
                "config.save", user=self.user_login, status="error", message=str(exc)
            )
            return
        save_secure_config(self.vault_session.vault, self._secure)
        self.audit.record("config.save", user=self.user_login, status="ok")
        self.accept()
