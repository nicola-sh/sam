from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class Finding:
    """Одно совпадение чувствительных данных."""

    id: str
    file_path: str
    line_no: int
    column: int
    match_type: str
    matched_text: str
    context: str = ""
    selected: bool = True
    cell: str = ""

    @classmethod
    def create(
        cls,
        file_path: str,
        line_no: int,
        column: int,
        match_type: str,
        matched_text: str,
        context: str = "",
        cell: str = "",
    ) -> Finding:
        return cls(
            id=str(uuid.uuid4()),
            file_path=file_path,
            line_no=line_no,
            column=column,
            match_type=match_type,
            matched_text=matched_text,
            context=context,
            cell=cell,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "line_no": self.line_no,
            "column": self.column,
            "match_type": self.match_type,
            "matched_text": self.matched_text,
            "context": self.context,
            "selected": self.selected,
            "cell": self.cell,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            id=data["id"],
            file_path=data["file_path"],
            line_no=int(data["line_no"]),
            column=int(data["column"]),
            match_type=data["match_type"],
            matched_text=data["matched_text"],
            context=data.get("context", ""),
            selected=bool(data.get("selected", True)),
            cell=data.get("cell", ""),
        )
