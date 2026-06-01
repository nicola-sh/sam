from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sam.services.ssh_client import SshEndpoint


@dataclass(frozen=True)
class HostEndpoint:
    """Один узел в кластере (fo-01, fo-02, …)."""

    id: str
    host: str
    port: int
    username: str
    password: str
    key_filename: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.id} ({self.host})" if self.host else self.id


@dataclass(frozen=True)
class ClusterDef:
    id: str
    name: str
    hosts: tuple[HostEndpoint, ...]

    @property
    def display_name(self) -> str:
        return self.name or self.id.upper()


@dataclass(frozen=True)
class StandaloneServer:
    """Отдельный сервер (например ATM), не кластер."""

    id: str
    name: str
    host: str
    port: int
    username: str
    password: str
    key_filename: str = ""

    @property
    def display_name(self) -> str:
        return self.name or self.id.upper()


def _parse_host(raw: dict[str, Any]) -> HostEndpoint:
    return HostEndpoint(
        id=str(raw.get("id") or "host"),
        host=str(raw.get("host") or "").strip(),
        port=int(raw.get("port") or 22),
        username=str(raw.get("username") or "").strip(),
        password=str(raw.get("password") or ""),
        key_filename=str(raw.get("key_filename") or "").strip(),
    )


def parse_clusters(config: dict[str, Any]) -> list[ClusterDef]:
    result: list[ClusterDef] = []
    for raw in config.get("clusters") or []:
        if not isinstance(raw, dict):
            continue
        hosts = tuple(_parse_host(h) for h in raw.get("hosts") or [] if isinstance(h, dict))
        result.append(
            ClusterDef(
                id=str(raw.get("id") or "cluster"),
                name=str(raw.get("name") or raw.get("id") or "cluster"),
                hosts=hosts,
            )
        )
    return result


def parse_servers(config: dict[str, Any]) -> list[StandaloneServer]:
    result: list[StandaloneServer] = []
    for raw in config.get("servers") or []:
        if not isinstance(raw, dict):
            continue
        result.append(
            StandaloneServer(
                id=str(raw.get("id") or "server"),
                name=str(raw.get("name") or raw.get("id") or "server"),
                host=str(raw.get("host") or "").strip(),
                port=int(raw.get("port") or 22),
                username=str(raw.get("username") or "").strip(),
                password=str(raw.get("password") or ""),
                key_filename=str(raw.get("key_filename") or "").strip(),
            )
        )
    return result


def cluster_by_id(config: dict[str, Any], cluster_id: str) -> ClusterDef | None:
    for c in parse_clusters(config):
        if c.id == cluster_id:
            return c
    return None


def server_by_id(config: dict[str, Any], server_id: str) -> StandaloneServer | None:
    for s in parse_servers(config):
        if s.id == server_id:
            return s
    return None


def legacy_ssh_endpoint(config: dict[str, Any], *, timeout_sec: float = 30.0) -> SshEndpoint | None:
    ssh = config.get("ssh") or {}
    if not ssh.get("host"):
        return None
    return SshEndpoint.from_mapping(ssh, timeout_sec=timeout_sec)


def resolve_ssh_endpoint(
    config: dict[str, Any],
    *,
    target_kind: str,
    target_id: str,
    host_id: str | None,
    timeout_sec: float = 30.0,
) -> SshEndpoint:
    """
    target_kind: cluster | server
    host_id: обязателен для cluster — какой узел кластера использовать
    """
    if target_kind == "server":
        srv = server_by_id(config, target_id)
        if srv is None:
            raise ValueError(f"Сервер «{target_id}» не найден в настройках")
        if not srv.host or not srv.username:
            raise ValueError(f"Заполните host и username для сервера «{target_id}»")
        return SshEndpoint(
            host=srv.host,
            port=srv.port,
            username=srv.username,
            password=srv.password,
            key_filename=srv.key_filename,
            timeout_sec=timeout_sec,
        )

    if target_kind == "cluster":
        cluster = cluster_by_id(config, target_id)
        if cluster is None:
            raise ValueError(f"Кластер «{target_id}» не найден")
        if not host_id:
            raise ValueError("Выберите узел кластера")
        host = next((h for h in cluster.hosts if h.id == host_id), None)
        if host is None:
            raise ValueError(f"Узел «{host_id}» не найден в кластере «{target_id}»")
        if not host.host or not host.username:
            raise ValueError(f"Заполните host и username для узла «{host_id}»")
        return SshEndpoint(
            host=host.host,
            port=host.port,
            username=host.username,
            password=host.password,
            key_filename=host.key_filename,
            timeout_sec=timeout_sec,
        )

    legacy = legacy_ssh_endpoint(config, timeout_sec=timeout_sec)
    if legacy:
        return legacy
    raise ValueError(f"Неизвестный источник: {target_kind}/{target_id}")


def list_download_sources(config: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(target_kind, target_id, подпись для UI)"""
    items: list[tuple[str, str, str]] = []
    for c in parse_clusters(config):
        items.append(("cluster", c.id, f"Кластер {c.display_name}"))
    for s in parse_servers(config):
        items.append(("server", s.id, f"Сервер {s.display_name}"))
    if not items and (config.get("ssh") or {}).get("host"):
        items.append(("legacy", "default", "Сервер (из старого ssh)"))
    return items


def hosts_for_source(
    config: dict[str, Any],
    target_kind: str,
    target_id: str,
) -> list[HostEndpoint]:
    if target_kind == "cluster":
        cluster = cluster_by_id(config, target_id)
        return list(cluster.hosts) if cluster else []
    return []
