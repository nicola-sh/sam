from __future__ import annotations

import shlex

from sam.models.microservice import LogOutput, Microservice
from sam.util.dates import AtmLogDateFormats


def archived_glob_path(
    service: Microservice,
    output: LogOutput,
    formats: AtmLogDateFormats,
) -> str:
    base = service.service_dir.rstrip("/")
    prefix = output.arch_prefix.strip()
    if output.arch_glob:
        path = output.arch_glob.replace("{date_dash}", formats.date_dash)
        path = path.replace("{date_plain}", formats.date_plain)
        if not path.startswith("/"):
            path = f"{base}{service.arch_subdir}/{path}"
        return path
    layout = (service.log_layout or "daily").lower()
    if layout == "hourly":
        return f"{base}{service.arch_subdir}/{prefix}.{formats.date_dash}-*.*.gz"
    return f"{base}{service.arch_subdir}/{prefix}.{formats.date_dash}.*.gz"


def main_log_path(service: Microservice, output: LogOutput) -> str:
    base = service.service_dir.rstrip("/")
    return f"{base}{service.main_subdir}/{output.main_name}"


def build_archived_command(
    service: Microservice,
    output: LogOutput,
    formats: AtmLogDateFormats,
    grep_value: str | None,
) -> str:
    path = archived_glob_path(service, output, formats)
    path_q = shlex.quote(path)
    if grep_value:
        needle = shlex.quote(grep_value)
        return f"zgrep -ah {needle} {path_q} 2>/dev/null || true"
    return f"zcat {path_q} 2>/dev/null || true"


def build_main_command(
    service: Microservice,
    output: LogOutput,
    grep_value: str | None,
) -> str:
    path_q = shlex.quote(main_log_path(service, output))
    if grep_value:
        needle = shlex.quote(grep_value)
        return f"grep -ah {needle} {path_q} 2>/dev/null || true"
    return f"cat {path_q} 2>/dev/null || true"


def commands_for_output(
    service: Microservice,
    output: LogOutput,
    formats: AtmLogDateFormats,
    grep_value: str | None,
) -> list[tuple[str, str]]:
    layout = (service.log_layout or "daily").lower()
    label_arch = "архив (по часам)" if layout == "hourly" else "архив (за сутки)"
    steps: list[tuple[str, str]] = [
        (label_arch, build_archived_command(service, output, formats, grep_value)),
    ]
    include_main = formats.is_today and output.main_only_today
    if formats.is_today and not output.main_only_today:
        include_main = True
    if include_main and output.main_name:
        steps.append(("текущий", build_main_command(service, output, grep_value)))
    return steps
