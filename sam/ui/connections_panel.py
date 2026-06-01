from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from sam.models.microservice import parse_microservices
from sam.util.masking import mask_ipv4

try:
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtGui import QDesktopServices
    _SELECT_TEXT = _SELECT_TEXT
    from PyQt6.QtWidgets import (
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover
    from PyQt5.QtCore import Qt, QUrl  # type: ignore
    from PyQt5.QtGui import QDesktopServices  # type: ignore
    _SELECT_TEXT = Qt.TextSelectableByMouse
    from PyQt5.QtWidgets import (  # type: ignore
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )


class ConnectionsPanel(QWidget):
    """Вкладка «Подключения»: где лежат файлы и сводка серверов."""

    def __init__(
        self,
        *,
        is_admin: bool,
        on_edit: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._is_admin = is_admin
        self._on_edit = on_edit
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        intro = QLabel(
            "Здесь задаются серверы, микросервисы и пути к логам. "
            "Пароли и IP хранятся в зашифрованном vault, не в открытом тексте."
        )
        intro.setObjectName("sectionHint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        files_box = QGroupBox("Файлы настроек на этом компьютере")
        fl = QVBoxLayout(files_box)
        self.lbl_public = QLabel()
        self.lbl_public.setObjectName("pathLabel")
        self.lbl_public.setTextInteractionFlags(
            _SELECT_TEXT
        )
        self.lbl_vault = QLabel()
        self.lbl_vault.setObjectName("pathLabel")
        self.lbl_vault.setTextInteractionFlags(
            _SELECT_TEXT
        )
        self.lbl_users = QLabel()
        self.lbl_users.setObjectName("pathLabel")
        self.lbl_users.setTextInteractionFlags(
            _SELECT_TEXT
        )
        fl.addWidget(QLabel("Общие настройки (без паролей и IP):"))
        fl.addWidget(self.lbl_public)
        fl.addWidget(QLabel("Серверы, IP, пароли, микросервисы (зашифровано):"))
        fl.addWidget(self.lbl_vault)
        fl.addWidget(QLabel("Пользователи SAM (хэши паролей):"))
        fl.addWidget(self.lbl_users)
        layout.addWidget(files_box)

        summary_box = QGroupBox("Текущие подключения")
        sl = QVBoxLayout(summary_box)
        self.lbl_ssh = QLabel()
        self.lbl_ssh.setWordWrap(True)
        self.lbl_services = QLabel()
        self.lbl_services.setWordWrap(True)
        self.lbl_upload = QLabel()
        self.lbl_upload.setWordWrap(True)
        sl.addWidget(QLabel("Откуда скачивать логи (SSH к серверу логов):"))
        sl.addWidget(self.lbl_ssh)
        sl.addWidget(QLabel("Микросервисы и пути к логам:"))
        sl.addWidget(self.lbl_services)
        sl.addWidget(QLabel("Куда загружать копию (опционально, другой сервер):"))
        sl.addWidget(self.lbl_upload)
        layout.addWidget(summary_box)

        row = QHBoxLayout()
        if self._is_admin:
            btn = QPushButton("Изменить серверы и микросервисы…")
            btn.setObjectName("primaryLarge")
            btn.clicked.connect(self._on_edit)
            row.addWidget(btn)
        else:
            row.addWidget(
                QLabel("Изменение подключений доступно только администратору.")
            )
        row.addStretch()
        btn_folder = QPushButton("Открыть папку SAM")
        btn_folder.setObjectName("secondaryBtn")
        btn_folder.clicked.connect(self._open_sam_folder)
        row.addWidget(btn_folder)
        layout.addLayout(row)
        layout.addStretch()

    def _open_sam_folder(self) -> None:
        path = Path(self.lbl_public.text().split("\n")[0]).parent
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def set_paths(
        self,
        public_config: Path,
        vault_path: Path,
        users_path: Path,
    ) -> None:
        self.lbl_public.setText(str(public_config.resolve()))
        self.lbl_vault.setText(str(vault_path.resolve()))
        self.lbl_users.setText(str(users_path.resolve()))

    def refresh_summary(self, config: dict[str, Any]) -> None:
        ssh = config.get("ssh") or {}
        host = mask_ipv4(str(ssh.get("host") or ""))
        user = ssh.get("username") or "—"
        if host and host != "—":
            self.lbl_ssh.setText(f"  {user}@{host}  (порт {ssh.get('port', 22)})")
        else:
            self.lbl_ssh.setObjectName("statusWarn")
            self.lbl_ssh.setText("  Не настроено — нажмите «Изменить серверы…»")

        lines = []
        for svc in parse_microservices(config):
            lines.append(f"  • {svc.display_name} — {svc.service_dir}")
        self.lbl_services.setText("\n".join(lines) if lines else "  Нет микросервисов")

        up = config.get("upload") or {}
        if up.get("enabled"):
            uh = mask_ipv4(str(up.get("host") or ""))
            self.lbl_upload.setText(
                f"  Включено → {up.get('username', '—')}@{uh}\n"
                f"  Папка: {up.get('remote_dir') or '—'}"
            )
            self.lbl_upload.setObjectName("statusOk")
        else:
            self.lbl_upload.setObjectName("hintLabel")
            self.lbl_upload.setText(
                "  Выключено (рекомендуется). Логи только на этот ПК."
            )
