from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from regcon.config.settings import load_config
from regcon.models import Finding
from regcon.workers.worker import Worker

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    _PYQT6 = True
except ImportError:  # pragma: no cover
    _PYQT6 = False
    from PyQt5.QtCore import Qt  # type: ignore
    from PyQt5.QtWidgets import (  # type: ignore
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

if _PYQT6:
    _CHECKED = Qt.CheckState.Checked
    _UNCHECKED = Qt.CheckState.Unchecked
    _USER_CHECKABLE = Qt.ItemFlag.ItemIsUserCheckable
    _ENABLED = Qt.ItemFlag.ItemIsEnabled
    _VERTICAL = Qt.Orientation.Vertical
    _STRETCH = QHeaderView.ResizeMode.Stretch
else:
    _CHECKED = Qt.Checked
    _UNCHECKED = Qt.Unchecked
    _USER_CHECKABLE = Qt.ItemIsUserCheckable
    _ENABLED = Qt.ItemIsEnabled
    _VERTICAL = Qt.Vertical
    _STRETCH = QHeaderView.Stretch


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RegCon — обезличивание логов")
        self.resize(1100, 720)
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
        self.config = load_config(config_path)
        self.files: list[str] = []
        self.findings: list[Finding] = []
        self.worker: Worker | None = None
        self._table_limit = int(
            self.config.get("regcon", {}).get("max_table_rows", 5000)
        )
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        drop_hint = QLabel(
            "Перетащите файлы в окно или выберите через «Обзор…»"
        )
        drop_hint.setStyleSheet("color: #555;")
        root.addWidget(drop_hint)

        files_row = QHBoxLayout()
        self.files_label = QLabel("Файлы не выбраны")
        self.files_label.setWordWrap(True)
        browse_btn = QPushButton("Обзор…")
        browse_btn.clicked.connect(self._browse_files)
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self._clear_files)
        files_row.addWidget(self.files_label, stretch=1)
        files_row.addWidget(browse_btn)
        files_row.addWidget(clear_btn)
        root.addLayout(files_row)

        opts = QGroupBox("Режим и детекторы")
        opts_layout = QVBoxLayout(opts)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(
            [
                "Сканировать",
                "Маскировать",
                "CSV → Excel",
                "Форматировать JSON",
                "Полный цикл",
            ]
        )
        mode_row.addWidget(self.mode_combo, stretch=1)
        opts_layout.addLayout(mode_row)

        det_row = QHBoxLayout()
        pan_cfg = self.config.get("pan", {})
        ip_cfg = self.config.get("ip", {})
        pwd_cfg = self.config.get("passwords", {})
        self.chk_pan = QCheckBox("PAN (Luhn)")
        self.chk_pan.setChecked(pan_cfg.get("enabled", True))
        self.chk_ip = QCheckBox("IP")
        self.chk_ip.setChecked(ip_cfg.get("enabled", True))
        self.chk_pwd = QCheckBox("Пароли")
        self.chk_pwd.setChecked(pwd_cfg.get("enabled", True))
        det_row.addWidget(self.chk_pan)
        det_row.addWidget(self.chk_ip)
        det_row.addWidget(self.chk_pwd)
        det_row.addStretch()
        opts_layout.addLayout(det_row)
        root.addWidget(opts)

        out_row = QHBoxLayout()
        default_out = str(Path.home() / "regcon-output")
        self.output_dir = default_out
        self.out_label = QLabel(f"Выход: {default_out}")
        out_btn = QPushButton("Папка выхода…")
        out_btn.clicked.connect(self._browse_output)
        open_btn = QPushButton("Открыть папку")
        open_btn.clicked.connect(self._open_output_dir)
        out_row.addWidget(self.out_label, stretch=1)
        out_row.addWidget(out_btn)
        out_row.addWidget(open_btn)
        root.addLayout(out_row)

        action_row = QHBoxLayout()
        self.start_btn = QPushButton("Старт")
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        self.apply_btn = QPushButton("Применить маску")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply_mask)
        self.select_all_btn = QPushButton("Выбрать все")
        self.select_all_btn.clicked.connect(lambda: self._set_all_findings(True))
        self.deselect_all_btn = QPushButton("Снять все")
        self.deselect_all_btn.clicked.connect(lambda: self._set_all_findings(False))
        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.stop_btn)
        action_row.addWidget(self.apply_btn)
        action_row.addWidget(self.select_all_btn)
        action_row.addWidget(self.deselect_all_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        self.progress = QProgressBar()
        root.addWidget(self.progress)

        splitter = QSplitter(_VERTICAL)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["✓", "Тип", "Файл", "Строка", "Фрагмент"]
        )
        self.table.horizontalHeader().setSectionResizeMode(4, _STRETCH)
        self.table.cellChanged.connect(self._on_cell_changed)
        splitter.addWidget(self.table)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        splitter.addWidget(self.log_view)
        splitter.setSizes([380, 200])
        root.addWidget(splitter, stretch=1)

    def _sync_config_flags(self) -> None:
        self.config.setdefault("pan", {})["enabled"] = self.chk_pan.isChecked()
        self.config.setdefault("ip", {})["enabled"] = self.chk_ip.isChecked()
        self.config.setdefault("passwords", {})["enabled"] = self.chk_pwd.isChecked()

    def _mode_key(self) -> str:
        mapping = {
            0: "scan",
            1: "mask",
            2: "csv2xlsx",
            3: "format_json",
            4: "full",
        }
        return mapping[self.mode_combo.currentIndex()]

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths: list[str] = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local and Path(local).is_file():
                paths.append(local)
        if paths:
            self._add_files(paths)
        event.acceptProposedAction()

    def _add_files(self, paths: list[str]) -> None:
        merged = list(dict.fromkeys(self.files + paths))
        self.files = merged
        self.files_label.setText(
            f"Выбрано файлов: {len(merged)} — "
            + ", ".join(Path(p).name for p in merged[:5])
            + (" …" if len(merged) > 5 else "")
        )

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы",
            str(Path.home()),
            "Логи и таблицы (*.txt *.log *.csv *.xlsx *.xls *.json);;Все (*.*)",
        )
        if paths:
            self._add_files(paths)

    def _clear_files(self) -> None:
        self.files = []
        self.findings = []
        self.files_label.setText("Файлы не выбраны")
        self.table.setRowCount(0)
        self.apply_btn.setEnabled(False)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка выхода", self.output_dir)
        if path:
            self.output_dir = path
            self.out_label.setText(f"Выход: {path}")

    def _open_output_dir(self) -> None:
        path = Path(self.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)

    def _set_busy(self, busy: bool) -> None:
        self.start_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.apply_btn.setEnabled((not busy) and bool(self.findings))

    def _connect_worker(self, worker: Worker) -> None:
        worker.progress.connect(self.progress.setValue)
        worker.log.connect(self._append_log)
        worker.error.connect(self._on_worker_error)
        worker.cancelled.connect(self._on_worker_cancelled)
        worker.scan_done.connect(self._on_scan_done)
        worker.finished_ok.connect(self._on_worker_finished)

    def _on_stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self._append_log("Запрошена остановка…")
            self.worker.requestInterruption()

    def _on_start(self) -> None:
        if not self.files:
            QMessageBox.warning(self, "RegCon", "Выберите хотя бы один файл.")
            return
        self._sync_config_flags()
        mode = self._mode_key()
        if mode == "mask" and not self.findings:
            QMessageBox.warning(
                self,
                "RegCon",
                "Сначала выполните сканирование или выберите режим «Полный цикл».",
            )
            return
        self.progress.setValue(0)
        self._set_busy(True)
        findings_payload = [f.to_dict() for f in self.findings] if mode == "mask" else None
        self.worker = Worker(
            files=self.files,
            mode=mode,
            config=self.config,
            output_dir=self.output_dir,
            findings=findings_payload,
        )
        self._connect_worker(self.worker)
        self.worker.start()

    def _on_apply_mask(self) -> None:
        if not self.findings:
            QMessageBox.warning(self, "RegCon", "Нет результатов сканирования.")
            return
        self._sync_table_to_findings()
        self._set_busy(True)
        self.progress.setValue(0)
        self.worker = Worker(
            files=self.files,
            mode="mask",
            config=self.config,
            output_dir=self.output_dir,
            findings=[f.to_dict() for f in self.findings],
        )
        self._connect_worker(self.worker)
        self.worker.start()

    def _on_scan_done(self, payload: list[dict[str, Any]]) -> None:
        self.findings = [Finding.from_dict(item) for item in payload]
        self._populate_table()
        self.apply_btn.setEnabled(bool(self.findings))
        self._append_log(f"Сканирование завершено. Совпадений: {len(self.findings)}")

    def _populate_table(self) -> None:
        display = self.findings[: self._table_limit]
        if len(self.findings) > self._table_limit:
            self._append_log(
                f"В таблице первые {self._table_limit} из {len(self.findings)} "
                "(все учитываются при маскировании)."
            )
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(display))
        for row, finding in enumerate(display):
            check = QTableWidgetItem()
            check.setFlags(_USER_CHECKABLE | _ENABLED)
            check.setCheckState(_CHECKED if finding.selected else _UNCHECKED)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(finding.match_type))
            self.table.setItem(
                row, 2, QTableWidgetItem(Path(finding.file_path).name)
            )
            loc = str(finding.line_no)
            if finding.cell:
                loc = f"{finding.line_no} ({finding.cell})"
            self.table.setItem(row, 3, QTableWidgetItem(loc))
            self.table.setItem(row, 4, QTableWidgetItem(finding.matched_text))
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)

    def _on_cell_changed(self, row: int, column: int) -> None:
        if column != 0 or row >= len(self.findings):
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        self.findings[row].selected = item.checkState() == _CHECKED

    def _sync_table_to_findings(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and row < len(self.findings):
                self.findings[row].selected = item.checkState() == _CHECKED

    def _set_all_findings(self, selected: bool) -> None:
        state = _CHECKED if selected else _UNCHECKED
        for finding in self.findings:
            finding.selected = selected
        self.table.blockSignals(True)
        rows = min(self.table.rowCount(), len(self.findings))
        for row in range(rows):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(state)
        self.table.blockSignals(False)

    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "Ошибка", message)

    def _on_worker_cancelled(self) -> None:
        self._set_busy(False)
        self.progress.setValue(0)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)
        self._append_log("Готово.")


def run_app() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
