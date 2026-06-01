from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from sam.config.settings import load_config, save_config, sam_cfg
from sam.ui.styles import APP_STYLESHEET
from sam.util.app_paths import default_export_dir, user_config_path
from sam.workers.fetch_worker import FetchWorker

try:
    from PyQt6.QtCore import QDate, Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QDateEdit,
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
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QDateEdit,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config_path = user_config_path()
        self.config = load_config()
        sam = sam_cfg(self.config)
        self.setWindowTitle(str(sam.get("window_title", "SAM")))
        self.resize(720, 520)
        self.worker: FetchWorker | None = None
        last = str(sam.get("last_export_dir") or "").strip()
        self.export_dir = last if last and Path(last).is_dir() else str(default_export_dir())
        self._build_ui()
        self._apply_ssh_hint()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Выгрузка логов atm-ddc-service")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        root.addWidget(title)

        hint = QLabel(
            "Укажите номер АТМ и дату. Поиск выполняется на сервере через SSH "
            "(zgrep по архиву и grep по текущему логу, как в atm-ddc-logs.sh)."
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QGroupBox("Параметры")
        form_layout = QVBoxLayout(form)

        row_atm = QHBoxLayout()
        row_atm.addWidget(QLabel("Номер АТМ:"))
        self.atm_edit = QLineEdit()
        self.atm_edit.setPlaceholderText("например M6768022")
        row_atm.addWidget(self.atm_edit, stretch=1)
        form_layout.addLayout(row_atm)

        row_date = QHBoxLayout()
        row_date.addWidget(QLabel("Дата:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setDate(QDate.currentDate())
        row_date.addWidget(self.date_edit)
        row_date.addStretch()
        form_layout.addLayout(row_date)

        row_dir = QHBoxLayout()
        row_dir.addWidget(QLabel("Папка сохранения:"))
        self.dir_edit = QLineEdit(self.export_dir)
        btn_dir = QPushButton("…")
        btn_dir.setObjectName("secondaryBtn")
        btn_dir.setFixedWidth(32)
        btn_dir.clicked.connect(self._pick_export_dir)
        row_dir.addWidget(self.dir_edit, stretch=1)
        row_dir.addWidget(btn_dir)
        form_layout.addLayout(row_dir)

        ssh = self.config.get("ssh", {})
        self.ssh_label = QLabel()
        self.ssh_label.setObjectName("hintLabel")
        self.ssh_label.setText(
            f"SSH: {ssh.get('username', '—')}@{ssh.get('host', '—')} "
            f"(настройка: {self.config_path})"
        )
        form_layout.addWidget(self.ssh_label)
        root.addWidget(form)

        actions = QHBoxLayout()
        self.btn_fetch = QPushButton("Скачать логи")
        self.btn_fetch.clicked.connect(self._start_fetch)
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setObjectName("stopBtn")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_fetch)
        self.btn_open = QPushButton("Открыть папку")
        self.btn_open.setObjectName("secondaryBtn")
        self.btn_open.clicked.connect(self._open_export_dir)
        actions.addWidget(self.btn_fetch)
        actions.addWidget(self.btn_cancel)
        actions.addStretch()
        actions.addWidget(self.btn_open)
        root.addLayout(actions)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, stretch=1)

    def _apply_ssh_hint(self) -> None:
        ssh = self.config.get("ssh", {})
        if not ssh.get("username") or not ssh.get("host"):
            self._append_log(
                "Подсказка: создайте config.yaml в "
                f"{self.config_path.parent} — см. sam/config.example.yaml"
            )

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

    def _qdate_to_py(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    def _persist_export_dir(self) -> None:
        path = self.dir_edit.text().strip()
        if path:
            self.config.setdefault("sam", {})["last_export_dir"] = path
            save_config(self.config, self.config_path)

    def _start_fetch(self) -> None:
        atm = self.atm_edit.text().strip()
        if not atm:
            QMessageBox.warning(self, "SAM", "Введите номер АТМ.")
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

        self._persist_export_dir()
        self.log_view.clear()
        self._append_log(f"АТМ: {atm.upper()} · дата: {self._qdate_to_py().isoformat()}")
        self.btn_fetch.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        self.worker = FetchWorker(
            self.config,
            atm,
            self._qdate_to_py(),
            export,
            self,
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
            self._append_log("Готово. Файлы не созданы (нет совпадений).")
            QMessageBox.information(self, "SAM", "Совпадений в логах не найдено.")
            return
        lines = ", ".join(
            f"{k}: {v}" for k, v in sorted(result.line_counts.items()) if v
        )
        self._append_log(f"Готово. {lines}")
        if result.uploaded:
            self._append_log("Загружено на сервер: " + ", ".join(result.uploaded))
        names = "\n".join(str(p) for p in result.files)
        QMessageBox.information(self, "SAM", f"Сохранено:\n{names}")

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
