import json
from pathlib import Path

from sam.audit.audit_log import AuditLogger


def test_audit_masks_ip(tmp_path: Path):
    audit = AuditLogger(tmp_path / "audit")
    audit.record("test.action", user="u1", host="10.11.44.10")
    files = list((tmp_path / "audit").glob("audit-*.jsonl"))
    assert files
    line = files[0].read_text(encoding="utf-8").strip()
    data = json.loads(line)
    assert "10.11.***" in data["host"]
    assert "44.10" not in data["host"]
