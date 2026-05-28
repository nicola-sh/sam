from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from regcon.config.pan_prefixes import resolve_prefix_path
from regcon.config.settings import load_config
from regcon.models import Finding
from regcon.util.pan_prefix_index import build_prefix_index
from regcon.ui.styles import APP_STYLESHEET
from regcon.workers.worker import Worker

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
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
        QFrame,
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
        self.resize(1024, 620)
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

    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine if _PYQT6 else QFrame.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken if _PYQT6 else QFrame.Sunken)
        return line

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(4)
        root.setContentsMargins(8, 6, 8, 6)

        top = QHBoxLayout()
        top.setSpacing(6)
        add_btn = QPushButton("+ Файлы")
        add_btn.setObjectName("secondaryBtn")
        add_btn.setToolTip("Выбрать .txt, .log, .csv, .xlsx …")
        add_btn.clicked.connect(self._browse_files)
        clear_btn = QPushButton("×")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.setFixedWidth(32)
        clear_btn.setToolTip("Очистить список")
        clear_btn.clicked.connect(self._clear_files)
        self.files_label = QLabel("Нет файлов")
        self.files_label.setWordWrap(True)
        self.files_label.setToolTip("Перетащите файлы в окно")
        pan_cfg = self.config.get("pan", {})
        ip_cfg = self.config.get("ip", {})
        pwd_cfg = self.config.get("passwords", {})
        self.chk_pan = QCheckBox("PAN")
        self.chk_pan.setChecked(pan_cfg.get("enabled", True))
        prefix_path = resolve_prefix_path(self.config)
        prefix_n = build_prefix_index(
            prefix_path, ()
        ).count
        pan_tip = "Карты (Luhn); в таблице только цифры"
        if prefix_n:
            pan_tip += f"; префиксов: {prefix_n} ({prefix_path.name})"
        self.chk_pan.setToolTip(pan_tip)
        self.chk_ip = QCheckBox("IP")
        self.chk_ip.setChecked(ip_cfg.get("enabled", True))
        self.chk_pwd = QCheckBox("Пароли")
        self.chk_pwd.setChecked(pwd_cfg.get("enabled", True))
        top.addWidget(add_btn)
        top.addWidget(clear_btn)
        top.addWidget(self.files_label, stretch=1)
        top.addWidget(self.chk_pan)
        top.addWidget(self.chk_ip)
        top.addWidget(self.chk_pwd)
        root.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_mask_tab(), "Обезличивание")
        self.tabs.addTab(self._build_excel_tab(), "CSV → Excel")
        root.addWidget(self.tabs, stretch=1)

        root.addWidget(self._hline())

        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        out_btn = QPushButton("…")
        out_btn.setObjectName("secondaryBtn")
        out_btn.setFixedWidth(32)
        out_btn.setToolTip("Папка результатов")
        out_btn.clicked.connect(self._browse_output)
        open_btn = QPushButton("↗")
        open_btn.setObjectName("secondaryBtn")
        open_btn.setFixedWidth(32)
        open_btn.setToolTip("Открыть папку")
        open_btn.clicked.connect(self._open_output_dir)
        self.out_label = QLabel(str(Path.home() / "regcon-output"))
        self.output_dir = str(Path.home() / "regcon-output")
        self.out_label.setToolTip(self.output_dir)
        out_row.addWidget(QLabel("→"))
        out_row.addWidget(self.out_label, stretch=1)
        out_row.addWidget(out_btn)
        out_row.addWidget(open_btn)
        root.addLayout(out_row)

        prog_row = QHBoxLayout()
        prog_row.setSpacing(6)
        self.progress = QProgressBar()
        self.progress.setFormat("%p%")
        self.progress.setFixedHeight(18)
        self.progress_label = QLabel("—")
        self.progress_label.setObjectName("progressLabel")
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        prog_row.addWidget(self.progress, stretch=1)
        prog_row.addWidget(self.progress_label)
        prog_row.addWidget(self.stop_btn)
        root.addLayout(prog_row)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(72)
        root.addWidget(self.log_view)

    def _build_mask_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        row1 = QHBoxLayout()
        self.btn_scan = QPushButton("Найти")
        self.btn_scan.setToolTip("Сканировать и показать совпадения")
        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_save_masked = QPushButton("Сохранить _masked")
        self.btn_save_masked.setEnabled(False)
        self.btn_save_masked.setToolTip("Обезличить отмеченные строки")
        self.btn_save_masked.clicked.connect(self._on_save_masked)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все", "PAN", "IP", "PASSWORD"])
        self.filter_combo.setToolTip("Фильтр таблицы")
        self.filter_combo.currentIndexChanged.connect(self._populate_table)
        self.select_all_btn = QPushButton("✓")
        self.select_all_btn.setObjectName("secondaryBtn")
        self.select_all_btn.setFixedWidth(36)
        self.select_all_btn.setToolTip("Отметить все видимые")
        self.select_all_btn.clicked.connect(lambda: self._set_all_findings(True))
        self.deselect_all_btn = QPushButton("○")
        self.deselect_all_btn.setObjectName("secondaryBtn")
        self.deselect_all_btn.setFixedWidth(36)
        self.deselect_all_btn.setToolTip("Снять отметки")
        self.deselect_all_btn.clicked.connect(lambda: self._set_all_findings(False))
        self.findings_count_label = QLabel("0")
        row1.addWidget(self.btn_scan)
        row1.addWidget(self.btn_save_masked)
        row1.addStretch()
        row1.addWidget(QLabel("Фильтр:"))
        row1.addWidget(self.filter_combo)
        row1.addWidget(self.select_all_btn)
        row1.addWidget(self.deselect_all_btn)
        row1.addWidget(self.findings_count_label)
        layout.addLayout(row1)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["✓", "Тип", "Файл", "Стр.", "…30", "Найдено", "30…"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, _STRETCH)
        header.setSectionResizeMode(4, _STRETCH)
        header.setSectionResizeMode(5, _STRETCH)
        header.setSectionResizeMode(6, _STRETCH)
        self.table.verticalHeader().setVisible(False)
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table, stretch=1)
        return tab

    def _build_excel_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        opts = QHBoxLayout()
        self.chk_excel_json = QCheckBox("JSON в ячейках")
        self.chk_excel_json.setChecked(
            self.config.get("json", {}).get("format_on_csv_export", True)
        )
        self.chk_excel_mask = QCheckBox("Сначала обезличить")
        self.chk_excel_mask.setToolTip(
            "Маскирование перед Excel; иначе — только отмеченные с вкладки «Обезличивание»"
        )
        opts.addWidget(self.chk_excel_json)
        opts.addWidget(self.chk_excel_mask)
        opts.addStretch()
        layout.addLayout(opts)

        self.csv_info_label = QLabel("CSV в списке: 0")
        layout.addWidget(self.csv_info_label)
        layout.addStretch()

        self.btn_excel = QPushButton("Создать Excel")
        self.btn_excel.clicked.connect(self._on_create_excel)
        layout.addWidget(self.btn_excel)
        return tab

    def _sync_config_flags(self) -> None:
        self.config.setdefault("pan", {})["enabled"] = self.chk_pan.isChecked()
        self.config.setdefault("ip", {})["enabled"] = self.chk_ip.isChecked()
        self.config.setdefault("passwords", {})["enabled"] = self.chk_pwd.isChecked()

    def _filter_type_key(self) -> str | None:
        text = self.filter_combo.currentText()
        if text == "Все":
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
        self.csv_info_label.setText(f"CSV в списке: {len(self._csv_files())}")

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
        names = ", ".join(Path(p).name for p in self.files[:4])
        extra = f" +{len(self.files) - 4}" if len(self.files) > 4 else ""
        self.files_label.setText(f"{len(self.files)}: {names}{extra}")
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
            self.out_label.setToolTip(path)

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

    def _format_status_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.progress_label.setText(f"{percent}% · {message}")

    def _update_findings_label(self) -> None:
        n = len(self.findings)
        sel = sum(1 for f in self.findings if f.selected)
        shown = len(self._displayed_findings)
        extra = f" / {shown}" if shown < n else ""
        self.findings_count_label.setText(f"{sel}/{n}{extra}")
        self.btn_save_masked.setEnabled(n > 0 and not self.stop_btn.isEnabled())

    def _set_busy(self, busy: bool) -> None:
        self.stop_btn.setEnabled(busy)
        self.btn_scan.setEnabled(not busy)
        self.btn_excel.setEnabled(not busy)
        self.btn_save_masked.setEnabled(not busy and len(self.findings) > 0)
        self.tabs.setEnabled(not busy)
        self.chk_pan.setEnabled(not busy)
        self.chk_ip.setEnabled(not busy)
        self.chk_pwd.setEnabled(not busy)
        if not busy:
            self._update_findings_label()

    def _connect_worker(self, worker: Worker) -> None:
        worker.progress.connect(self.progress.setValue)
        worker.progress_status.connect(self._format_status_progress)
        worker.log.connect(self._append_log)
        worker.error.connect(self._on_worker_error)
        worker.cancelled.connect(self._on_worker_cancelled)
        worker.scan_done.connect(self._on_scan_done)
        worker.finished_ok.connect(self._on_worker_finished)

    def _start_worker(self, **kwargs: Any) -> None:
        self.progress.setValue(0)
        self.progress_label.setText("0% · …")
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
            QMessageBox.warning(self, "RegCon", "Сначала «Найти».")
            return
        self._sync_table_to_findings()
        if not any(f.selected for f in self.findings):
            QMessageBox.warning(self, "RegCon", "Отметьте совпадения.")
            return
        self._sync_config_flags()
        self._start_worker(
            mode="mask",
            findings=[f.to_dict() for f in self.findings],
        )

    def _on_create_excel(self) -> None:
        csv_list = self._csv_files()
        if not csv_list:
            QMessageBox.warning(self, "RegCon", "Нужен хотя бы один .csv.")
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
                f"Таблица: {self._table_limit} из {len(all_filtered)} "
                f"({self.filter_combo.currentText()})."
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
                loc = f"{finding.line_no}:{finding.cell}"
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
        if self.progress.value() < 100:
            self.progress.setValue(100)
        self.progress_label.setText("готово")


def run_app() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
