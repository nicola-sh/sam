from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sam.regcon.models import Finding

_DIGITS_IN_PREFIX = re.compile(r"\d+")


def _prefix_signature(context_before: str) -> str:
    """
    Шаблон текста перед совпадением: цифры заменены на #,
    чтобы одинаковые фрагменты лога (дата, id) объединялись.
    """
    text = " ".join(context_before.split())
    if not text:
        return ""
    return _DIGITS_IN_PREFIX.sub("#", text)


def group_key(finding: Finding) -> tuple[str, ...]:
    before_sig = _prefix_signature(finding.context_before)
    if before_sig:
        return (
            finding.file_path,
            finding.match_type,
            before_sig,
        )
    return (
        finding.file_path,
        finding.match_type,
        str(finding.line_no),
        finding.cell,
        before_sig,
    )


@dataclass
class FindingGroup:
    """Несколько находок с одинаковым контекстом перед PAN/другим типом."""

    id: str
    items: list[Finding] = field(default_factory=list)
    selected: bool = True

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def head(self) -> Finding:
        return self.items[0]

    def sync_selection_to_items(self) -> None:
        for item in self.items:
            item.selected = self.selected


def build_finding_groups(findings: list[Finding]) -> list[FindingGroup]:
    """Сгруппировать находки по повторяющемуся префиксу перед совпадением."""
    buckets: dict[tuple[str, ...], list[Finding]] = {}
    order: list[tuple[str, ...]] = []
    for finding in findings:
        key = group_key(finding)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(finding)

    groups: list[FindingGroup] = []
    for key in order:
        items = buckets[key]
        items.sort(key=lambda f: (f.line_no, f.column))
        selected = all(f.selected for f in items)
        groups.append(
            FindingGroup(
                id=str(uuid.uuid4()),
                items=items,
                selected=selected,
            )
        )
    return groups


def flatten_selected(groups: list[FindingGroup]) -> list[Finding]:
    """Все отмеченные находки из групп (для маскирования)."""
    result: list[Finding] = []
    for group in groups:
        if group.selected:
            for item in group.items:
                item.selected = True
                result.append(item)
    return result
