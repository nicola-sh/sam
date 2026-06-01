from __future__ import annotations

import ipaddress
import re
from typing import Iterable

from sam.regcon.models import Finding


def mask_pan_text(text: str, keep_first: int = 6, keep_last: int = 4) -> str:
    digits = [(i, ch) for i, ch in enumerate(text) if ch.isdigit()]
    if len(digits) < keep_first + keep_last:
        return "*" * len(text)
    hide_from = keep_first
    hide_to = len(digits) - keep_last
    hide_positions = {idx for idx, _ in digits[hide_from:hide_to]}
    chars = list(text)
    for pos in hide_positions:
        chars[pos] = "*"
    return "".join(chars)


def mask_ip_text(text: str, mode: str = "last_two") -> str:
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return "***"
    if isinstance(ip, ipaddress.IPv4Address):
        parts = text.split(".")
        if mode == "full":
            return "***.***.***.***"
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        return "***"
    if mode == "full":
        return "****:****:****:****"
    if "::" in text:
        return text.split("::")[0] + "::****"
    parts = text.split(":")
    if len(parts) >= 4:
        return ":".join(parts[: len(parts) // 2]) + ":****"
    return "****"


def mask_password_text(text: str) -> str:
    if len(text) <= 2:
        return "**"
    return text[0] + "*" * (len(text) - 2) + text[-1]


def mask_match(text: str, match_type: str, config: dict) -> str:
    if match_type == "PAN":
        pan_cfg = config.get("pan", {})
        return mask_pan_text(
            text,
            keep_first=int(pan_cfg.get("mask_keep_first", 6)),
            keep_last=int(pan_cfg.get("mask_keep_last", 4)),
        )
    if match_type == "IP":
        return mask_ip_text(text, config.get("ip", {}).get("mask_mode", "last_two"))
    if match_type == "PASSWORD":
        return mask_password_text(text)
    return "***"


def apply_replacements(line: str, replacements: Iterable[tuple[int, int, str]]) -> str:
    """Замены с конца строки, чтобы не сбивать индексы."""
    ordered = sorted(replacements, key=lambda item: item[0], reverse=True)
    result = line
    for start, end, masked in ordered:
        if start < 0 or end > len(result) or start >= end:
            continue
        result = result[:start] + masked + result[end:]
    return result


def findings_to_replacements(
    line: str,
    findings: Iterable[Finding],
    config: dict,
) -> list[tuple[int, int, str]]:
    replacements: list[tuple[int, int, str]] = []
    for finding in findings:
        start = finding.column
        end = (
            finding.span_end
            if finding.span_end > start
            else start + len(finding.matched_text)
        )
        if start < 0 or end > len(line) or start >= end:
            continue
        fragment = line[start:end]
        if finding.match_type == "PAN":
            masked = mask_pan_text(
                fragment,
                keep_first=int(config.get("pan", {}).get("mask_keep_first", 6)),
                keep_last=int(config.get("pan", {}).get("mask_keep_last", 4)),
            )
        else:
            if fragment != finding.matched_text:
                idx = line.find(finding.matched_text, max(0, start - 8))
                if idx >= 0:
                    start, end = idx, idx + len(finding.matched_text)
                    fragment = line[start:end]
                else:
                    continue
            masked = mask_match(fragment, finding.match_type, config)
        replacements.append((start, end, masked))
    return replacements
