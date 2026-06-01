from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from sam.config.settings import load_config, save_config, sam_cfg
from sam.models.microservice import microservice_by_id, parse_microservices
from sam.ui.microservices_dialog import MicroservicesDialog
from sam.ui.styles import APP_STYLESHEET
from sam.ui.vault_dialog import VaultSecretsDialog, VaultUnlockDialog
from sam.util.app_paths import default_export_dir, user_config_path
from sam.util.date_range import iter_dates
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
except ImportError:  # pragma: no cover
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config_path = user_config_path()
        self.config = load_config()
        self.vault_session = VaultSession.get(self.config)
        self._ensure_vault()
        sam = sam_cfg(self.config)
        self.setWindowTitle(str(sam.get("window_title", "SAM")))
        self.resize(760, 560)
        self.worker: FetchWorker | None = None
        last = str(sam.get("last_export_dir") or "").strip()
        self.export_dir = last if last and Path(last).is_dir() else str(default_export_dir())
        self._build_ui()
        self._reload_services()

    def _ensure_vault(self) -> None:
        if self.vault_session.try_auto_unlock():
            return
        if self.vault_session.needs_unlock():
            dlg = VaultUnlockDialog(self.vault_session, self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                QMessageBox.warning(
                    self,
                    "SAM",
                    "Без vault нельзя использовать password_secret в конфиге.",
                )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Выгрузка логов микросервисов")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        root.addWidget(title)

        hint = QLabel(
            "Выберите микросервис и дату (или период). "
            "С фильтром — grep/zgrep по значению (АТМ и т.п.); "
            "без фильтра — полный лог за день из архива (zcat)."
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QGroupBox("Параметры")
        fl = QVBoxLayout(form)

        row_svc = QHBoxLayout()
        row_svc.addWidget(QLabel("Микросервис:"))
        self.service_combo = QComboBox()
        self.service_combo.setMinimumWidth(220)
        row_svc.addWidget(self.service_combo, stretch=1)
        btn_svc = QPushButton("Сервисы…")
        btn_svc.setObjectName("secondaryBtn")
        btn_svc.clicked.connect(self._edit_services)
        row_svc.addWidget(btn_svc)
        fl.addLayout(row_svc)

        self.chk_grep = QCheckBox("Фильтр по значению (grep / zgrep)")
        self.chk_grep.toggled.connect(self._on_grep_toggled)
        fl.addWidget(self.chk_grep)

        row_grep = QHBoxLayout()
        row_grep.addWidget(QLabel("Значение:"))
        self.grep_edit = QLineEdit()
        self.grep_edit.setPlaceholderText("например M6768022")
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
        secret = ssh.get("password_secret") or ""
        sec_hint = f" · vault: {secret}" if secret else ""
        self.ssh_label = QLabel(
            f"SSH: {ssh.get('username', '—')}@{ssh.get('host', '—')}{sec_hint}"
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
        btn_vault = QPushButton("Секреты…")
        btn_vault.setObjectName("secondaryBtn")
        btn_vault.clicked.connect(self._edit_vault)
        btn_open = QPushButton("Открыть папку")
        btn_open.setObjectName("secondaryBtn")
        btn_open.clicked.connect(self._open_export_dir)
        actions.addWidget(self.btn_fetch)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(btn_vault)
        actions.addStretch()
        actions.addWidget(btn_open)
        root.addLayout(actions)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, stretch=1)

    def _on_grep_toggled(self, checked: bool) -> None:
        self.grep_edit.setEnabled(checked)

    def _reload_services(self) -> None:
        self.service_combo.clear()
        for svc in parse_microservices(self.config):
            self.service_combo.addItem(svc.display_name, svc.id)

    def _edit_services(self) -> None:
        dlg = MicroservicesDialog(self.config, self.config_path, self)
        if dlg.exec():
            self.config = load_config()
            self._reload_services()

    def _edit_vault(self) -> None:
        if not self.vault_session.is_unlocked:
            dlg = VaultUnlockDialog(self.vault_session, self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
        VaultSecretsDialog(self.vault_session, self).exec()

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

    def _qdate_to_py(self, widget: QDateEdit) -> date:
        qd = widget.date()
        return date(qd.year(), qd.month(), qd.day())

    def _persist_export_dir(self) -> None:
        path = self.dir_edit.text().strip()
        if path:
            self.config.setdefault("sam", {})["last_export_dir"] = path
            save_config(self.config, self.config_path)

    def _start_fetch(self) -> None:
        if self.service_combo.count() == 0:
            QMessageBox.warning(self, "SAM", "Добавьте микросервис (кнопка «Сервисы…»).")
            return
        service_id = self.service_combo.currentData()
        service = microservice_by_id(self.config, service_id)
        if service is None:
            QMessageBox.warning(self, "SAM", "Микросервис не найден в конфиге.")
            return

        grep: str | None = None
        label = "all"
        if self.chk_grep.isChecked():
            grep = self.grep_edit.text().strip()
            if not grep:
                QMessageBox.warning(self, "SAM", "Включён фильтр — введите значение для grep.")
                return
            label = grep

        d_from = self._qdate_to_py(self.date_from)
        d_to = self._qdate_to_py(self.date_to)
        dates = iter_dates(d_from, d_to)
        if len(dates) > 31:
            QMessageBox.warning(self, "SAM", "Максимум 31 день за один запрос.")
            return

        export = self.dir_edit.text().strip()
        if not export:
            QMessageBox.warning(self, "SAM", "Укажите папку сохранения.")
            return

        ssh = self.config.get("ssh", {})
        if not ssh.get("host") or not ssh.get("username"):
            QMessageBox.warning(
                self,
                "SAM",
                f"Заполните ssh.host и ssh.username в\n{self.config_path}",
            )
            return

        if self.vault_session.needs_unlock() and not self.vault_session.is_unlocked:
            QMessageBox.warning(self, "SAM", "Разблокируйте vault (Секреты…).")
            return

        self._persist_export_dir()
        self.log_view.clear()
        self._append_log(f"{service.display_name} · дней: {len(dates)}")
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
            self._append_log("Отмена…")

    def _reset_buttons(self) -> None:
        self.btn_fetch.setEnabled(True)
        self.btn_cancel.setEnabled(False)

    def _on_finished(self, result) -> None:
        self._reset_buttons()
        if not result.files:
            self._append_log("Готово. Файлы не созданы.")
            QMessageBox.information(self, "SAM", "Данных за выбранный период не найдено.")
            return
        self._append_log(f"Готово. Файлов: {len(result.files)}")
        names = "\n".join(p.name for p in result.files[:10])
        extra = "" if len(result.files) <= 10 else f"\n… и ещё {len(result.files) - 10}"
        QMessageBox.information(self, "SAM", f"Сохранено:\n{names}{extra}")

    def _on_cancelled(self) -> None:
        self._reset_buttons()
        self._append_log("Операция отменена.")

    def _on_error(self, message: str) -> None:
        self._reset_buttons()
        self._append_log(f"Ошибка: {message}")
        QMessageBox.critical(self, "SAM", message)


def run_app() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
