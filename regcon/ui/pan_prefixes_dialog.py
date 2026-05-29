from __future__ import annotations

from pathlib import Path
from typing import Any

from regcon.config.pan_prefixes import (
    DEFAULT_PREFIX_LEN,
    load_prefixes_from_file,
    load_prefixes_from_text,
    prefixes_to_text,
)
from regcon.config.settings import save_config

try:
    from PyQt6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
    )
except ImportError:  # pragma: no cover
    from PyQt5.QtWidgets import (  # type: ignore
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
    )


class PanPrefixesDialog(QDialog):
    """Редактор первых 8 цифр PAN — сохраняется в config.yaml."""

    def __init__(
        self,
        config: dict[str, Any],
        config_path: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.config_path = config_path
        self.prefix_len = int(
            config.get("pan", {}).get("prefix_digits", DEFAULT_PREFIX_LEN)
        )
        self.setWindowTitle("Префиксы PAN")
        self.resize(420, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"Первые {self.prefix_len} цифр номера — по одной строке.\n"
                "Сохраняется в config.yaml (pan.prefix_list)."
            )
        )

        self.editor = QTextEdit()
        pan_cfg = config.setdefault("pan", {})
        current = pan_cfg.get("prefix_list", [])
        self.editor.setPlainText(prefixes_to_text([str(p) for p in current]))
        self.editor.setPlaceholderText("91123912\n41111111")
        layout.addWidget(self.editor)

        import_row = QHBoxLayout()
        import_btn = QPushButton("Импорт из .txt…")
        import_btn.clicked.connect(self._import_txt)
        import_row.addWidget(import_btn)
        import_row.addStretch()
        layout.addLayout(import_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _import_txt(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт префиксов", str(Path.home()), "Текст (*.txt)"
        )
        if not path:
            return
        items = load_prefixes_from_file(Path(path), self.prefix_len)
        if items:
            self.editor.setPlainText(prefixes_to_text(items))

    def _save(self) -> None:
        items = load_prefixes_from_text(
            self.editor.toPlainText(), self.prefix_len
        )
        self.config.setdefault("pan", {})["prefix_list"] = items
        save_config(self.config, self.config_path)
        self.accept()

    def prefix_count(self) -> int:
        return len(
            load_prefixes_from_text(self.editor.toPlainText(), self.prefix_len)
        )
