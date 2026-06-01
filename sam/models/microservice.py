from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LogOutput:
    """Один выходной файл (например DDC / DDC5556)."""

    id: str
    arch_prefix: str
    main_name: str
    main_only_today: bool = True


@dataclass(frozen=True)
class Microservice:
    id: str
    name: str
    service_dir: str
    arch_subdir: str = "/log_arch"
    main_subdir: str = "/log"
    outputs: tuple[LogOutput, ...] = ()
    ssh_profile: str = "default"

    @property
    def display_name(self) -> str:
        return self.name or self.id


def _norm_subdir(value: str, default: str) -> str:
    text = (value or default).strip()
    if not text.startswith("/"):
        text = "/" + text
    return text


def _parse_output(raw: dict[str, Any]) -> LogOutput:
    return LogOutput(
        id=str(raw.get("id") or "main"),
        arch_prefix=str(raw.get("arch_prefix") or raw.get("arch_glob_prefix") or ""),
        main_name=str(raw.get("main_name") or raw.get("main_file") or ""),
        main_only_today=bool(raw.get("main_only_today", True)),
    )


def _parse_one(raw: dict[str, Any]) -> Microservice:
    outputs_raw = raw.get("outputs") or raw.get("log_kinds") or []
    outputs = tuple(_parse_output(o) for o in outputs_raw)
    if not outputs:
        outputs = (LogOutput(id="main", arch_prefix="app", main_name="app"),)
    return Microservice(
        id=str(raw.get("id") or "service"),
        name=str(raw.get("name") or raw.get("id") or "service"),
        service_dir=str(raw.get("service_dir") or "").rstrip("/"),
        arch_subdir=_norm_subdir(str(raw.get("arch_subdir", "/log_arch")), "/log_arch"),
        main_subdir=_norm_subdir(str(raw.get("main_subdir", "/log")), "/log"),
        outputs=outputs,
        ssh_profile=str(raw.get("ssh_profile") or "default"),
    )


def parse_microservices(config: dict[str, Any]) -> list[Microservice]:
    items = config.get("microservices")
    if not items:
        legacy = config.get("atm_ddc")
        if legacy:
            items = [
                {
                    "id": "atm-ddc",
                    "name": "ATM DDC Service",
                    "service_dir": legacy.get("service_dir"),
                    "arch_subdir": legacy.get("arch_subdir", "/log_arch"),
                    "main_subdir": legacy.get("main_subdir", "/log"),
                    "outputs": legacy.get("log_kinds")
                    or [
                        {"id": "DDC", "arch_prefix": "atm-ddc", "main_name": "atm-ddc"},
                        {
                            "id": "DDC5556",
                            "arch_prefix": "atm-ddc5556",
                            "main_name": "atm-ddc5556",
                        },
                    ],
                }
            ]
    result: list[Microservice] = []
    for raw in items or []:
        if isinstance(raw, dict):
            svc = _parse_one(raw)
            if svc.service_dir:
                result.append(svc)
    return result


def microservice_by_id(config: dict[str, Any], service_id: str) -> Microservice | None:
    for svc in parse_microservices(config):
        if svc.id == service_id:
            return svc
    return None
