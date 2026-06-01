from __future__ import annotations

import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

from sam.auth.session import SamUser
from sam.audit.audit_log import AuditLogger
from sam.config.runtime import load_runtime_config
from sam.config.settings import save_config, sam_cfg
from sam.models.microservice import microservice_by_id, parse_microservices
from sam.ui.connections_panel import ConnectionsPanel
from sam.ui.infrastructure_dialog import InfrastructureDialog
from sam.ui.styles import APP_STYLESHEET
from sam.ui.users_dialog import UsersDialog
from sam.util.app_paths import (
    app_data_dir,
    default_export_dir,
    user_config_path,
    users_db_path,
)
from sam.util.date_range import iter_dates
from sam.util.masking import mask_ipv4
from sam.vault.session import VaultSession
from sam.vault.store import vault_path_from_config
from sam.workers.fetch_worker import FetchWorker

try:
    from PyQt6.QtCore import QDate, Qt
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
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    _PYQT6 = True
except ImportError:  # pragma: no cover
    _PYQT6 = False
    from PyQt5.QtCore import QDate, Qt  # type: ignore
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
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )


def run_qt_app(app: QApplication) -> int:
    return app.exec()


def _section(layout: QVBoxLayout, title: str, hint: str = "") -> None:
    t = QLabel(title)
    t.setObjectName("sectionTitle")
    layout.addWidget(t)
    if hint:
        h = QLabel(hint)
        h.setObjectName("sectionHint")
        h.setWordWrap(True)
        layout.addWidget(h)


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
        self.resize(820, 620)
        self.worker: FetchWorker | None = None
        last = str(sam.get("last_export_dir") or "").strip()
        self.export_dir = last if last and Path(last).is_dir() else str(default_export_dir())
        self._build_ui()
        self._refresh_all()
        self.audit.record("ui.open", user=user.login, status="ok", role=user.role)
        self.logger.info("Main window opened for %s", user.login)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        brand = QLabel("SAM")
        brand.setObjectName("appTitle")
        sub = QLabel(f"  ·  {self.user.display_name} ({self.user.role})")
        sub.setObjectName("hintLabel")
        header.addWidget(brand)
        header.addWidget(sub)
        header.addStretch()
        btn_logout = QPushButton("Выйти")
        btn_logout.setObjectName("secondaryBtn")
        btn_logout.clicked.connect(self.close)
        header.addWidget(btn_logout)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_download_tab(), "Скачивание логов")
        self.connections_panel = ConnectionsPanel(
            is_admin=self.user.is_admin,
            on_edit=self._edit_infrastructure,
        )
        self.tabs.addTab(self.connections_panel, "Подключения")
        if self.user.is_admin:
            self.tabs.addTab(self._build_users_tab(), "Пользователи")
        self.tabs.addTab(self._build_help_tab(), "Справка")
        root.addWidget(self.tabs, stretch=1)

    def _build_download_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # --- ОТКУДА ---
        from_box = QGroupBox("Откуда скачать")
        from_layout = QVBoxLayout(from_box)

        self.source_summary = QLabel()
        self.source_summary.setObjectName("hintLabel")
        self.source_summary.setWordWrap(True)
        from_layout.addWidget(self.source_summary)

        row_svc = QHBoxLayout()
        row_svc.addWidget(QLabel("Микросервис:"))
        self.service_combo = QComboBox()
        self.service_combo.setMinimumWidth(260)
        row_svc.addWidget(self.service_combo, stretch=1)
        from_layout.addLayout(row_svc)

        row_dates = QHBoxLayout()
        row_dates.addWidget(QLabel("Период:"))
        row_dates.addWidget(QLabel("с"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setDate(QDate.currentDate())
        row_dates.addWidget(self.date_from)
        row_dates.addWidget(QLabel("по"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setDate(QDate.currentDate())
        row_dates.addWidget(self.date_to)
        row_dates.addStretch()
        from_layout.addLayout(row_dates)

        self.chk_grep = QCheckBox("Искать только строки с текстом (grep / zgrep)")
        self.chk_grep.toggled.connect(lambda c: self.grep_edit.setEnabled(c))
        from_layout.addWidget(self.chk_grep)
        row_grep = QHBoxLayout()
        row_grep.addWidget(QLabel("Текст в логе:"))
        self.grep_edit = QLineEdit()
        self.grep_edit.setPlaceholderText("например номер АТМ M6768022")
        self.grep_edit.setEnabled(False)
        row_grep.addWidget(self.grep_edit, stretch=1)
        from_layout.addLayout(row_grep)

        layout.addWidget(from_box)

        # --- КУДА (локально) ---
        to_box = QGroupBox("Куда сохранить на этом компьютере")
        to_layout = QVBoxLayout(to_box)
        hint_local = QLabel(
            "Сюда попадут файлы .txt после выгрузки. Сервер с логами не изменяется."
        )
        hint_local.setObjectName("sectionHint")
        hint_local.setWordWrap(True)
        to_layout.addWidget(hint_local)
        row_dir = QHBoxLayout()
        self.dir_edit = QLineEdit(self.export_dir)
        self.dir_edit.setPlaceholderText("Папка на диске…")
        btn_dir = QPushButton("Выбрать папку…")
        btn_dir.setObjectName("secondaryBtn")
        btn_dir.clicked.connect(self._pick_export_dir)
        row_dir.addWidget(self.dir_edit, stretch=1)
        row_dir.addWidget(btn_dir)
        to_layout.addLayout(row_dir)
        layout.addWidget(to_box)

        # --- КУДА (upload) ---
        upload_box = QGroupBox("Куда загрузить копию (опционально)")
        ul = QVBoxLayout(upload_box)
        self.upload_summary = QLabel()
        self.upload_summary.setWordWrap(True)
        self.upload_summary.setObjectName("hintLabel")
        ul.addWidget(self.upload_summary)
        link = QLabel(
            'Настраивается на вкладке «Подключения». По умолчанию выключено — '
            "только скачивание, без записи на сервер."
        )
        link.setObjectName("sectionHint")
        link.setWordWrap(True)
        ul.addWidget(link)
        layout.addWidget(upload_box)

        # --- действия + лог ---
        actions = QHBoxLayout()
        self.btn_fetch = QPushButton("Скачать логи")
        self.btn_fetch.setObjectName("primaryLarge")
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
        layout.addLayout(actions)

        _section(layout, "Ход операции")
        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(140)
        layout.addWidget(self.log_view, stretch=1)

        return page

    def _build_users_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        _section(
            layout,
            "Пользователи SAM",
            "Учётные записи для входа в программу. Пароли хранятся как bcrypt-хэш.",
        )
        btn = QPushButton("Управление пользователями…")
        btn.setObjectName("primaryLarge")
        btn.clicked.connect(self._edit_users)
        layout.addWidget(btn)
        layout.addStretch()
        return page

    def _build_help_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        data = app_data_dir()
        text = QLabel(
            "<b>Как это работает</b><br><br>"
            "1. Вкладка <b>«Подключения»</b> — укажите сервер, с которого читать логи, "
            "микросервисы и пути (файл vault).<br>"
            "2. Вкладка <b>«Скачивание логов»</b> — выберите микросервис, дату, "
            "при необходимости текст для grep.<br>"
            "3. Блок <b>«Куда сохранить»</b> — папка на вашем ПК.<br><br>"
            "<b>Файлы</b><br>"
            f"• Настройки: <code>{user_config_path()}</code><br>"
            f"• Подключения (шифр.): <code>{vault_path_from_config(self.public_config, data)}</code><br>"
            f"• Пользователи: <code>{users_db_path()}</code><br>"
            f"• Аудит: <code>{data / 'audit'}</code><br>"
            f"• Технический лог: <code>{data / 'logs'}</code><br><br>"
            "<b>Безопасность</b><br>"
            "На сервере с логами выполняются только команды чтения "
            "(zgrep, grep, zcat, cat). Файлы логов не изменяются."
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText if _PYQT6 else Qt.RichText)
        text.setOpenExternalLinks(False)
        layout.addWidget(text)
        layout.addStretch()
        return page

    def _refresh_all(self) -> None:
        self.config = load_runtime_config(self.vault_session.vault)
        self._reload_services()
        self._refresh_source_summary()
        self._refresh_upload_summary()
        data = app_data_dir()
        self.connections_panel.set_paths(
            self.config_path,
            vault_path_from_config(self.public_config, data),
            users_db_path(),
        )
        self.connections_panel.refresh_summary(self.config)

    def _refresh_source_summary(self) -> None:
        ssh = self.config.get("ssh") or {}
        host = mask_ipv4(str(ssh.get("host") or ""))
        user = ssh.get("username") or "—"
        if ssh.get("host"):
            self.source_summary.setText(
                f"Сервер логов: {user}@{host}  ·  "
                "данные читаются по SSH, без изменений на сервере."
            )
        else:
            self.source_summary.setText(
                "Сервер не настроен. Откройте вкладку «Подключения»."
            )

    def _refresh_upload_summary(self) -> None:
        up = self.config.get("upload") or {}
        if up.get("enabled"):
            uh = mask_ipv4(str(up.get("host") or ""))
            self.upload_summary.setText(
                f"После скачивания файлы будут отправлены на: "
                f"{up.get('username', '—')}@{uh} → {up.get('remote_dir') or '?'}"
            )
        else:
            self.upload_summary.setText("Выключено — файлы остаются только на этом ПК.")

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
            self._refresh_all()
            self.audit.record("config.reload", user=self.user.login, status="ok")

    def _edit_users(self) -> None:
        from sam.auth.users import UserStore

        UsersDialog(UserStore(users_db_path()), self.audit, self.user.login, self).exec()

    def _pick_export_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Куда сохранить логи на этом компьютере",
            self.dir_edit.text(),
        )
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
            QMessageBox.warning(
                self,
                "SAM",
                "Нет микросервисов.\n\nОткройте вкладку «Подключения» "
                "и настройте серверы.",
            )
            self.tabs.setCurrentWidget(self.connections_panel)
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
                QMessageBox.warning(self, "SAM", "Введите текст для поиска в логе.")
                return
            label = grep

        dates = iter_dates(self._qdate_to_py(self.date_from), self._qdate_to_py(self.date_to))
        if len(dates) > 31:
            QMessageBox.warning(self, "SAM", "Не более 31 дня за один раз.")
            return

        export = self.dir_edit.text().strip()
        if not export:
            QMessageBox.warning(self, "SAM", "Укажите папку «Куда сохранить».")
            return

        ssh = self.config.get("ssh", {})
        if not ssh.get("host") or not ssh.get("username"):
            QMessageBox.warning(
                self,
                "SAM",
                "Не настроен сервер «Откуда скачать».\n\n"
                "Вкладка «Подключения» → «Изменить серверы и микросервисы».",
            )
            self.tabs.setCurrentWidget(self.connections_panel)
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
    from sam.__main__ import main

    raise SystemExit(main())
