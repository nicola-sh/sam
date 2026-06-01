from __future__ import annotations

import logging
import subprocess
import sys
from datetime import date, time
from pathlib import Path

from sam.auth.session import SamUser
from sam.audit.audit_log import AuditLogger
from sam.config.runtime import load_runtime_config
from sam.config.settings import save_config, sam_cfg
from sam.models.microservice import (
    microservice_by_id,
    microservices_for_source,
    parse_microservices,
)
from sam.models.topology import (
    hosts_for_source,
    list_download_sources,
    resolve_ssh_endpoint,
)
from sam.ui.connections_panel import ConnectionsPanel
from sam.ui.regcon_tab import RegConTabHost
from sam.ui.infrastructure_dialog import InfrastructureDialog
from sam.ui.styles import APP_STYLESHEET
from sam.ui.users_dialog import UsersDialog
from sam.util.app_paths import (
    app_data_dir,
    default_export_dir,
    user_config_path,
    users_db_path,
)
from sam.util.archive_names import default_archive_basename, sanitize_archive_basename, archive_filename
from sam.util.date_range import iter_dates
from sam.services.time_filter import needs_time_filter
from sam.services.zip_archive import ArchiveError, create_password_zip
from sam.util.masking import mask_ipv4
from sam.util.time_window import build_time_window
from sam.vault.session import VaultSession
from sam.vault.store import vault_path_from_config
from sam.workers.fetch_worker import BatchFetchResult, FetchWorker

try:
    from PyQt6.QtCore import QDate, QTime, Qt
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
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QTimeEdit,
        QPushButton,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    _PYQT6 = True
except ImportError:  # pragma: no cover
    _PYQT6 = False
    from PyQt5.QtCore import QDate, QTime, Qt  # type: ignore
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
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTabWidget,
        QTextEdit,
        QTimeEdit,
        QVBoxLayout,
        QWidget,
    )


_USER_ROLE = _USER_ROLE if _PYQT6 else Qt.UserRole


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
        self.tabs.addTab(self._build_download_tab(), "Скачивание")
        self._regcon_host = RegConTabHost(
            export_dir_provider=lambda: self.dir_edit.text().strip(),
            parent=self,
        )
        self.tabs.addTab(self._regcon_host, "Обезличивание")
        self.tabs.currentChanged.connect(self._on_tab_changed)
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

        row_src = QHBoxLayout()
        row_src.addWidget(QLabel("Источник:"))
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(200)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        row_src.addWidget(self.source_combo, stretch=1)
        from_layout.addLayout(row_src)

        row_host = QHBoxLayout()
        self.host_label = QLabel("Узел кластера:")
        row_host.addWidget(self.host_label)
        self.host_combo = QComboBox()
        self.host_combo.setMinimumWidth(200)
        row_host.addWidget(self.host_combo, stretch=1)
        from_layout.addLayout(row_host)

        svc_hint = QLabel(
            "Отметьте один или несколько микросервисов (Ctrl+клик). "
            "Время — для отсечения строк по метке времени в логе."
        )
        svc_hint.setObjectName("sectionHint")
        svc_hint.setWordWrap(True)
        from_layout.addWidget(svc_hint)

        self.service_list = QListWidget()
        self.service_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        self.service_list.setMinimumHeight(72)
        self.service_list.setMaximumHeight(140)
        from_layout.addWidget(self.service_list)

        row_dates = QHBoxLayout()
        row_dates.addWidget(QLabel("Период:"))
        row_dates.addWidget(QLabel("с"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setDate(QDate.currentDate())
        row_dates.addWidget(self.date_from)
        self.time_from = QTimeEdit()
        self.time_from.setDisplayFormat("HH:mm")
        row_dates.addWidget(self.time_from)
        row_dates.addWidget(QLabel("по"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setDate(QDate.currentDate())
        row_dates.addWidget(self.date_to)
        self.time_to = QTimeEdit()
        self.time_to.setDisplayFormat("HH:mm")
        self.time_to.setTime(QTime(23, 59))
        row_dates.addWidget(self.time_to)
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

        # --- АРХИВ ---
        arch_box = QGroupBox("Архив с паролем (опционально)")
        arch_layout = QVBoxLayout(arch_box)
        arch_hint = QLabel(
            "После скачивания собрать файлы в ZIP с паролем (AES). "
            "Имя по умолчанию: log_ММДД-ЧЧММ, например log_0601-1053."
        )
        arch_hint.setObjectName("sectionHint")
        arch_hint.setWordWrap(True)
        arch_layout.addWidget(arch_hint)
        self.chk_archive = QCheckBox("Создать ZIP-архив с паролем")
        self.chk_archive.toggled.connect(self._on_archive_toggled)
        arch_layout.addWidget(self.chk_archive)
        row_arch_name = QHBoxLayout()
        row_arch_name.addWidget(QLabel("Имя архива:"))
        self.archive_name_edit = QLineEdit(default_archive_basename())
        self.archive_name_edit.setPlaceholderText("log_0601-1053")
        self.archive_name_edit.setEnabled(False)
        row_arch_name.addWidget(self.archive_name_edit, stretch=1)
        row_arch_name.addWidget(QLabel(".zip"))
        arch_layout.addLayout(row_arch_name)
        row_arch_pwd = QHBoxLayout()
        row_arch_pwd.addWidget(QLabel("Пароль архива:"))
        self.archive_password_edit = QLineEdit()
        self.archive_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.archive_password_edit.setPlaceholderText("задайте пароль для ZIP")
        self.archive_password_edit.setEnabled(False)
        arch_layout.addLayout(row_arch_pwd)
        layout.addWidget(arch_box)

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
        btn_regcon = QPushButton("Обезличивание →")
        btn_regcon.setObjectName("secondaryBtn")
        btn_regcon.setToolTip("Открыть вкладку RegCon с папкой выгрузки")
        btn_regcon.clicked.connect(self._goto_regcon)
        actions.addWidget(self.btn_fetch)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(btn_regcon)
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
            "2. <b>«Скачивание»</b> — логи с серверов; <b>«Обезличивание»</b> — RegCon (PAN, IP, пароли) по локальным файлам. "
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
        self._reload_sources()
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
        kind, sid = self._current_source()
        try:
            host_id = self.host_combo.currentData() if kind == "cluster" else None
            ep = resolve_ssh_endpoint(
                self.config,
                target_kind=kind,
                target_id=sid,
                host_id=str(host_id) if host_id else None,
                timeout_sec=float(sam_cfg(self.config).get("ssh_timeout_sec", 30)),
            )
            self.source_summary.setText(
                f"Подключение только на время выгрузки · {ep.username}@"
                f"{mask_ipv4(ep.host)} · без изменений файлов на сервере"
            )
        except ValueError:
            self.source_summary.setText(
                "Источник не настроен. Вкладка «Подключения» → изменить серверы."
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


    def _on_source_changed(self) -> None:
        self._reload_hosts()
        self._reload_sources()
        self._refresh_source_summary()

    def _current_source(self) -> tuple[str, str]:
        data = self.source_combo.currentData()
        if data and len(data) >= 2:
            return str(data[0]), str(data[1])
        return "legacy", "default"

    def _reload_sources(self) -> None:
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for kind, sid, label in list_download_sources(self.config):
            self.source_combo.addItem(label, (kind, sid))
        self.source_combo.blockSignals(False)
        if self.source_combo.count():
            self.source_combo.setCurrentIndex(0)
        self._on_source_changed()

    def _reload_hosts(self) -> None:
        kind, sid = self._current_source()
        is_cluster = kind == "cluster"
        self.host_label.setVisible(is_cluster)
        self.host_combo.setVisible(is_cluster)
        self.host_combo.clear()
        if is_cluster:
            for h in hosts_for_source(self.config, kind, sid):
                self.host_combo.addItem(h.id, h.id)
            if self.host_combo.count():
                self.host_combo.setCurrentIndex(0)

    def _reload_services(self) -> None:
        kind, sid = self._current_source()
        self.service_list.clear()
        for svc in microservices_for_source(self.config, kind, sid):
            layout = "сутки" if svc.log_layout != "hourly" else "по часам"
            item = QListWidgetItem(f"{svc.display_name} ({layout})")
            item.setData(_USER_ROLE, svc.id)
            self.service_list.addItem(item)

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

    def _qtime_to_py(self, widget: QTimeEdit) -> time:
        qt = widget.time()
        return time(qt.hour(), qt.minute(), qt.second())

    def _selected_service_ids(self) -> list[str]:
        ids: list[str] = []
        for item in self.service_list.selectedItems():
            sid = item.data(Qt.ItemDataRole.UserRole)
            if sid:
                ids.append(str(sid))
        return ids

    def _start_fetch(self) -> None:
        if self.service_list.count() == 0:
            QMessageBox.warning(
                self,
                "SAM",
                "Нет микросервисов.\n\nОткройте вкладку «Подключения» "
                "и настройте серверы.",
            )
            self.tabs.setCurrentWidget(self.connections_panel)
            return
        service_ids = self._selected_service_ids()
        if not service_ids:
            QMessageBox.warning(
                self,
                "SAM",
                "Выберите хотя бы один микросервис в списке "
                "(Ctrl+клик для нескольких).",
            )
            return
        services = []
        for sid in service_ids:
            svc = microservice_by_id(self.config, sid)
            if svc is not None:
                services.append(svc)
        if not services:
            return

        grep = None
        label = "all"
        if self.chk_grep.isChecked():
            grep = self.grep_edit.text().strip()
            if not grep:
                QMessageBox.warning(self, "SAM", "Введите текст для поиска в логе.")
                return
            label = grep

        d_from = self._qdate_to_py(self.date_from)
        d_to = self._qdate_to_py(self.date_to)
        t_from = self._qtime_to_py(self.time_from)
        t_to = self._qtime_to_py(self.time_to)
        dates = iter_dates(d_from, d_to)
        if len(dates) > 31:
            QMessageBox.warning(self, "SAM", "Не более 31 дня за один раз.")
            return
        time_window = build_time_window(d_from, d_to, t_from, t_to)
        apply_time_filter = needs_time_filter(t_from, t_to)

        export = self.dir_edit.text().strip()
        if not export:
            QMessageBox.warning(self, "SAM", "Укажите папку «Куда сохранить».")
            return

        kind, sid = self._current_source()
        host_id = str(self.host_combo.currentData() or "") if kind == "cluster" else None
        try:
            ssh_ep = resolve_ssh_endpoint(
                self.config,
                target_kind=kind,
                target_id=sid,
                host_id=host_id,
                timeout_sec=float(sam_cfg(self.config).get("ssh_timeout_sec", 30)),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "SAM", str(exc))
            self.tabs.setCurrentWidget(self.connections_panel)
            return

        self.public_config.setdefault("sam", {})["last_export_dir"] = export
        save_config(self.public_config, self.config_path)

        if self.chk_archive.isChecked():
            self.archive_name_edit.setText(default_archive_basename())
        self.log_view.clear()
        self.audit.record(
            "log.fetch.start",
            user=self.user.login,
            status="ok",
            service_ids=[s.id for s in services],
            date_from=str(dates[0]),
            date_to=str(dates[-1]),
            time_from=t_from.isoformat(timespec="minutes"),
            time_to=t_to.isoformat(timespec="minutes"),
            time_filter=apply_time_filter,
            grep_enabled=bool(grep),
            days=len(dates),
            archive_enabled=self.chk_archive.isChecked(),
            target_kind=kind,
            target_id=sid,
            host_id=host_id or "",
        )
        self.btn_fetch.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        vault = self.vault_session.vault if self.vault_session.is_unlocked else None
        self.worker = FetchWorker(
            self.config,
            services,
            dates,
            export,
            grep,
            vault,
            label=label,
            ssh_endpoint=ssh_ep,
            target_kind=kind,
            target_id=sid,
            host_id=host_id or "",
            time_window=time_window,
            apply_time_filter=apply_time_filter,
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

    def _on_finished(self, result: BatchFetchResult) -> None:
        self.btn_fetch.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.audit.record(
            "log.fetch.done",
            user=self.user.login,
            status="ok",
            files=len(result.files),
            service_ids=result.service_ids,
        )
        if not result.files:
            QMessageBox.information(self, "SAM", "Совпадений не найдено.")
            return

        msg = f"Сохранено файлов: {len(result.files)}"
        want_arch, base_name, arch_pwd = self._archive_options()
        if want_arch:
            if not arch_pwd:
                QMessageBox.warning(self, "SAM", "Укажите пароль для архива.")
                return
            export_dir = Path(self.dir_edit.text().strip())
            zip_name = archive_filename(base_name)
            zip_path = export_dir / zip_name
            try:
                self._append_log(f"Архивирование → {zip_name}…")
                create_password_zip(
                    result.files,
                    output_path=zip_path,
                    password=arch_pwd,
                )
                self.audit.record(
                    "log.archive",
                    user=self.user.login,
                    status="ok",
                    archive_name=zip_name,
                    file_count=len(result.files),
                )
                msg += f"\n\nАрхив: {zip_path}"
                self._append_log(f"Архив создан: {zip_path}")
            except ArchiveError as exc:
                self.audit.record(
                    "log.archive",
                    user=self.user.login,
                    status="error",
                    message=str(exc),
                )
                QMessageBox.critical(self, "SAM", f"Ошибка архива: {exc}")
                return

        QMessageBox.information(self, "SAM", msg)

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
