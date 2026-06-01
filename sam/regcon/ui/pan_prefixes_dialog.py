from __future__ import annotations

from pathlib import Path
from typing import Any

from sam.regcon.config.pan_prefixes import (
    DEFAULT_PREFIX_LEN,
    load_prefixes_from_file,
    load_prefixes_from_text,
    prefixes_to_text,
)
from sam.regcon.util.app_paths import app_data_dir, pan_prefix_path
from sam.regcon.util.pan_prefix_store import load_prefixes_as_text, save_prefixes_from_text

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
    """Редактор префиксов PAN → зашифрованный pan_prefix.yaml рядом с exe."""

    def __init__(self, config: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.prefix_len = int(
            config.get("pan", {}).get("prefix_digits", DEFAULT_PREFIX_LEN)
        )
        self.setWindowTitle("Префиксы PAN")
        self.resize(420, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"Первые {self.prefix_len} цифр — по строке.\n"
                f"Файл (шифр.): {pan_prefix_path()}"
            )
        )

        self.editor = QTextEdit()
        self.editor.setPlainText(load_prefixes_as_text())
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
            self,
            "Импорт префиксов",
            str(app_data_dir()),
            "Текст (*.txt);;YAML (*.yaml)",
        )
        if not path:
            return
        items = load_prefixes_from_file(Path(path), self.prefix_len)
        if items:
            self.editor.setPlainText(prefixes_to_text(items))

    def _save(self) -> None:
        save_prefixes_from_text(self.editor.toPlainText(), self.prefix_len)
        self.accept()
