from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sam.util.masking import mask_hosts_in_text, mask_ipv4


class AuditLogger:
    """Append-only JSONL аудит действий пользователей (IP в записях маскируются)."""

    def __init__(self, audit_dir: Path) -> None:
        self.audit_dir = audit_dir
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path_for_today(self) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.audit_dir / f"audit-{day}.jsonl"

    def record(
        self,
        action: str,
        *,
        user: str = "system",
        status: str = "ok",
        message: str = "",
        **fields: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "action": action,
            "status": status,
        }
        if message:
            payload["message"] = mask_hosts_in_text(str(message))
        for key, value in fields.items():
            if value is None:
                continue
            if key in ("host", "ssh_host", "server_host"):
                payload[key] = mask_ipv4(str(value))
            elif isinstance(value, str):
                payload[key] = mask_hosts_in_text(value)
            else:
                payload[key] = value
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with self._path_for_today().open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
