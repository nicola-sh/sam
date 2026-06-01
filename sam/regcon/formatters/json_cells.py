from __future__ import annotations

import json
import re

JSON_START = re.compile(r"^\s*[\{\[]")


def format_json_cell(value: str, indent: int = 2) -> str:
    """Форматирует JSON в тексте ячейки, если распознан."""
    text = value.strip()
    if not text or not JSON_START.match(text):
        return value
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False, indent=indent)
    except json.JSONDecodeError:
        return value


def format_dataframe_json_cells(frame, indent: int = 2):
    """Применяет format_json_cell ко всем ячейкам DataFrame."""
    for col in frame.columns:
        frame[col] = frame[col].map(
            lambda v: format_json_cell(str(v), indent=indent) if v else v
        )
    return frame
