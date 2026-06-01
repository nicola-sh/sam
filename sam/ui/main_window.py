from __future__ import annotations

import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

from sam.auth.session import SamUser
from sam.audit.audit_log import AuditLogger
from sam.config.runtime import load_runtime_config
from sam.config.settings import load_config, save_config, sam_cfg
from sam.models.microservice import microservice_by_id, parse_microservices
from sam.ui.infrastructure_dialog import InfrastructureDialog
from sam.ui.styles import APP_STYLESHEET
from sam.ui.users_dialog import UsersDialog
from sam.util.app_paths import default_export_dir, user_config_path
from sam.util.date_range import iter_dates
from sam.util.masking import mask_ipv4
from sam.vault.session import VaultSession
from sam.workers.fetch_worker import FetchWorker

try:
    from PyQt6.QtCore import QDate
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDateEdit,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    _PYQT6 = True
except ImportError:  # pragma: no cover
    _PYQT6 = False
    from PyQt5.QtCore import QDate  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QApplication,
        QCheckBox,
        QComboBox,
        QDateEdit,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )


def run_qt_app(app: QApplication) -> int:
    return app.exec()


class MainWindow(QMainWindow):
    def __init__(
        self,
        user: SamUser,
        public_config: dict,
        vault_session: VaultSession,
        audit: AuditLogger,
        logger: logging.Logger,
    ) -> None:
        super().__init__()
        self.user = user
        self.public_config = public_config
        self.vault_session = vault_session
        self.audit = audit
        self.logger = logger
        self.config_path = user_config_path()
        self.config = load_runtime_config(vault_session.vault)
        sam = sam_cfg(self.config)
        title = str(sam.get("window_title", "SAM"))
        self.setWindowTitle(f"{title} — {user.display_name}")
        self.resize(780, 580)
        self.worker: FetchWorker | None = None
        last = str(sam.get("last_export_dir") or "").strip()
        self.export_dir = last if last and Path(last).is_dir() else str(default_export_dir())
        self._build_ui()
        self._reload_services()
        self.audit.record("ui.open", user=user.login, status="ok", role=user.role)
        self.logger.info("Main window opened for %s", user.login)

    def _reload_runtime_config(self) -> None:
        self.config = load_runtime_config(self.vault_session.vault)
        self._reload_services()
        ssh = self.config.get("ssh", {})
        self.ssh_label.setText(
            f"SSH: {ssh.get('username', '—')}@{mask_ipv4(str(ssh.get('host', '')))}"
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        header = QHBoxLayout()
        title = QLabel("Выгрузка логов микросервисов")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        btn_logout = QPushButton("Выйти")
        btn_logout.setObjectName("secondaryBtn")
        btn_logout.clicked.connect(self.close)
        header.addWidget(btn_logout)
        root.addLayout(header)

        form = QGroupBox("Параметры")
        fl = QVBoxLayout(form)

        row_svc = QHBoxLayout()
        row_svc.addWidget(QLabel("Микросервис:"))
        self.service_combo = QComboBox()
        row_svc.addWidget(self.service_combo, stretch=1)
        if self.user.is_admin:
            btn_infra = QPushButton("Инфраструктура…")
            btn_infra.setObjectName("secondaryBtn")
            btn_infra.clicked.connect(self._edit_infrastructure)
            row_svc.addWidget(btn_infra)
            btn_users = QPushButton("Пользователи…")
            btn_users.setObjectName("secondaryBtn")
            btn_users.clicked.connect(self._edit_users)
            row_svc.addWidget(btn_users)
        fl.addLayout(row_svc)

        self.chk_grep = QCheckBox("Фильтр по значению (grep / zgrep)")
        self.chk_grep.toggled.connect(lambda c: self.grep_edit.setEnabled(c))
        fl.addWidget(self.chk_grep)
        row_grep = QHBoxLayout()
        row_grep.addWidget(QLabel("Значение:"))
        self.grep_edit = QLineEdit()
        self.grep_edit.setEnabled(False)
        row_grep.addWidget(self.grep_edit, stretch=1)
        fl.addLayout(row_grep)

        row_dates = QHBoxLayout()
        row_dates.addWidget(QLabel("Дата с:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setDate(QDate.currentDate())
        row_dates.addWidget(self.date_from)
        row_dates.addWidget(QLabel("по:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setDate(QDate.currentDate())
        row_dates.addWidget(self.date_to)
        row_dates.addStretch()
        fl.addLayout(row_dates)

        row_dir = QHBoxLayout()
        row_dir.addWidget(QLabel("Папка:"))
        self.dir_edit = QLineEdit(self.export_dir)
        btn_dir = QPushButton("…")
        btn_dir.setObjectName("secondaryBtn")
        btn_dir.setFixedWidth(32)
        btn_dir.clicked.connect(self._pick_export_dir)
        row_dir.addWidget(self.dir_edit, stretch=1)
        row_dir.addWidget(btn_dir)
        fl.addLayout(row_dir)

        ssh = self.config.get("ssh", {})
        self.ssh_label = QLabel(
            f"SSH: {ssh.get('username', '—')}@{mask_ipv4(str(ssh.get('host', '')))}"
        )
        self.ssh_label.setObjectName("hintLabel")
        fl.addWidget(self.ssh_label)
        root.addWidget(form)

        actions = QHBoxLayout()
        self.btn_fetch = QPushButton("Скачать логи")
        self.btn_fetch.clicked.connect(self._start_fetch)
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setObjectName("stopBtn")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_fetch)
        btn_open = QPushButton("Открыть папку")
        btn_open.setObjectName("secondaryBtn")
        btn_open.clicked.connect(self._open_export_dir)
        actions.addWidget(self.btn_fetch)
        actions.addWidget(self.btn_cancel)
        actions.addStretch()
        actions.addWidget(btn_open)
        root.addLayout(actions)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, stretch=1)

    def _reload_services(self) -> None:
        self.service_combo.clear()
        for svc in parse_microservices(self.config):
            self.service_combo.addItem(svc.display_name, svc.id)

    def _edit_infrastructure(self) -> None:
        dlg = InfrastructureDialog(
            self.vault_session,
            self.audit,
            self.user.login,
            self,
        )
        if dlg.exec():
            self._reload_runtime_config()
            self.audit.record("config.reload", user=self.user.login, status="ok")

    def _edit_users(self) -> None:
        from sam.auth.users import UserStore
        from sam.util.app_paths import users_db_path

        UsersDialog(UserStore(users_db_path()), self.audit, self.user.login, self).exec()

    def _pick_export_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка для логов", self.dir_edit.text())
        if path:
            self.dir_edit.setText(path)

    def _open_export_dir(self) -> None:
        path = Path(self.dir_edit.text().strip() or self.export_dir)
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.run(["explorer", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def _append_log(self, text: str) -> None:
        self.log_view.append(text)
        self.logger.info(text)

    def _qdate_to_py(self, widget: QDateEdit) -> date:
        qd = widget.date()
        return date(qd.year(), qd.month(), qd.day())

    def _start_fetch(self) -> None:
        if self.service_combo.count() == 0:
            QMessageBox.warning(self, "SAM", "Нет микросервисов. Админ: «Инфраструктура…».")
            return
        service_id = self.service_combo.currentData()
        service = microservice_by_id(self.config, service_id)
        if service is None:
            return

        grep = None
        label = "all"
        if self.chk_grep.isChecked():
            grep = self.grep_edit.text().strip()
            if not grep:
                QMessageBox.warning(self, "SAM", "Введите значение для grep.")
                return
            label = grep

        dates = iter_dates(self._qdate_to_py(self.date_from), self._qdate_to_py(self.date_to))
        if len(dates) > 31:
            QMessageBox.warning(self, "SAM", "Не более 31 дня за раз.")
            return

        export = self.dir_edit.text().strip()
        if not export:
            QMessageBox.warning(self, "SAM", "Укажите папку.")
            return

        ssh = self.config.get("ssh", {})
        if not ssh.get("host") or not ssh.get("username"):
            QMessageBox.warning(self, "SAM", "Заполните SSH в «Инфраструктура…».")
            return

        self.public_config.setdefault("sam", {})["last_export_dir"] = export
        save_config(self.public_config, self.config_path)

        self.log_view.clear()
        self.audit.record(
            "log.fetch.start",
            user=self.user.login,
            status="ok",
            service_id=service.id,
            date_from=str(dates[0]),
            date_to=str(dates[-1]),
            grep_enabled=bool(grep),
            days=len(dates),
        )
        self.btn_fetch.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        vault = self.vault_session.vault if self.vault_session.is_unlocked else None
        self.worker = FetchWorker(
            self.config,
            service,
            dates,
            export,
            grep,
            vault,
            label=label,
            parent=self,
        )
        self.worker.log.connect(self._append_log)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel_fetch(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.audit.record("log.fetch.cancel", user=self.user.login, status="ok")

    def _on_finished(self, result) -> None:
        self.btn_fetch.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.audit.record(
            "log.fetch.done",
            user=self.user.login,
            status="ok",
            files=len(result.files),
            service_id=result.service_id,
        )
        if not result.files:
            QMessageBox.information(self, "SAM", "Совпадений не найдено.")
            return
        QMessageBox.information(self, "SAM", f"Сохранено файлов: {len(result.files)}")

    def _on_cancelled(self) -> None:
        self.btn_fetch.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def _on_error(self, message: str) -> None:
        self.btn_fetch.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.logger.error("Fetch error: %s", message)
        self.audit.record(
            "log.fetch.error",
            user=self.user.login,
            status="error",
            message=message,
        )
        QMessageBox.critical(self, "SAM", message)


def run_app() -> None:
    """Совместимость: полный цикл через sam.__main__.main()."""
    from sam.__main__ import main

    raise SystemExit(main())
