from pathlib import Path

from regcon.config.pan_prefixes import load_prefixes, load_prefixes_from_text
from regcon.detectors.pan import PanDetector, is_plausible_pan, luhn_valid
from regcon.maskers.masker import apply_replacements, findings_to_replacements, mask_pan_text
from regcon.models import Finding
from regcon.util.context import split_context
from regcon.util.pan_prefix_index import PanPrefixIndex


def test_luhn_valid_card():
    assert luhn_valid("4111111111111111")


def test_luhn_invalid():
    assert not luhn_valid("4111111111111112")


def test_rejects_date_as_pan():
    digits = "20260521143000"
    line = "2026-05-21 14:30:00"
    assert not is_plausible_pan(digits, line, 0, len(digits))


def test_context_30_chars():
    line = "AAAA" + "4111111111111111" + "ZZZZ"
    before, after = split_context(line, 4, 20, 30)
    assert before == "AAAA"
    assert after == "ZZZZ"


def test_load_prefixes_from_config():
    cfg = {"pan": {"prefix_list": ["91123912", "41111111"], "prefix_digits": 8}}
    items = load_prefixes(cfg)
    assert len(items) == 2
    assert all(len(p) == 8 for p in items)


def test_prefix_index_finds_pan_by_eight_and_luhn():
    idx = PanPrefixIndex(["41111111"])
    line = "card 4111 1111 1111 1111 ok"
    hits = idx.iter_pan_candidates(line)
    assert len(hits) == 1
    assert hits[0][2] == "4111111111111111"


def test_prefix_index_tab_separated():
    idx = PanPrefixIndex(["41111111"])
    line = "41111111\t11111111"
    hits = idx.iter_pan_candidates(line)
    assert len(hits) == 1


def test_prefix_filter_skips_unknown_bin():
    cfg = {
        "pan": {
            "enabled": True,
            "prefix_list": ["55000000"],
            "prefix_digits": 8,
            "prefix_line_filter": True,
        }
    }
    det = PanDetector(cfg)
    line = "card 4111 1111 1111 1111"
    assert list(det.scan_line(line, "f.log", 1)) == []


def test_detector_finds_configured_prefix():
    cfg = {
        "pan": {
            "enabled": True,
            "prefix_list": ["41111111"],
            "prefix_digits": 8,
            "prefix_line_filter": True,
        }
    }
    det = PanDetector(cfg)
    hits = list(det.scan_line("n 4111111111111111", "f.log", 1))
    assert len(hits) == 1
    assert "4111" in hits[0].matched_text


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
