from __future__ import annotations

from copy import deepcopy
from typing import Any

from sam.config.settings import save_config
from sam.models.microservice import parse_microservices

try:
    from PyQt6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
    )
except ImportError:  # pragma: no cover
    from PyQt5.QtWidgets import (  # type: ignore
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMessageBox,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
    )


class MicroservicesDialog(QDialog):
    """Редактор списка microservices в config.yaml."""

    def __init__(self, config: dict[str, Any], config_path, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.config_path = config_path
        self.setWindowTitle("Микросервисы")
        self.resize(560, 480)
        self._services: list[dict[str, Any]] = deepcopy(config.get("microservices") or [])

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Сервисы и пути к логам на удалённом сервере:"))

        self.list_widget = QListWidget()
        self._refresh_list()
        root.addWidget(self.list_widget)

        form = QFormLayout()
        self.id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.dir_edit = QLineEdit("/srv_mproc/mproc/services/")
        self.arch_edit = QLineEdit("/log_arch")
        self.main_edit = QLineEdit("/log")
        self.outputs_edit = QTextEdit()
        self.outputs_edit.setPlaceholderText(
            "JSON-массив outputs, например:\n"
            '[{"id":"DDC","arch_prefix":"atm-ddc","main_name":"atm-ddc"}]'
        )
        self.outputs_edit.setMaximumHeight(90)
        form.addRow("id:", self.id_edit)
        form.addRow("Название:", self.name_edit)
        form.addRow("service_dir:", self.dir_edit)
        form.addRow("arch_subdir:", self.arch_edit)
        form.addRow("main_subdir:", self.main_edit)
        form.addRow("outputs (JSON):", self.outputs_edit)
        root.addLayout(form)

        row = QHBoxLayout()
        for label, slot in (
            ("Добавить", self._add),
            ("Обновить", self._update),
            ("Удалить", self._remove),
        ):
            btn = QPushButton(label)
            btn.setObjectName("secondaryBtn")
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch()
        root.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_all)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if self._services:
            self.list_widget.setCurrentRow(0)
            self._load_selected()

        self.list_widget.currentRowChanged.connect(lambda _: self._load_selected())

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for raw in self._services:
            sid = raw.get("id", "?")
            name = raw.get("name", sid)
            self.list_widget.addItem(f"{name} ({sid})")

    def _load_selected(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._services):
            return
        raw = self._services[row]
        self.id_edit.setText(str(raw.get("id", "")))
        self.name_edit.setText(str(raw.get("name", "")))
        self.dir_edit.setText(str(raw.get("service_dir", "")))
        self.arch_edit.setText(str(raw.get("arch_subdir", "/log_arch")))
        self.main_edit.setText(str(raw.get("main_subdir", "/log")))
        import json

        outs = raw.get("outputs") or []
        self.outputs_edit.setPlainText(json.dumps(outs, ensure_ascii=False, indent=2))

    def _form_to_dict(self) -> dict[str, Any]:
        import json

        outs_text = self.outputs_edit.toPlainText().strip()
        outputs = json.loads(outs_text) if outs_text else []
        return {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "service_dir": self.dir_edit.text().strip(),
            "arch_subdir": self.arch_edit.text().strip() or "/log_arch",
            "main_subdir": self.main_edit.text().strip() or "/log",
            "outputs": outputs,
        }

    def _add(self) -> None:
        try:
            entry = self._form_to_dict()
        except Exception as exc:
            QMessageBox.warning(self, "Микросервисы", f"Ошибка outputs JSON: {exc}")
            return
        if not entry["id"] or not entry["service_dir"]:
            QMessageBox.warning(self, "Микросервисы", "Нужны id и service_dir")
            return
        self._services.append(entry)
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self._services) - 1)

    def _update(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        try:
            self._services[row] = self._form_to_dict()
        except Exception as exc:
            QMessageBox.warning(self, "Микросервисы", f"Ошибка outputs JSON: {exc}")
            return
        self._refresh_list()
        self.list_widget.setCurrentRow(row)

    def _remove(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        del self._services[row]
        self._refresh_list()

    def _save_all(self) -> None:
        try:
            parse_microservices({"microservices": self._services})
        except Exception as exc:
            QMessageBox.warning(self, "Микросервисы", str(exc))
            return
        self.config["microservices"] = self._services
        if "atm_ddc" in self.config:
            del self.config["atm_ddc"]
        save_config(self.config, self.config_path)
        self.accept()
