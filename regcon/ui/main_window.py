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
        QTabWidget,
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
        QTabWidget,
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
    """Интерфейс: две задачи — обезличивание логов и CSV → Excel."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RegCon — подготовка логов")
        self.resize(1100, 760)
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
        root.setSpacing(10)

        # --- Файлы ---
        files_group = QGroupBox("1. Файлы")
        files_layout = QVBoxLayout(files_group)
        drop_hint = QLabel(
            "Перетащите файлы сюда или нажмите «Добавить файлы…»"
        )
        drop_hint.setStyleSheet("color: #444;")
        files_layout.addWidget(drop_hint)
        files_row = QHBoxLayout()
        self.files_label = QLabel("Файлы не выбраны")
        self.files_label.setWordWrap(True)
        add_btn = QPushButton("Добавить файлы…")
        add_btn.clicked.connect(self._browse_files)
        clear_btn = QPushButton("Очистить список")
        clear_btn.clicked.connect(self._clear_files)
        files_row.addWidget(self.files_label, stretch=1)
        files_row.addWidget(add_btn)
        files_row.addWidget(clear_btn)
        files_layout.addLayout(files_row)
        root.addWidget(files_group)

        # --- Что искать (общее) ---
        search_group = QGroupBox("Что искать в файлах")
        search_row = QHBoxLayout(search_group)
        pan_cfg = self.config.get("pan", {})
        ip_cfg = self.config.get("ip", {})
        pwd_cfg = self.config.get("passwords", {})
        self.chk_pan = QCheckBox("Номера карт (PAN)")
        self.chk_pan.setChecked(pan_cfg.get("enabled", True))
        self.chk_ip = QCheckBox("IP-адреса")
        self.chk_ip.setChecked(ip_cfg.get("enabled", True))
        self.chk_pwd = QCheckBox("Пароли и секреты")
        self.chk_pwd.setChecked(pwd_cfg.get("enabled", True))
        search_row.addWidget(self.chk_pan)
        search_row.addWidget(self.chk_ip)
        search_row.addWidget(self.chk_pwd)
        search_row.addStretch()
        root.addWidget(search_group)

        # --- Вкладки задач ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_mask_tab(), "Обезличивание логов")
        self.tabs.addTab(self._build_excel_tab(), "CSV → Excel")
        root.addWidget(self.tabs, stretch=1)

        # --- Выход и управление ---
        out_group = QGroupBox("Папка результатов")
        out_row = QHBoxLayout(out_group)
        default_out = str(Path.home() / "regcon-output")
        self.output_dir = default_out
        self.out_label = QLabel(default_out)
        self.out_label.setWordWrap(True)
        out_btn = QPushButton("Изменить…")
        out_btn.clicked.connect(self._browse_output)
        open_btn = QPushButton("Открыть папку")
        open_btn.clicked.connect(self._open_output_dir)
        out_row.addWidget(self.out_label, stretch=1)
        out_row.addWidget(out_btn)
        out_row.addWidget(open_btn)
        root.addWidget(out_group)

        ctrl_row = QHBoxLayout()
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        ctrl_row.addWidget(self.stop_btn)
        ctrl_row.addStretch()
        root.addLayout(ctrl_row)

        self.progress = QProgressBar()
        root.addWidget(self.progress)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        root.addWidget(self.log_view)

    def _build_mask_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        hint = QLabel(
            "Шаг 1 — найдите чувствительные данные.\n"
            "Шаг 2 — отметьте в таблице, что заменить, и сохраните копии файлов.\n"
            "Исходники не изменяются."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #333; padding: 4px;")
        layout.addWidget(hint)

        step1_row = QHBoxLayout()
        self.btn_scan = QPushButton("① Найти чувствительные данные")
        self.btn_scan.setMinimumHeight(36)
        self.btn_scan.clicked.connect(self._on_scan)
        step1_row.addWidget(self.btn_scan)
        step1_row.addStretch()
        layout.addLayout(step1_row)

        table_tools = QHBoxLayout()
        self.select_all_btn = QPushButton("Выбрать все")
        self.select_all_btn.clicked.connect(lambda: self._set_all_findings(True))
        self.deselect_all_btn = QPushButton("Снять все")
        self.deselect_all_btn.clicked.connect(lambda: self._set_all_findings(False))
        self.findings_count_label = QLabel("Совпадений: 0")
        table_tools.addWidget(self.select_all_btn)
        table_tools.addWidget(self.deselect_all_btn)
        table_tools.addStretch()
        table_tools.addWidget(self.findings_count_label)
        layout.addLayout(table_tools)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Заменить", "Тип", "Файл", "Место", "Найденный текст"]
        )
        self.table.horizontalHeader().setSectionResizeMode(4, _STRETCH)
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table, stretch=1)

        self.btn_save_masked = QPushButton("② Сохранить обезличенные копии")
        self.btn_save_masked.setMinimumHeight(40)
        self.btn_save_masked.setEnabled(False)
        self.btn_save_masked.clicked.connect(self._on_save_masked)
        layout.addWidget(self.btn_save_masked)

        return tab

    def _build_excel_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        hint = QLabel(
            "Конвертирует CSV в Excel с оформленной таблицей.\n"
            "Работают только файлы с расширением .csv из списка выше."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #333; padding: 4px;")
        layout.addWidget(hint)

        opts = QGroupBox("Параметры конвертации")
        opts_layout = QVBoxLayout(opts)

        self.chk_excel_json = QCheckBox("Форматировать JSON в ячейках")
        self.chk_excel_json.setChecked(
            self.config.get("json", {}).get("format_on_csv_export", True)
        )
        self.chk_excel_json.setToolTip(
            "Если в ячейке CSV лежит JSON — в Excel он будет с отступами и переносами"
        )
        opts_layout.addWidget(self.chk_excel_json)

        self.chk_excel_mask = QCheckBox(
            "Сначала обезличить CSV (PAN, IP, пароли — по галочкам выше)"
        )
        self.chk_excel_mask.setToolTip(
            "Если вы уже искали данные на вкладке «Обезличивание», "
            "будут использованы отмеченные в таблице совпадения. "
            "Иначе — поиск и замена всех найденных автоматически."
        )
        opts_layout.addWidget(self.chk_excel_mask)

        layout.addWidget(opts)

        self.csv_info_label = QLabel("CSV в списке: 0")
        layout.addWidget(self.csv_info_label)

        layout.addStretch()

        self.btn_excel = QPushButton("Создать Excel")
        self.btn_excel.setMinimumHeight(44)
        self.btn_excel.clicked.connect(self._on_create_excel)
        layout.addWidget(self.btn_excel)

        return tab

    def _sync_config_flags(self) -> None:
        self.config.setdefault("pan", {})["enabled"] = self.chk_pan.isChecked()
        self.config.setdefault("ip", {})["enabled"] = self.chk_ip.isChecked()
        self.config.setdefault("passwords", {})["enabled"] = self.chk_pwd.isChecked()

    def _csv_files(self) -> list[str]:
        return [f for f in self.files if Path(f).suffix.lower() == ".csv"]

    def _update_csv_label(self) -> None:
        count = len(self._csv_files())
        self.csv_info_label.setText(
            f"CSV в списке: {count}"
            + ("" if count else " — добавьте .csv файлы в блок «Файлы»")
        )

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
            f"Выбрано: {len(merged)} — "
            + ", ".join(Path(p).name for p in merged[:6])
            + (" …" if len(merged) > 6 else "")
        )
        self._update_csv_label()

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Добавить файлы",
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
        self._update_findings_label()
        self._update_csv_label()

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Папка результатов", self.output_dir)
        if path:
            self.output_dir = path
            self.out_label.setText(path)

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

    def _update_findings_label(self) -> None:
        n = len(self.findings)
        selected = sum(1 for f in self.findings if f.selected)
        self.findings_count_label.setText(f"Совпадений: {n} (отмечено: {selected})")
        self.btn_save_masked.setEnabled(n > 0)

    def _set_busy(self, busy: bool) -> None:
        self.stop_btn.setEnabled(busy)
        self.btn_scan.setEnabled(not busy)
        self.btn_save_masked.setEnabled((not busy) and bool(self.findings))
        self.btn_excel.setEnabled(not busy)
        self.tabs.setEnabled(not busy)
        self.chk_pan.setEnabled(not busy)
        self.chk_ip.setEnabled(not busy)
        self.chk_pwd.setEnabled(not busy)

    def _connect_worker(self, worker: Worker) -> None:
        worker.progress.connect(self.progress.setValue)
        worker.log.connect(self._append_log)
        worker.error.connect(self._on_worker_error)
        worker.cancelled.connect(self._on_worker_cancelled)
        worker.scan_done.connect(self._on_scan_done)
        worker.finished_ok.connect(self._on_worker_finished)

    def _start_worker(
        self,
        mode: str,
        files: list[str] | None = None,
        findings: list[dict[str, Any]] | None = None,
        job_options: dict[str, Any] | None = None,
    ) -> None:
        self.progress.setValue(0)
        self._set_busy(True)
        self.worker = Worker(
            files=files or self.files,
            mode=mode,
            config=self.config,
            output_dir=self.output_dir,
            findings=findings,
            job_options=job_options,
        )
        self._connect_worker(self.worker)
        self.worker.start()

    def _on_stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self._append_log("Остановка…")
            self.worker.requestInterruption()

    def _on_scan(self) -> None:
        if not self.files:
            QMessageBox.warning(self, "RegCon", "Сначала добавьте файлы.")
            return
        self._sync_config_flags()
        self._append_log("——— Поиск чувствительных данных ———")
        self._start_worker("scan")

    def _on_save_masked(self) -> None:
        if not self.findings:
            QMessageBox.warning(
                self,
                "RegCon",
                "Сначала нажмите «Найти чувствительные данные».",
            )
            return
        self._sync_table_to_findings()
        selected = sum(1 for f in self.findings if f.selected)
        if selected == 0:
            QMessageBox.warning(self, "RegCon", "Отметьте хотя бы одно совпадение в таблице.")
            return
        self._sync_config_flags()
        self._append_log("——— Сохранение обезличенных копий ———")
        self._start_worker(
            "mask",
            findings=[f.to_dict() for f in self.findings],
        )

    def _on_create_excel(self) -> None:
        csv_list = self._csv_files()
        if not csv_list:
            QMessageBox.warning(
                self,
                "RegCon",
                "Добавьте хотя бы один файл .csv в блок «Файлы».",
            )
            return
        self._sync_config_flags()
        mask_before = self.chk_excel_mask.isChecked()
        use_existing = mask_before and bool(self.findings)
        if mask_before and use_existing:
            self._sync_table_to_findings()

        self._append_log("——— Конвертация CSV → Excel ———")
        self._start_worker(
            "csv2xlsx",
            files=csv_list,
            job_options={
                "mask_before": mask_before,
                "format_json_cells": self.chk_excel_json.isChecked(),
                "use_existing_findings": use_existing,
            },
            findings=[f.to_dict() for f in self.findings] if use_existing else None,
        )

    def _on_scan_done(self, payload: list[dict[str, Any]]) -> None:
        self.findings = [Finding.from_dict(item) for item in payload]
        self._populate_table()
        self._update_findings_label()
        self.tabs.setCurrentIndex(0)
        self._append_log(
            f"Поиск завершён. Найдено: {len(self.findings)}. "
            "Проверьте таблицу и нажмите «Сохранить обезличенные копии»."
        )

    def _populate_table(self) -> None:
        display = self.findings[: self._table_limit]
        if len(self.findings) > self._table_limit:
            self._append_log(
                f"В таблице показаны первые {self._table_limit} из {len(self.findings)}. "
                "При сохранении учитываются все."
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
            self.table.setItem(row, 2, QTableWidgetItem(Path(finding.file_path).name))
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
        self._update_findings_label()

    def _sync_table_to_findings(self) -> None:
        rows = min(self.table.rowCount(), len(self.findings))
        for row in range(rows):
            item = self.table.item(row, 0)
            if item:
                self.findings[row].selected = item.checkState() == _CHECKED

    def _set_all_findings(self, selected: bool) -> None:
        for finding in self.findings:
            finding.selected = selected
        state = _CHECKED if selected else _UNCHECKED
        self.table.blockSignals(True)
        for row in range(min(self.table.rowCount(), len(self.findings))):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(state)
        self.table.blockSignals(False)
        self._update_findings_label()

    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "RegCon", message)

    def _on_worker_cancelled(self) -> None:
        self._set_busy(False)
        self.progress.setValue(0)
        self._update_findings_label()
        self.btn_save_masked.setEnabled(bool(self.findings))

    def _on_worker_finished(self) -> None:
        self._set_busy(False)
        self._update_findings_label()
        self._append_log("Готово. Результаты в папке выхода.")


def run_app() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
