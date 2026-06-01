from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

import paramiko

from sam.services.ssh_client import SshEndpoint, connect, stream_command
from sam.util.dates import AtmLogDateFormats, formats_for_day
from sam.util.output_names import output_file_path, target_dir

LogCallback = Callable[[str], None]
CancelCallback = Callable[[], bool]


@dataclass
class AtmDdcFetchResult:
    atm_id: str
    day: date
    files: list[Path] = field(default_factory=list)
    line_counts: dict[str, int] = field(default_factory=dict)
    uploaded: list[str] = field(default_factory=list)


class AtmDdcFetcher:
    """Повторяет логику atm-ddc-logs.sh (zgrep архив + grep текущий лог)."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        sam = config.get("sam", {})
        self._cmd_timeout = float(sam.get("command_timeout_sec", 3600))
        self._ssh_timeout = float(sam.get("ssh_timeout_sec", 30))
        self._atm = config.get("atm_ddc", {})
        self._ssh = SshEndpoint.from_mapping(
            config.get("ssh", {}),
            timeout_sec=self._ssh_timeout,
        )
        upload = config.get("upload", {})
        self._upload_enabled = bool(upload.get("enabled"))
        self._upload = (
            SshEndpoint.from_mapping(upload, timeout_sec=self._ssh_timeout)
            if self._upload_enabled
            else None
        )
        self._upload_dir = str(upload.get("remote_dir") or "").rstrip("/")

    def fetch(
        self,
        atm_id: str,
        day: date,
        download_root: Path,
        *,
        log: LogCallback | None = None,
        cancel: CancelCallback | None = None,
    ) -> AtmDdcFetchResult:
        def _log(msg: str) -> None:
            if log:
                log(msg)

        def _cancelled() -> bool:
            return bool(cancel and cancel())

        formats = formats_for_day(day)
        atm = atm_id.strip().upper()
        result = AtmDdcFetchResult(atm_id=atm, day=day)
        target_dir(download_root, atm).mkdir(parents=True, exist_ok=True)

        _log(f"Подключение SSH {self._ssh.username}@{self._ssh.host}…")
        client = connect(self._ssh)
        try:
            for kind in self._log_kinds():
                if _cancelled():
                    raise InterruptedError("Отменено пользователем")
                local_path = output_file_path(download_root, atm, formats, kind["id"])
                local_path.write_text("", encoding="utf-8")
                lines = self._collect_kind(client, atm, formats, kind, local_path, _log)
                result.line_counts[kind["id"]] = lines
                if lines > 0:
                    result.files.append(local_path)
                    _log(f"{kind['id']}: {lines} строк → {local_path.name}")
                else:
                    local_path.unlink(missing_ok=True)
                    _log(f"{kind['id']}: совпадений нет")
        finally:
            client.close()

        if self._upload_enabled and result.files and not _cancelled():
            result.uploaded = self._upload_files(result.files, _log)

        return result

    def _log_kinds(self) -> list[dict[str, str]]:
        kinds = self._atm.get("log_kinds")
        if not kinds:
            return [
                {"id": "DDC", "arch_prefix": "atm-ddc", "main_name": "atm-ddc"},
                {
                    "id": "DDC5556",
                    "arch_prefix": "atm-ddc5556",
                    "main_name": "atm-ddc5556",
                },
            ]
        return [
            {
                "id": str(k["id"]),
                "arch_prefix": str(k["arch_prefix"]),
                "main_name": str(k["main_name"]),
            }
            for k in kinds
        ]

    def _service_paths(self) -> tuple[str, str, str]:
        base = str(self._atm.get("service_dir", "")).rstrip("/")
        arch = str(self._atm.get("arch_subdir", "/log_arch"))
        main = str(self._atm.get("main_subdir", "/log"))
        if not arch.startswith("/"):
            arch = "/" + arch
        if not main.startswith("/"):
            main = "/" + main
        return base, arch, main

    def _remote_append_command(
        self,
        atm: str,
        formats: AtmLogDateFormats,
        kind: dict[str, str],
        *,
        archived: bool,
    ) -> str:
        base, arch, main = self._service_paths()
        atm_q = shlex.quote(atm)
        if archived:
            path = f"{base}{arch}/{kind['arch_prefix']}.{formats.date_dash}.*.gz"
            return f"zgrep -ah {atm_q} {shlex.quote(path)} 2>/dev/null || true"
        path = f"{base}{main}/{kind['main_name']}"
        return f"grep -ah {atm_q} {shlex.quote(path)} 2>/dev/null || true"

    def _collect_kind(
        self,
        client: paramiko.SSHClient,
        atm: str,
        formats: AtmLogDateFormats,
        kind: dict[str, str],
        local_path: Path,
        log: LogCallback,
    ) -> int:
        commands: list[tuple[str, str]] = [
            ("архив", self._remote_append_command(atm, formats, kind, archived=True)),
        ]
        if formats.is_today:
            commands.append(
                (
                    "текущий",
                    self._remote_append_command(atm, formats, kind, archived=False),
                ),
            )

        total_lines = 0
        with local_path.open("ab") as out_fh:
            for label, cmd in commands:
                log(f"  {kind['id']} ({label})…")
                code, data, err = stream_command(
                    client,
                    cmd,
                    timeout_sec=self._cmd_timeout,
                )
                if err:
                    text = err.decode("utf-8", errors="replace").strip()
                    if text and "No such file" not in text:
                        log(f"    stderr: {text[:200]}")
                if code not in (0, 1):
                    log(f"    код выхода: {code}")
                if data:
                    out_fh.write(data)
                    if not data.endswith(b"\n"):
                        out_fh.write(b"\n")
                    total_lines += data.count(b"\n")
        return total_lines

    def _upload_files(self, paths: list[Path], log: LogCallback) -> list[str]:
        if not self._upload or not self._upload_dir:
            raise ValueError("upload.enabled=true, но не задан upload.remote_dir")
        uploaded: list[str] = []
        log(f"Загрузка на {self._upload.host}:{self._upload_dir}…")
        client = connect(self._upload)
        try:
            sftp = client.open_sftp()
            try:
                for path in paths:
                    remote = f"{self._upload_dir}/{path.name}"
                    sftp.put(str(path), remote)
                    uploaded.append(remote)
                    log(f"  → {remote}")
            finally:
                sftp.close()
        finally:
            client.close()
        return uploaded
