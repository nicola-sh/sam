from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from regcon.util.context import split_context


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
    context_before: str = ""
    context_after: str = ""
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
        line: str = "",
        match_start: int | None = None,
        match_end: int | None = None,
        context_radius: int = 30,
        context: str = "",
        cell: str = "",
    ) -> Finding:
        before, after = "", ""
        if line and match_start is not None and match_end is not None:
            before, after = split_context(line, match_start, match_end, context_radius)
            if not context:
                context = f"...{before}>>{matched_text}<<{after}..."
        return cls(
            id=str(uuid.uuid4()),
            file_path=file_path,
            line_no=line_no,
            column=column,
            match_type=match_type,
            matched_text=matched_text,
            context=context,
            context_before=before,
            context_after=after,
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
            "context_before": self.context_before,
            "context_after": self.context_after,
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
            context_before=data.get("context_before", ""),
            context_after=data.get("context_after", ""),
            selected=bool(data.get("selected", True)),
            cell=data.get("cell", ""),
        )
