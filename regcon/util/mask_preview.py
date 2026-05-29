from __future__ import annotations

from regcon.maskers.masker import mask_match
from regcon.models import Finding
from regcon.util.finding_groups import FindingGroup


def preview_masked_value(finding: Finding, config: dict) -> str:
    """Как будет выглядеть найденный фрагмент после маски."""
    return mask_match(finding.matched_text, finding.match_type, config)


def format_finding_preview(finding: Finding, config: dict, *, max_before: int = 36) -> str:
    before = finding.context_before.replace("\n", " ").replace("\r", "").strip()
    if len(before) > max_before:
        before = "…" + before[-max_before:]
    masked = preview_masked_value(finding, config)
    return f"{before} → {masked}" if before else masked


def format_group_preview(group: FindingGroup, config: dict) -> str:
    text = format_finding_preview(group.head, config)
    if group.count > 1:
        return f"{text}  (×{group.count})"
    return text
