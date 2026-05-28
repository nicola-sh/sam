from regcon.detectors.pan import (
    PanDetector,
    is_plausible_pan,
    luhn_valid,
)
from regcon.maskers.masker import apply_replacements, findings_to_replacements
from regcon.models import Finding


def test_luhn_valid_card():
    assert luhn_valid("4111111111111111")


def test_luhn_invalid():
    assert not luhn_valid("4111111111111112")


def test_rejects_date_as_pan():
    line = "2026-05-21 14:30:00 event ok"
    digits = "20260521143000"
    assert not is_plausible_pan(digits, digits, line, 0, len(digits))


def test_rejects_date_plus_zeros():
    line = "timestamp 2026052100000000"
    text = "2026052100000000"
    digits = "2026052100000000"
    assert not is_plausible_pan(text, digits, line, 11, 11 + len(text))


def test_finds_real_pan_in_line():
    cfg = {
        "pan": {
            "enabled": True,
            "use_luhn": True,
            "use_grouped_scan": True,
            "regex_list": [],
        }
    }
    det = PanDetector(cfg)
    line = "pay card 4111 1111 1111 1111 ok"
    hits = list(det.scan_line(line, "f.log", 1))
    assert len(hits) == 1
    assert "4111" in hits[0].matched_text


def test_mask_pan_keeps_edges():
    from regcon.maskers.masker import mask_pan_text

    masked = mask_pan_text("4111111111111111")
    assert masked.startswith("411111")
    assert masked.endswith("1111")
    assert "*" in masked


def test_apply_replacements():
    line = "card=4111111111111111 end"
    finding = Finding.create(
        file_path="t.txt",
        line_no=1,
        column=5,
        match_type="PAN",
        matched_text="4111111111111111",
    )
    reps = findings_to_replacements(
        line, [finding], {"pan": {"mask_keep_first": 6, "mask_keep_last": 4}}
    )
    out = apply_replacements(line, reps)
    assert "4111111111111111" not in out
