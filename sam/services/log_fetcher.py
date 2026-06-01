from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

import paramiko

from sam.config.secrets import resolve_ssh_endpoint as resolve_ssh_from_section
from sam.models.microservice import Microservice
from sam.models.topology import legacy_ssh_endpoint
from sam.services.remote_commands import commands_for_output
from sam.services.ssh_client import SshEndpoint, connect, stream_command
from sam.util.dates import formats_for_day
from sam.util.masking import mask_ipv4
from sam.util.output_names import output_file_path, safe_label
from sam.vault.store import SecretVault

LogCallback = Callable[[str], None]
CancelCallback = Callable[[], bool]


@dataclass
class FetchResult:
    service_id: str
    label: str
    dates: list[date]
    grep_value: str | None
    files: list[Path] = field(default_factory=list)
    line_counts: dict[str, int] = field(default_factory=dict)
    uploaded: list[str] = field(default_factory=list)
    target_kind: str = ""
    target_id: str = ""
    host_id: str = ""


class LogFetcher:
    def __init__(
        self,
        config: dict,
        vault: SecretVault | None,
        *,
        ssh_endpoint: SshEndpoint | None = None,
        ssh_section: str = "ssh",
    ) -> None:
        self._config = config
        sam = config.get("sam", {})
        self._cmd_timeout = float(sam.get("command_timeout_sec", 3600))
        self._ssh_timeout = float(sam.get("ssh_timeout_sec", 30))
        self._vault = vault
        if ssh_endpoint is not None:
            self._ssh = ssh_endpoint
        else:
            legacy = legacy_ssh_endpoint(config, timeout_sec=self._ssh_timeout)
            self._ssh = legacy or resolve_ssh_from_section(
                config.get(ssh_section, {}),
                vault,
                timeout_sec=self._ssh_timeout,
            )
        upload = config.get("upload", {})
        self._upload_enabled = bool(upload.get("enabled"))
        self._upload = (
            resolve_ssh_from_section(upload, vault, timeout_sec=self._ssh_timeout)
            if self._upload_enabled
            else None
        )
        self._upload_dir = str(upload.get("remote_dir") or "").rstrip("/")

    def fetch(
        self,
        service: Microservice,
        dates: list[date],
        download_root: Path,
        *,
        grep_value: str | None = None,
        label: str | None = None,
        log: LogCallback | None = None,
        cancel: CancelCallback | None = None,
        target_kind: str = "",
        target_id: str = "",
        host_id: str = "",
    ) -> FetchResult:
        def _log(msg: str) -> None:
            if log:
                log(msg)

        def _cancelled() -> bool:
            return bool(cancel and cancel())

        grep = grep_value.strip() if grep_value and grep_value.strip() else None
        folder_label = label or (grep if grep else "all")
        result = FetchResult(
            service_id=service.id,
            label=folder_label,
            dates=list(dates),
            grep_value=grep,
            target_kind=target_kind,
            target_id=target_id,
            host_id=host_id,
        )

        _log(
            f"Сервис: {service.display_name} · узел {self._ssh.username}@"
            f"{mask_ipv4(self._ssh.host)} · формат логов: {service.log_layout}"
        )
        if grep:
            _log(f"Фильтр grep: {grep}")
        else:
            _log("Без фильтра — полный лог за выбранные даты")

        client = connect(self._ssh)
        try:
            for day in dates:
                if _cancelled():
                    raise InterruptedError("Отменено пользователем")
                formats = formats_for_day(day)
                _log(f"Дата {formats.date_dash}…")
                for output in service.outputs:
                    if _cancelled():
                        raise InterruptedError("Отменено пользователем")
                    key = f"{formats.date_dash}/{output.id}"
                    local_path = output_file_path(
                        download_root,
                        service.id,
                        folder_label,
                        formats,
                        output.id,
                        grep_value=grep,
                    )
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_text("", encoding="utf-8")
                    lines = self._collect_output(
                        client,
                        service,
                        output,
                        formats,
                        grep,
                        local_path,
                        _log,
                    )
                    result.line_counts[key] = lines
                    if lines > 0:
                        result.files.append(local_path)
                        _log(f"  {output.id}: {lines} строк → {local_path.name}")
                    else:
                        local_path.unlink(missing_ok=True)
                        _log(f"  {output.id}: пусто")
        finally:
            client.close()

        if self._upload_enabled and result.files and not _cancelled():
            result.uploaded = self._upload_files(result.files, _log)

        return result

    def _collect_output(
        self,
        client: paramiko.SSHClient,
        service: Microservice,
        output,
        formats,
        grep_value: str | None,
        local_path: Path,
        log: LogCallback,
    ) -> int:
        total_lines = 0
        steps = commands_for_output(service, output, formats, grep_value)
        with local_path.open("ab") as out_fh:
            for step_label, cmd in steps:
                log(f"    {output.id} ({step_label})…")
                code, data, err = stream_command(
                    client,
                    cmd,
                    timeout_sec=self._cmd_timeout,
                )
                if err:
                    text = err.decode("utf-8", errors="replace").strip()
                    if text and "No such file" not in text:
                        log(f"      stderr: {text[:200]}")
                if code not in (0, 1):
                    log(f"      код выхода: {code}")
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
        log(f"Загрузка на {mask_ipv4(self._upload.host)}…")
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
