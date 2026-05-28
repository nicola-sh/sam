from regcon.detectors.pan import PanDetector, is_plausible_pan, luhn_valid
from regcon.maskers.masker import apply_replacements, findings_to_replacements, mask_pan_text
from regcon.models import Finding
from regcon.util.context import split_context


def test_luhn_valid_card():
    assert luhn_valid("4111111111111111")


def test_luhn_invalid():
    assert not luhn_valid("4111111111111112")


def test_rejects_date_as_pan():
    digits = "20260521143000"
    assert not is_plausible_pan(digits, digits, "2026-05-21 14:30:00", 0, len(digits))


def test_rejects_date_plus_zeros():
    text = "2026052100000000"
    assert not is_plausible_pan(text, text, "timestamp 2026052100000000", 11, 27)


def test_context_30_chars():
    line = "AAAA" + "4111111111111111" + "ZZZZ"
    before, after = split_context(line, 4, 20, 30)
    assert before == "AAAA"
    assert after == "ZZZZ"


def test_finds_pan_with_letters_around():
    cfg = {
        "pan": {
            "enabled": True,
            "use_luhn": True,
            "use_grouped_scan": True,
            "scan_mixed_alnum": True,
            "regex_list": [],
        }
    }
    det = PanDetector(cfg)
    line = "token=4111x111111111111x9999 field"
    hits = list(det.scan_line(line, "f.log", 1))
    assert any("4111" in h.matched_text for h in hits)


def test_finds_grouped_pan():
    cfg = {
        "pan": {
            "enabled": True,
            "use_luhn": True,
            "use_grouped_scan": True,
            "scan_mixed_alnum": False,
            "regex_list": [],
        }
    }
    det = PanDetector(cfg)
    line = "pay card 4111 1111 1111 1111 ok"
    hits = list(det.scan_line(line, "f.log", 1))
    assert len(hits) == 1


def test_mask_pan_keeps_edges():
    masked = mask_pan_text("4111111111111111")
    assert masked.startswith("411111")
    assert masked.endswith("1111")


def test_apply_replacements():
    line = "card=4111111111111111 end"
    finding = Finding.create(
        file_path="t.txt",
        line_no=1,
        column=5,
        match_type="PAN",
        matched_text="4111111111111111",
        line=line,
        match_start=5,
        match_end=21,
    )
    reps = findings_to_replacements(
        line, [finding], {"pan": {"mask_keep_first": 6, "mask_keep_last": 4}}
    )
    out = apply_replacements(line, reps)
    assert "4111111111111111" not in out
