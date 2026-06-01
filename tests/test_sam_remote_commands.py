from datetime import date

from sam.models.microservice import Microservice, LogOutput
from sam.services.remote_commands import (
    build_archived_command,
    build_main_command,
)
from sam.util.dates import formats_for_day

_SVC = Microservice(
    id="atm-ddc",
    name="ATM DDC",
    service_dir="/srv_mproc/mproc/services/atm-ddc-service",
    arch_subdir="/log_arch",
    main_subdir="/log",
    outputs=(LogOutput("DDC", "atm-ddc", "atm-ddc"),),
)
_OUT = _SVC.outputs[0]
_FMT = formats_for_day(date(2026, 5, 28), today=date(2026, 6, 1))


def test_archived_with_grep():
    cmd = build_archived_command(_SVC, _OUT, _FMT, "M6768022")
    assert "zgrep -ah" in cmd
    assert "M6768022" in cmd
    assert "2026-05-28" in cmd


def test_archived_without_grep():
    cmd = build_archived_command(_SVC, _OUT, _FMT, None)
    assert cmd.startswith("zcat ")
    assert "zgrep" not in cmd


def test_main_without_grep():
    cmd = build_main_command(_SVC, _OUT, None)
    assert "cat " in cmd
