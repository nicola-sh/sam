from __future__ import annotations

from pathlib import Path
from typing import Callable

try:
    from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
except ImportError:  # pragma: no cover
    from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget  # type: ignore


class RegConTabHost(QWidget):
    """Ленивая вкладка RegCon: тяжёлые импорты только при первом открытии."""

    def __init__(
        self,
        *,
        export_dir_provider: Callable[[], str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._export_dir_provider = export_dir_provider
        self._panel = None
        self._loaded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel("Загрузка модуля обезличивания…")
        self._placeholder.setObjectName("hintLabel")
        layout.addWidget(self._placeholder)

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        from sam.regcon.ui.main_window import RegConWidget
        from sam.regcon.ui.styles import APP_STYLESHEET as REGCON_STYLES

        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:  # pragma: no cover
            from PyQt5.QtWidgets import QApplication  # type: ignore

        app = QApplication.instance()
        if app is not None:
            base = app.styleSheet() or ""
            if "RegCon" not in base:
                app.setStyleSheet(base + "\n" + REGCON_STYLES)

        layout = self.layout()
        layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._panel = RegConWidget(parent=self)
        layout.addWidget(self._panel)

        export = (self._export_dir_provider() or "").strip() if self._export_dir_provider else ""
        if export and Path(export).is_dir():
            self._panel.hint_export_dir(export)

    def shutdown(self) -> None:
        if self._panel is not None:
            self._panel.shutdown()

    def open_export_folder(self, path: str) -> None:
        self.ensure_loaded()
        if self._panel is not None:
            self._panel.hint_export_dir(path)
