from regcon.models import Finding
from regcon.services.audit import write_audit
from regcon.util.privacy import redact_sensitive_text, sanitize_audit_details, wipe_findings


def test_redact_pan_in_log_line():
    line = "found 4111111111111111 in file"
    out = redact_sensitive_text(line)
    assert "4111111111111111" not in out
    assert "411111" in out


def test_audit_sanitizes_details(tmp_path, monkeypatch):
    from regcon.util import app_paths as paths_mod

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(paths_mod, "app_data_dir", lambda: data)
    write_audit(
        data,
        {"regcon": {"audit_log": "audit.log"}},
        "scan",
        {
            "count": 1,
            "matched_text": "4111111111111111",
            "files": ["a.log"],
        },
    )
    text = (data / "audit.log").read_text(encoding="utf-8")
    assert "4111111111111111" not in text
    assert "a.log" in text


def test_wipe_findings_clears_fields():
    f = Finding.create(
        file_path="/x",
        line_no=1,
        column=0,
        match_type="PAN",
        matched_text="4111111111111111",
        line="x",
        match_start=0,
        match_end=16,
    )
    items = [f]
    wipe_findings(items)
    assert items == []
    assert f.matched_text == ""
