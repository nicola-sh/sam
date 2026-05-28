from regcon.detectors.pan import luhn_valid
from regcon.maskers.masker import mask_pan_text, apply_replacements
from regcon.models import Finding
from regcon.detectors.pan import PanDetector


def test_luhn_valid_card():
    assert luhn_valid("4111111111111111")


def test_luhn_invalid():
    assert not luhn_valid("4111111111111112")


def test_mask_pan_keeps_edges():
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
    from regcon.maskers.masker import findings_to_replacements

    reps = findings_to_replacements(
        line, [finding], {"pan": {"mask_keep_first": 6, "mask_keep_last": 4}}
    )
    out = apply_replacements(line, reps)
    assert "411111" in out
    assert "1111" in out
    assert "4111111111111111" not in out


def test_pan_detector_skips_invalid_luhn():
    cfg = {
        "pan": {
            "enabled": True,
            "use_luhn": True,
            "generic_16_digit": False,
            "regex_list": [r"\b\d{16}\b"],
        }
    }
    det = PanDetector(cfg)
    hits = list(det.scan_line("num 1234567890123456", "f.log", 1))
    assert len(hits) == 0
