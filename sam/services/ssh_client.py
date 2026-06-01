from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import paramiko


@dataclass
class SshEndpoint:
    host: str
    port: int = 22
    username: str = ""
    password: str = ""
    key_filename: str = ""
    look_for_keys: bool = True
    allow_agent: bool = True
    timeout_sec: float = 30.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any], *, timeout_sec: float = 30.0) -> SshEndpoint:
        return cls(
            host=str(data.get("host") or "").strip(),
            port=int(data.get("port") or 22),
            username=str(data.get("username") or "").strip(),
            password=str(data.get("password") or ""),
            key_filename=str(data.get("key_filename") or "").strip(),
            look_for_keys=bool(data.get("look_for_keys", True)),
            allow_agent=bool(data.get("allow_agent", True)),
            timeout_sec=timeout_sec,
        )


def connect(endpoint: SshEndpoint) -> paramiko.SSHClient:
    if not endpoint.host:
        raise ValueError("Не задан host для SSH")
    if not endpoint.username:
        raise ValueError("Не задан username для SSH")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict[str, Any] = {
        "hostname": endpoint.host,
        "port": endpoint.port,
        "username": endpoint.username,
        "timeout": endpoint.timeout_sec,
        "allow_agent": endpoint.allow_agent,
        "look_for_keys": endpoint.look_for_keys,
    }
    if endpoint.password:
        kwargs["password"] = endpoint.password
    if endpoint.key_filename:
        kwargs["key_filename"] = endpoint.key_filename
    client.connect(**kwargs)
    return client


def stream_command(
    client: paramiko.SSHClient,
    command: str,
    *,
    timeout_sec: float | None = None,
) -> tuple[int, bytes, bytes]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout_sec)
    del stdin
    out = stdout.read()
    err = stderr.read()
    code = stdout.channel.recv_exit_status()
    return code, out, err
