from sam.regcon.models import Finding
from sam.regcon.util.finding_groups import build_finding_groups, flatten_selected, group_key


def _finding(
    before: str,
    matched: str,
    line: int = 1,
    col: int = 10,
) -> Finding:
    f = Finding.create(
        file_path="/tmp/a.log",
        line_no=line,
        column=col,
        match_type="PAN",
        matched_text=matched,
        line=f"prefix {before}{matched} suffix",
        match_start=10,
        match_end=10 + len(matched.replace(" ", "")),
    )
    f.context_before = before
    return f


def test_group_same_prefix_before_pan():
    f1 = _finding("TXN ", "4111111111111111", col=10)
    f2 = _finding("TXN ", "5500000000000004", col=40)
    groups = build_finding_groups([f1, f2])
    assert len(groups) == 1
    assert groups[0].count == 2


def test_different_prefix_not_grouped():
    f1 = _finding("AAA ", "4111111111111111")
    f2 = _finding("BBB ", "4111111111111111")
    assert len(build_finding_groups([f1, f2])) == 2


def test_flatten_selected_respects_group():
    f1 = _finding("TXN ", "4111111111111111")
    f2 = _finding("TXN ", "5500000000000004")
    groups = build_finding_groups([f1, f2])
    groups[0].selected = False
    assert flatten_selected(groups) == []
