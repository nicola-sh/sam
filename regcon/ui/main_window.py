from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from regcon.config.settings import load_config
from regcon.models import Finding
from regcon.ui.styles import APP_STYLESHEET
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
    _STRETCH = QHeaderView.ResizeMode.Stretch
else:
    _CHECKED = Qt.Checked
    _UNCHECKED = Qt.Unchecked
    _USER_CHECKABLE = Qt.ItemIsUserCheckable
    _ENABLED = Qt.ItemIsEnabled
    _STRETCH = QHeaderView.Stretch

_TYPE_SORT = {"PAN": 0, "IP": 1, "PASSWORD": 2}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RegCon")
        self.resize(1180, 700)
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
        self.config = load_config(config_path)
        self.files: list[str] = []
        self.findings: list[Finding] = []
        self._displayed_findings: list[Finding] = []
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
        root.setSpacing(6)
        root.setContentsMargins(10, 8, 10, 8)

        files_group = QGroupBox("Файлы")
        files_layout = QHBoxLayout(files_group)
        self.files_label = QLabel("Нет файлов")
        self.files_label.setWordWrap(True)
        self.files_label.setToolTip(
            "Перетащите файлы в окно или нажмите «Добавить»"
        )
        add_btn = QPushButton("Добавить")
        add_btn.setObjectName("secondaryBtn")
        add_btn.setToolTip("Выбрать .txt, .log, .csv, .xlsx …")
        add_btn.clicked.connect(self._browse_files)
        clear_btn = QPushButton("Очистить")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.clicked.connect(self._clear_files)
        files_layout.addWidget(self.files_label, stretch=1)
        files_layout.addWidget(add_btn)
        files_layout.addWidget(clear_btn)
        root.addWidget(files_group)

        search_group = QGroupBox("Искать")
        search_row = QHBoxLayout(search_group)
        pan_cfg = self.config.get("pan", {})
        ip_cfg = self.config.get("ip", {})
        pwd_cfg = self.config.get("passwords", {})
        self.chk_pan = QCheckBox("PAN")
        self.chk_pan.setChecked(pan_cfg.get("enabled", True))
        self.chk_pan.setToolTip("Номера карт, в т.ч. среди букв и символов (Luhn)")
        self.chk_ip = QCheckBox("IP")
        self.chk_ip.setChecked(ip_cfg.get("enabled", True))
        self.chk_ip.setToolTip("IPv4 и IPv6")
        self.chk_pwd = QCheckBox("Пароли")
        self.chk_pwd.setChecked(pwd_cfg.get("enabled", True))
        self.chk_pwd.setToolTip("password=, secret= и т.п.")
        search_row.addWidget(self.chk_pan)
        search_row.addWidget(self.chk_ip)
        search_row.addWidget(self.chk_pwd)
        search_row.addStretch()
        root.addWidget(search_group)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_mask_tab(), "Обезличивание")
        self.tabs.addTab(self._build_excel_tab(), "CSV → Excel")
        root.addWidget(self.tabs, stretch=1)

        out_row = QHBoxLayout()
        self.out_label = QLabel(str(Path.home() / "regcon-output"))
        self.out_label.setWordWrap(True)
        self.output_dir = str(Path.home() / "regcon-output")
        out_btn = QPushButton("Папка…")
        out_btn.setObjectName("secondaryBtn")
        out_btn.setToolTip("Куда сохранять результаты")
        out_btn.clicked.connect(self._browse_output)
        open_btn = QPushButton("Открыть")
        open_btn.setObjectName("secondaryBtn")
        open_btn.clicked.connect(self._open_output_dir)
        out_row.addWidget(QLabel("Результат:"))
        out_row.addWidget(self.out_label, stretch=1)
        out_row.addWidget(out_btn)
        out_row.addWidget(open_btn)
        root.addLayout(out_row)

        prog_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setFormat("%p%")
        self.progress_label = QLabel("—")
        self.progress_label.setObjectName("progressLabel")
        self.progress_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("Прервать текущую операцию")
        self.stop_btn.clicked.connect(self._on_stop)
        prog_row.addWidget(self.progress, stretch=1)
        prog_row.addWidget(self.progress_label)
        prog_row.addWidget(self.stop_btn)
        root.addLayout(prog_row)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(100)
        root.addWidget(self.log_view)

    def _build_mask_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        row1 = QHBoxLayout()
        self.btn_scan = QPushButton("① Найти")
        self.btn_scan.setToolTip(
            "Сканировать файлы и показать PAN, IP, пароли в таблице"
        )
        self.btn_scan.clicked.connect(self._on_scan)
        row1.addWidget(self.btn_scan)
        row1.addStretch()
        layout.addLayout(row1)

        tools = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все типы", "PAN", "IP", "PASSWORD"])
        self.filter_combo.setToolTip("Фильтр и сортировка таблицы по типу")
        self.filter_combo.currentIndexChanged.connect(self._populate_table)
        self.select_all_btn = QPushButton("Все")
        self.select_all_btn.setObjectName("secondaryBtn")
        self.select_all_btn.setToolTip("Отметить все видимые строки")
        self.select_all_btn.clicked.connect(lambda: self._set_all_findings(True))
        self.deselect_all_btn = QPushButton("Снять")
        self.deselect_all_btn.setObjectName("secondaryBtn")
        self.deselect_all_btn.clicked.connect(lambda: self._set_all_findings(False))
        self.findings_count_label = QLabel("0")
        tools.addWidget(QLabel("Показать:"))
        tools.addWidget(self.filter_combo)
        tools.addWidget(self.select_all_btn)
        tools.addWidget(self.deselect_all_btn)
        tools.addStretch()
        tools.addWidget(self.findings_count_label)
        layout.addLayout(tools)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "✓",
                "Тип",
                "Файл",
                "Строка",
                "…30 до",
                "Найдено",
                "30 после…",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(4, _STRETCH)
        header.setSectionResizeMode(5, _STRETCH)
        header.setSectionResizeMode(6, _STRETCH)
        self.table.setToolTip("Контекст ±30 символов вокруг совпадения")
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table, stretch=1)

        self.btn_save_masked = QPushButton("② Сохранить обезличенные копии")
        self.btn_save_masked.setEnabled(False)
        self.btn_save_masked.setToolTip(
            "Записать файлы с суффиксом _masked; исходники не трогаются"
        )
        self.btn_save_masked.clicked.connect(self._on_save_masked)
        layout.addWidget(self.btn_save_masked)
        return tab

    def _build_excel_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        self.chk_excel_json = QCheckBox("Форматировать JSON в ячейках")
        self.chk_excel_json.setChecked(
            self.config.get("json", {}).get("format_on_csv_export", True)
        )
        self.chk_excel_json.setToolTip(
            "JSON в CSV будет развёрнут в читаемый вид в Excel"
        )
        self.chk_excel_mask = QCheckBox("Сначала обезличить CSV")
        self.chk_excel_mask.setToolTip(
            "Поиск и маскирование перед конвертацией; "
            "если есть результаты на вкладке «Обезличивание» — только отмеченные"
        )
        layout.addWidget(self.chk_excel_json)
        layout.addWidget(self.chk_excel_mask)

        self.csv_info_label = QLabel("CSV: 0")
        layout.addWidget(self.csv_info_label)
        layout.addStretch()

        self.btn_excel = QPushButton("Создать Excel")
        self.btn_excel.setToolTip("Конвертировать все .csv из списка файлов")
        self.btn_excel.clicked.connect(self._on_create_excel)
        layout.addWidget(self.btn_excel)
        return tab

    def _sync_config_flags(self) -> None:
        self.config.setdefault("pan", {})["enabled"] = self.chk_pan.isChecked()
        self.config.setdefault("ip", {})["enabled"] = self.chk_ip.isChecked()
        self.config.setdefault("passwords", {})["enabled"] = self.chk_pwd.isChecked()

    def _filter_type_key(self) -> str | None:
        text = self.filter_combo.currentText()
        if text == "Все типы":
            return None
        return text

    def _filtered_sorted_findings(self) -> list[Finding]:
        ftype = self._filter_type_key()
        items = list(self.findings)
        if ftype:
            items = [f for f in items if f.match_type == ftype]
        items.sort(
            key=lambda f: (
                _TYPE_SORT.get(f.match_type, 9),
                Path(f.file_path).name.lower(),
                f.line_no,
                f.column,
            )
        )
        return items

    def _csv_files(self) -> list[str]:
        return [f for f in self.files if Path(f).suffix.lower() == ".csv"]

    def _update_csv_label(self) -> None:
        self.csv_info_label.setText(f"CSV: {len(self._csv_files())}")

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.toLocalFile() and Path(url.toLocalFile()).is_file()
        ]
        if paths:
            self._add_files(paths)
        event.acceptProposedAction()

    def _add_files(self, paths: list[str]) -> None:
        self.files = list(dict.fromkeys(self.files + paths))
        self.files_label.setText(
            f"{len(self.files)} файл(ов): "
            + ", ".join(Path(p).name for p in self.files[:5])
            + (" …" if len(self.files) > 5 else "")
        )
        self._update_csv_label()

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Файлы",
            str(Path.home()),
            "Логи (*.txt *.log *.csv *.xlsx *.xls *.json);;Все (*.*)",
        )
        if paths:
            self._add_files(paths)

    def _clear_files(self) -> None:
        self.files = []
        self.findings = []
        self._displayed_findings = []
        self.files_label.setText("Нет файлов")
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

    def _format_lines_progress(self, percent: int, done: int, total: int) -> None:
        self.progress.setValue(percent)
        self.progress_label.setText(f"{percent}%  ·  {done:,} / {total:,} строк")

    def _update_findings_label(self) -> None:
        n = len(self.findings)
        sel = sum(1 for f in self.findings if f.selected)
        shown = len(self._displayed_findings)
        extra = f", в таблице {shown}" if shown < n else ""
        self.findings_count_label.setText(f"всего {n}, отмечено {sel}{extra}")
        self.btn_save_masked.setEnabled(n > 0 and not self.stop_btn.isEnabled())

    def _set_busy(self, busy: bool) -> None:
        self.stop_btn.setEnabled(busy)
        self.btn_scan.setEnabled(not busy)
        self.btn_excel.setEnabled(not busy)
        self.tabs.setEnabled(not busy)
        self.chk_pan.setEnabled(not busy)
        self.chk_ip.setEnabled(not busy)
        self.chk_pwd.setEnabled(not busy)
        if busy:
            self.btn_save_masked.setEnabled(False)
        else:
            self._update_findings_label()

    def _connect_worker(self, worker: Worker) -> None:
        worker.progress.connect(self.progress.setValue)
        worker.progress_lines.connect(self._format_lines_progress)
        worker.log.connect(self._append_log)
        worker.error.connect(self._on_worker_error)
        worker.cancelled.connect(self._on_worker_cancelled)
        worker.scan_done.connect(self._on_scan_done)
        worker.finished_ok.connect(self._on_worker_finished)

    def _start_worker(self, **kwargs: Any) -> None:
        self.progress.setValue(0)
        self.progress_label.setText("0%  ·  подсчёт…")
        self._set_busy(True)
        self.worker = Worker(
            files=kwargs.get("files") or self.files,
            mode=kwargs["mode"],
            config=self.config,
            output_dir=self.output_dir,
            findings=kwargs.get("findings"),
            job_options=kwargs.get("job_options"),
        )
        self._connect_worker(self.worker)
        self.worker.start()

    def _on_stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()

    def _on_scan(self) -> None:
        if not self.files:
            QMessageBox.warning(self, "RegCon", "Добавьте файлы.")
            return
        self._sync_config_flags()
        self._start_worker(mode="scan")

    def _on_save_masked(self) -> None:
        if not self.findings:
            QMessageBox.warning(self, "RegCon", "Сначала нажмите «① Найти».")
            return
        self._sync_table_to_findings()
        if not any(f.selected for f in self.findings):
            QMessageBox.warning(self, "RegCon", "Отметьте совпадения в таблице.")
            return
        self._sync_config_flags()
        self._start_worker(
            mode="mask",
            findings=[f.to_dict() for f in self.findings],
        )

    def _on_create_excel(self) -> None:
        csv_list = self._csv_files()
        if not csv_list:
            QMessageBox.warning(self, "RegCon", "Нужен хотя бы один .csv файл.")
            return
        self._sync_config_flags()
        mask_before = self.chk_excel_mask.isChecked()
        use_existing = mask_before and bool(self.findings)
        if use_existing:
            self._sync_table_to_findings()
        self._start_worker(
            mode="csv2xlsx",
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

    def _populate_table(self) -> None:
        all_filtered = self._filtered_sorted_findings()
        if len(all_filtered) > self._table_limit:
            self._append_log(
                f"Показаны {self._table_limit} из {len(all_filtered)} "
                f"(фильтр: {self.filter_combo.currentText()})."
            )
        self._displayed_findings = all_filtered[: self._table_limit]
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._displayed_findings))
        for row, finding in enumerate(self._displayed_findings):
            check = QTableWidgetItem()
            check.setFlags(_USER_CHECKABLE | _ENABLED)
            check.setCheckState(_CHECKED if finding.selected else _UNCHECKED)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(finding.match_type))
            self.table.setItem(row, 2, QTableWidgetItem(Path(finding.file_path).name))
            loc = str(finding.line_no)
            if finding.cell:
                loc = f"{finding.line_no} · {finding.cell}"
            self.table.setItem(row, 3, QTableWidgetItem(loc))
            before = finding.context_before.replace("\n", " ").replace("\r", "")
            after = finding.context_after.replace("\n", " ").replace("\r", "")
            self.table.setItem(row, 4, QTableWidgetItem(before))
            self.table.setItem(row, 5, QTableWidgetItem(finding.matched_text))
            self.table.setItem(row, 6, QTableWidgetItem(after))
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        self._update_findings_label()

    def _on_cell_changed(self, row: int, column: int) -> None:
        if column != 0 or row >= len(self._displayed_findings):
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        self._displayed_findings[row].selected = item.checkState() == _CHECKED
        self._update_findings_label()

    def _sync_table_to_findings(self) -> None:
        for row in range(min(self.table.rowCount(), len(self._displayed_findings))):
            item = self.table.item(row, 0)
            if item:
                self._displayed_findings[row].selected = item.checkState() == _CHECKED

    def _set_all_findings(self, selected: bool) -> None:
        ftype = self._filter_type_key()
        state = _CHECKED if selected else _UNCHECKED
        for finding in self.findings:
            if ftype is None or finding.match_type == ftype:
                finding.selected = selected
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(state)
        self.table.blockSignals(False)
        self._update_findings_label()

    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        self.progress_label.setText("ошибка")
        QMessageBox.critical(self, "RegCon", message)

    def _on_worker_cancelled(self) -> None:
        self._set_busy(False)
        self.progress.setValue(0)
        self.progress_label.setText("остановлено")

    def _on_worker_finished(self) -> None:
        self._set_busy(False)
        self.progress_label.setText("100%  ·  готово")


def run_app() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
