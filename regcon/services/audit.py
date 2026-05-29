from __future__ import annotations

import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from regcon.util.privacy import sanitize_audit_details


def write_audit(
    data_dir: Path,
    config: dict,
    event: str,
    details: dict[str, Any],
) -> None:
    rc = config.get("regcon", {})
    log_name = rc.get("audit_log", "regcon_actions.log")
    log_path = data_dir / log_name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": getpass.getuser(),
        "event": event,
        **sanitize_audit_details(details),
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
