from regcon.models import Finding
from regcon.util.finding_groups import FindingGroup
from regcon.util.mask_preview import format_group_preview, preview_masked_value


def test_preview_pan_masks_middle():
    cfg = {"pan": {"mask_keep_first": 6, "mask_keep_last": 4}}
    f = Finding.create(
        file_path="/a.log",
        line_no=1,
        column=0,
        match_type="PAN",
        matched_text="4111111111111111",
        line="x",
        match_start=0,
        match_end=16,
    )
    masked = preview_masked_value(f, cfg)
    assert "411111" in masked
    assert "1111" in masked
    assert "*" in masked


def test_format_group_preview_shows_count():
    cfg = {"pan": {"mask_keep_first": 6, "mask_keep_last": 4}}
    f = Finding.create(
        file_path="/a.log",
        line_no=1,
        column=0,
        match_type="PAN",
        matched_text="4111111111111111",
        line="x",
        match_start=0,
        match_end=16,
    )
    g = FindingGroup(id="1", items=[f, f], selected=True)
    text = format_group_preview(g, cfg)
    assert "×2" in text
