from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable

from regcon.detectors import IpDetector, PanDetector, SecretDetector
from regcon.models import Finding
from regcon.services.scan_line import scan_line_with_detectors
from regcon.util.cancel import CancelCallback, check_cancelled


def _scan_chunk(args: tuple[list[str], int, str, dict]) -> list[dict]:
    lines, start_line_no, file_path, config = args
    pan = PanDetector(config)
    pan.begin_file(10**12)
    pan._active_profile = "bulk"
    ip = IpDetector(config)
    secrets = SecretDetector(config)
    out: list[dict] = []
    for offset, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        for finding in scan_line_with_detectors(
            stripped,
            file_path,
            start_line_no + offset,
            pan,
            ip,
            secrets,
        ):
            out.append(finding.to_dict())
    return out


def scan_text_file_parallel(
    path: Path,
    config: dict,
    file_path: str,
    workers: int,
    chunk_lines: int,
    cancel: CancelCallback,
    on_chunk_done: Callable[[int], None] | None = None,
) -> list[Finding]:
    """Параллельный проход по чанкам строк (bulk-профиль в воркерах)."""
    encoding = config.get("regcon", {}).get("encoding", "utf-8")
    fallback = config.get("regcon", {}).get("fallback_encoding", "cp1251")
    read_buffer = int(config.get("regcon", {}).get("read_buffer_bytes", 1048576))

    try:
        handle = path.open(
            encoding=encoding, errors="replace", buffering=read_buffer
        )
    except OSError:
        handle = path.open(
            encoding=fallback, errors="replace", buffering=read_buffer
        )

    findings: list[Finding] = []
    chunk: list[str] = []
    chunk_start = 1
    futures = []

    with ProcessPoolExecutor(max_workers=workers) as pool:
        with handle:
            for line_no, line in enumerate(handle, start=1):
                check_cancelled(cancel)
                chunk.append(line)
                if len(chunk) < chunk_lines:
                    continue
                futures.append(
                    pool.submit(
                        _scan_chunk,
                        (chunk, chunk_start, file_path, config),
                    )
                )
                chunk = []
                chunk_start = line_no + 1

            if chunk:
                futures.append(
                    pool.submit(
                        _scan_chunk,
                        (chunk, chunk_start, file_path, config),
                    )
                )

        for future in futures:
            check_cancelled(cancel)
            for item in future.result():
                findings.append(Finding.from_dict(item))
            if on_chunk_done:
                on_chunk_done(len(findings))

    return findings
