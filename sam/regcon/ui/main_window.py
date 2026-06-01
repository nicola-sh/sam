from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sam.regcon.config.pan_prefixes import load_prefixes
from sam.regcon.config.settings import default_config_path, load_config, save_config
from sam.regcon.models import Finding
from sam.regcon.ui.pan_prefixes_dialog import PanPrefixesDialog
from sam.regcon.ui.styles import APP_STYLESHEET
from sam.regcon.util.app_paths import app_data_dir, default_output_dir, pan_prefix_path, ui_log_path
from sam.regcon.util.finding_groups import (
    FindingGroup,
    build_finding_groups,
    flatten_selected,
)
from sam.regcon.util.mask_preview import format_group_preview
from sam.regcon.util.privacy import redact_sensitive_text, wipe_findings
from sam.regcon.workers.worker import Worker

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
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
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
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
    _SELECT_ROWS = QTableWidget.SelectionBehavior.SelectRows
else:
    _CHECKED = Qt.Checked
    _UNCHECKED = Qt.Unchecked
    _USER_CHECKABLE = Qt.ItemIsUserCheckable
    _ENABLED = Qt.ItemIsEnabled
    _STRETCH = QHeaderView.Stretch
    _SELECT_ROWS = QTableWidget.SelectRows

_TYPE_SORT = {"PAN": 0, "IP": 1, "PASSWORD": 2}


class RegConWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.config_path = default_config_path()
        self.config = load_config(self.config_path)
        self.files: list[str] = []
        self.findings: list[Finding] = []
        self._groups: list[FindingGroup] = []
        self._displayed_groups: list[FindingGroup] = []
        self.worker: Worker | None = None
        self._purge_after_job = False
        self._page_size = int(
            self.config.get("regcon", {}).get("max_table_rows", 5000)
        )
        self._page_index = 0
        self._app_dir = app_data_dir()
        rc = self.config.get("regcon", {})
        last_out = str(rc.get("last_output_dir") or "").strip()
        self.output_dir = (
            last_out
            if last_out and Path(last_out).is_dir()
            else str(default_output_dir())
        )
        self.setAcceptDrops(True)
        self._build_ui()

    def _refresh_pan_tooltip(self) -> None:
        n = len(load_prefixes(self.config))
        self.chk_pan.setToolTip(
            f"PAN (префиксы: {n}). Кнопка «BIN» — справочник 8 цифр."
            if n
            else "Добавьте BIN через «BIN»"
        )

    def _edit_pan_prefixes(self) -> None:
        if PanPrefixesDialog(self.config, self).exec():
            self._refresh_pan_tooltip()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # --- файлы + детекторы ---
        row_files = QHBoxLayout()
        row_files.setSpacing(4)
        btn_add = QPushButton("+")
        btn_add.setObjectName("secondaryBtn")
        btn_add.setFixedWidth(28)
        btn_add.setToolTip("Добавить файлы")
        btn_add.clicked.connect(self._browse_files)
        btn_clr = QPushButton("×")
        btn_clr.setObjectName("secondaryBtn")
        btn_clr.setFixedWidth(28)
        btn_clr.setToolTip("Очистить")
        btn_clr.clicked.connect(self._clear_files)
        self.files_label = QLabel("Файлы: нет")
        self.files_label.setToolTip("Перетащите файлы в окно")
        pan_cfg = self.config.get("pan", {})
        self.chk_pan = QCheckBox("PAN")
        self.chk_pan.setChecked(pan_cfg.get("enabled", True))
        self._refresh_pan_tooltip()
        btn_bin = QPushButton("BIN")
        btn_bin.setObjectName("secondaryBtn")
        btn_bin.setFixedWidth(40)
        btn_bin.clicked.connect(self._edit_pan_prefixes)
        self.chk_ip = QCheckBox("IP")
        self.chk_ip.setChecked(self.config.get("ip", {}).get("enabled", True))
        self.chk_pwd = QCheckBox("Pwd")
        self.chk_pwd.setChecked(
            self.config.get("passwords", {}).get("enabled", True)
        )
        row_files.addWidget(btn_add)
        row_files.addWidget(btn_clr)
        row_files.addWidget(self.files_label, stretch=1)
        row_files.addWidget(self.chk_pan)
        row_files.addWidget(btn_bin)
        row_files.addWidget(self.chk_ip)
        row_files.addWidget(self.chk_pwd)
        root.addLayout(row_files)

        # --- действия ---
        row_act = QHBoxLayout()
        row_act.setSpacing(6)
        self.btn_scan = QPushButton("Скан")
        self.btn_scan.setToolTip("Найти чувствительные данные")
        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_save_masked = QPushButton("Маска →")
        self.btn_save_masked.setEnabled(False)
        self.btn_save_masked.setToolTip("Сохранить _masked для отмеченных")
        self.btn_save_masked.clicked.connect(self._on_save_masked)
        row_act.addWidget(self.btn_scan)
        row_act.addWidget(self.btn_save_masked)
        row_act.addStretch()
        root.addLayout(row_act)

        # --- фильтры таблицы ---
        row_tbl = QHBoxLayout()
        row_tbl.setSpacing(4)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все типы", "PAN", "IP", "PASSWORD"])
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.chk_only_selected = QCheckBox("К маске")
        self.chk_only_selected.setToolTip("Только отмеченные группы")
        self.chk_only_selected.toggled.connect(self._on_filter_changed)
        self.page_prev_btn = QPushButton("◀")
        self.page_prev_btn.setObjectName("secondaryBtn")
        self.page_prev_btn.setFixedWidth(30)
        self.page_prev_btn.clicked.connect(self._page_prev)
        self.page_label = QLabel("—")
        self.page_next_btn = QPushButton("▶")
        self.page_next_btn.setObjectName("secondaryBtn")
        self.page_next_btn.setFixedWidth(30)
        self.page_next_btn.clicked.connect(self._page_next)
        btn_all = QPushButton("Все")
        btn_all.setObjectName("secondaryBtn")
        btn_all.setFixedWidth(36)
        btn_all.setToolTip("Отметить видимые")
        btn_all.clicked.connect(lambda: self._set_visible_groups(True))
        btn_none = QPushButton("Нет")
        btn_none.setObjectName("secondaryBtn")
        btn_none.setFixedWidth(36)
        btn_none.setToolTip("Снять отметки на странице")
        btn_none.clicked.connect(lambda: self._set_visible_groups(False))
        self.findings_count_label = QLabel("0")
        row_tbl.addWidget(self.filter_combo)
        row_tbl.addWidget(self.chk_only_selected)
        row_tbl.addWidget(self.page_prev_btn)
        row_tbl.addWidget(self.page_label)
        row_tbl.addWidget(self.page_next_btn)
        row_tbl.addWidget(btn_all)
        row_tbl.addWidget(btn_none)
        row_tbl.addWidget(self.findings_count_label)
        root.addLayout(row_tbl)

        self.preview_label = QLabel(
            "Клик по строке — предпросмотр маски. Двойной клик — вкл/выкл."
        )
        self.preview_label.setObjectName("previewLabel")
        self.preview_label.setWordWrap(True)
        root.addWidget(self.preview_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["✓", "Тип", "Где", "Станет после маски", "×"]
        )
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(3, _STRETCH)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(_SELECT_ROWS)
        self.table.setAlternatingRowColors(True)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_row_double_click)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.table, stretch=1)

        # --- CSV / Excel (компактно) ---
        row_xl = QHBoxLayout()
        self.chk_excel_json = QCheckBox("JSON")
        self.chk_excel_json.setChecked(
            self.config.get("json", {}).get("format_on_csv_export", True)
        )
        self.chk_excel_mask = QCheckBox("Маска")
        self.chk_excel_mask.setToolTip("Только после скана и отметок")
        self.btn_excel = QPushButton("Excel")
        self.btn_excel.setObjectName("secondaryBtn")
        self.btn_excel.clicked.connect(self._on_create_excel)
        row_xl.addWidget(self.chk_excel_json)
        row_xl.addWidget(self.chk_excel_mask)
        row_xl.addWidget(self.btn_excel)
        row_xl.addStretch()
        root.addLayout(row_xl)

        # --- вывод + прогресс ---
        row_out = QHBoxLayout()
        row_out.setSpacing(4)
        btn_out = QPushButton("…")
        btn_out.setObjectName("secondaryBtn")
        btn_out.setFixedWidth(28)
        btn_out.clicked.connect(self._browse_output)
        btn_open = QPushButton("↗")
        btn_open.setObjectName("secondaryBtn")
        btn_open.setFixedWidth(28)
        btn_open.clicked.connect(self._open_output_dir)
        self.out_label = QLabel(Path(self.output_dir).name)
        self.out_label.setToolTip(self.output_dir)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(14)
        self.progress.setTextVisible(False)
        self.stop_btn = QPushButton("■")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setFixedWidth(32)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        row_out.addWidget(QLabel("→"))
        row_out.addWidget(self.out_label, stretch=1)
        row_out.addWidget(btn_out)
        row_out.addWidget(btn_open)
        row_out.addWidget(self.progress, stretch=2)
        row_out.addWidget(self.stop_btn)
        root.addLayout(row_out)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(48)
        root.addWidget(self.log_view)

    def _sync_config_flags(self) -> None:
        self.config.setdefault("pan", {})["enabled"] = self.chk_pan.isChecked()
        self.config.setdefault("ip", {})["enabled"] = self.chk_ip.isChecked()
        self.config.setdefault("passwords", {})["enabled"] = self.chk_pwd.isChecked()

    def _filter_type_key(self) -> str | None:
        text = self.filter_combo.currentText()
        if text == "Все типы":
            return None
        return text

    def _on_filter_changed(self) -> None:
        self._page_index = 0
        self._populate_table()

    def _total_pages(self, count: int) -> int:
        if count <= 0:
            return 1
        return (count + self._page_size - 1) // self._page_size

    def _page_prev(self) -> None:
        if self._page_index > 0:
            self._sync_table_to_groups()
            self._page_index -= 1
            self._populate_table()

    def _page_next(self) -> None:
        total = len(self._filtered_sorted_groups())
        if self._page_index < self._total_pages(total) - 1:
            self._sync_table_to_groups()
            self._page_index += 1
            self._populate_table()

    def _update_page_controls(self, total_items: int) -> None:
        pages = self._total_pages(total_items)
        if self._page_index >= pages:
            self._page_index = max(0, pages - 1)
        self.page_label.setText(
            f"{self._page_index + 1}/{pages}" if total_items else "—"
        )
        self.page_prev_btn.setEnabled(total_items > 0 and self._page_index > 0)
        self.page_next_btn.setEnabled(
            total_items > 0 and self._page_index < pages - 1
        )

    def _rebuild_groups(self) -> None:
        self._groups = build_finding_groups(self.findings)

    def _filtered_sorted_groups(self) -> list[FindingGroup]:
        ftype = self._filter_type_key()
        items = list(self._groups)
        if ftype:
            items = [g for g in items if g.head.match_type == ftype]
        if self.chk_only_selected.isChecked():
            items = [g for g in items if g.selected]
        items.sort(
            key=lambda g: (
                _TYPE_SORT.get(g.head.match_type, 9),
                Path(g.head.file_path).name.lower(),
                g.head.line_no,
                g.head.column,
            )
        )
        return items

    def _purge_session_findings(self) -> None:
        wipe_findings(self.findings)
        self._groups = []
        self._displayed_groups = []
        self.table.setRowCount(0)
        self._update_page_controls(0)
        self._update_findings_label()
        self.preview_label.setText("Клик по строке — предпросмотр маски.")
        self.log_view.clear()

    def _csv_files(self) -> list[str]:
        return [f for f in self.files if Path(f).suffix.lower() == ".csv"]

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
        names = ", ".join(Path(p).name for p in self.files[:3])
        extra = f" +{len(self.files) - 3}" if len(self.files) > 3 else ""
        self.files_label.setText(f"Файлы: {len(self.files)} — {names}{extra}")

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Файлы",
            str(Path.home()),
            "Логи (*.txt *.log *.csv *.xlsx);;Все (*.*)",
        )
        if paths:
            self._add_files(paths)

    def _clear_files(self) -> None:
        self.files = []
        self._purge_session_findings()
        self._page_index = 0
        self.files_label.setText("Файлы: нет")

    def hint_export_dir(self, path: str) -> None:
        folder = Path(path)
        if not folder.is_dir():
            return
        self.output_dir = str(folder)
        self.out_label.setText(folder.name)
        self.out_label.setToolTip(str(folder))

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Папка результатов", self.output_dir
        )
        if path:
            self.output_dir = path
            self.out_label.setText(Path(path).name)
            self.out_label.setToolTip(path)
            self._persist_settings()

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
        safe = redact_sensitive_text(message)
        self.log_view.append(safe)
        try:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            path = ui_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f"{stamp} {safe}\n")
        except OSError:
            pass

    def _format_status_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.progress.setToolTip(f"{percent}% — {message}")

    def _update_findings_label(self) -> None:
        n = len(self.findings)
        sel = sum(1 for f in self.findings if f.selected)
        to_mask = len([g for g in self._groups if g.selected])
        self.findings_count_label.setText(f"✓{sel}/{n} · {to_mask} гр.")
        self.btn_save_masked.setEnabled(n > 0 and not self.stop_btn.isEnabled())

    def _set_busy(self, busy: bool) -> None:
        self.stop_btn.setEnabled(busy)
        self.btn_scan.setEnabled(not busy)
        self.btn_excel.setEnabled(not busy)
        self.btn_save_masked.setEnabled(not busy and len(self.findings) > 0)
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
        worker.scan_truncated.connect(self._on_scan_truncated)
        worker.finished_ok.connect(self._on_worker_finished)

    def _persist_settings(self) -> None:
        self._sync_config_flags()
        self.config.setdefault("regcon", {})["last_output_dir"] = self.output_dir
        save_config(self.config, self.config_path)

    def shutdown(self) -> None:
        """Сохранить настройки и очистить память (вкладка SAM или закрытие окна)."""
        self._persist_settings()
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(30_000)
        self._purge_session_findings()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.shutdown()
        super().closeEvent(event)

    def _start_worker(self, **kwargs: Any) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(30_000)
        self.progress.setValue(0)
        self._set_busy(True)
        self.worker = Worker(
            files=kwargs.get("files") or self.files,
            mode=kwargs["mode"],
            config=self.config,
            output_dir=self.output_dir,
            data_dir=str(self._app_dir),
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
        if self.chk_pan.isChecked() and len(load_prefixes(self.config)) == 0:
            QMessageBox.warning(
                self,
                "RegCon",
                "Справочник BIN пуст. Кнопка «BIN» — первые 8 цифр.",
            )
            return
        self._start_worker(mode="scan")

    def _on_save_masked(self) -> None:
        if not self.findings:
            QMessageBox.warning(self, "RegCon", "Сначала «Скан».")
            return
        self._sync_table_to_groups()
        if not any(g.selected for g in self._groups):
            QMessageBox.warning(self, "RegCon", "Отметьте строки для маски.")
            return
        self._sync_config_flags()
        self._purge_after_job = bool(
            self.config.get("regcon", {}).get("purge_findings_after_mask", True)
        )
        self._start_worker(
            mode="mask",
            findings=[f.to_dict() for f in flatten_selected(self._groups)],
        )

    def _on_create_excel(self) -> None:
        csv_list = self._csv_files()
        if not csv_list:
            QMessageBox.warning(self, "RegCon", "Нужен .csv в списке файлов.")
            return
        self._sync_config_flags()
        mask_before = self.chk_excel_mask.isChecked()
        if mask_before and not self.findings:
            QMessageBox.warning(
                self,
                "RegCon",
                "Сначала «Скан» и отметьте строки.",
            )
            return
        use_existing = mask_before and bool(self.findings)
        if use_existing:
            self._sync_table_to_groups()
            if not any(g.selected for g in self._groups):
                QMessageBox.warning(self, "RegCon", "Отметьте строки.")
                return
        if mask_before and use_existing:
            self._purge_after_job = bool(
                self.config.get("regcon", {}).get("purge_findings_after_mask", True)
            )
        selected = flatten_selected(self._groups) if use_existing else []
        self._start_worker(
            mode="csv2xlsx",
            files=csv_list,
            job_options={
                "mask_before": mask_before,
                "format_json_cells": self.chk_excel_json.isChecked(),
                "use_existing_findings": use_existing,
            },
            findings=[f.to_dict() for f in selected] if use_existing else None,
        )

    def _on_scan_done(self, payload: list[dict[str, Any]]) -> None:
        wipe_findings(self.findings)
        self.findings = [Finding.from_dict(item) for item in payload]
        self._rebuild_groups()
        self._page_index = 0
        self.chk_only_selected.setChecked(False)
        self._populate_table()
        self._append_log(f"Найдено: {len(self.findings)} ({len(self._groups)} гр.)")

    def _on_scan_truncated(self, count: int, limit: int) -> None:
        QMessageBox.warning(
            self,
            "RegCon",
            f"Лимит {limit}. Показано {count}. Разбейте файлы или ужесточите фильтры.",
        )

    def _populate_table(self) -> None:
        all_filtered = self._filtered_sorted_groups()
        self._update_page_controls(len(all_filtered))
        start = self._page_index * self._page_size
        self._displayed_groups = all_filtered[start : start + self._page_size]
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._displayed_groups))
        for row, group in enumerate(self._displayed_groups):
            finding = group.head
            check = QTableWidgetItem()
            check.setFlags(_USER_CHECKABLE | _ENABLED)
            check.setCheckState(_CHECKED if group.selected else _UNCHECKED)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(finding.match_type))
            where = Path(finding.file_path).name
            loc = f"{finding.line_no}"
            if finding.cell:
                loc = f"{finding.line_no}:{finding.cell}"
            self.table.setItem(row, 2, QTableWidgetItem(f"{where} · {loc}"))
            preview_item = QTableWidgetItem(
                format_group_preview(group, self.config)
            )
            preview_item.setToolTip(
                "Как изменится фрагмент. Двойной клик — снять/поставить ✓"
            )
            self.table.setItem(row, 3, preview_item)
            self.table.setItem(row, 4, QTableWidgetItem(str(group.count)))
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        self._update_findings_label()
        if self._displayed_groups:
            self.table.selectRow(0)

    def _on_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._displayed_groups):
            return
        group = self._displayed_groups[row]
        mark = "✓ к маске" if group.selected else "○ пропуск"
        self.preview_label.setText(
            f"{mark} · {format_group_preview(group, self.config)}"
        )

    def _on_row_double_click(self, row: int, _col: int) -> None:
        if row >= len(self._displayed_groups):
            return
        group = self._displayed_groups[row]
        group.selected = not group.selected
        group.sync_selection_to_items()
        item = self.table.item(row, 0)
        if item:
            self.table.blockSignals(True)
            item.setCheckState(_CHECKED if group.selected else _UNCHECKED)
            self.table.blockSignals(False)
        self._on_selection_changed()
        self._update_findings_label()

    def _on_cell_changed(self, row: int, column: int) -> None:
        if column != 0 or row >= len(self._displayed_groups):
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        self._displayed_groups[row].selected = item.checkState() == _CHECKED
        self._displayed_groups[row].sync_selection_to_items()
        self._on_selection_changed()
        self._update_findings_label()

    def _sync_table_to_groups(self) -> None:
        for row in range(min(self.table.rowCount(), len(self._displayed_groups))):
            item = self.table.item(row, 0)
            if item:
                self._displayed_groups[row].selected = item.checkState() == _CHECKED
                self._displayed_groups[row].sync_selection_to_items()

    def _set_visible_groups(self, selected: bool) -> None:
        state = _CHECKED if selected else _UNCHECKED
        for group in self._displayed_groups:
            group.selected = selected
            group.sync_selection_to_items()
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
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

    def _on_worker_finished(self) -> None:
        self._set_busy(False)
        if self.progress.value() < 100:
            self.progress.setValue(100)
        if self._purge_after_job:
            self._purge_session_findings()
            self._purge_after_job = False
            self._append_log("Очищено из памяти.")


# Совместимость со старым импортом
MainWindow = RegConWidget


class _RegConStandaloneWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RegCon")
        self.resize(960, 580)
        self._panel = RegConWidget()
        self.setCentralWidget(self._panel)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._panel.shutdown()
        super().closeEvent(event)


def run_standalone() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = _RegConStandaloneWindow()
    window.show()
    sys.exit(app.exec())


def run_app() -> None:
    run_standalone()


if __name__ == "__main__":
    run_standalone()
