from sam.models.microservice import microservices_for_source
from sam.models.topology import (
    list_download_sources,
    resolve_ssh_endpoint,
)
from sam.services.remote_commands import archived_glob_path
from sam.models.microservice import LogOutput, Microservice
from sam.util.dates import formats_for_day
from datetime import date


def _cfg():
    return {
        "clusters": [
            {
                "id": "fo",
                "name": "FO",
                "hosts": [
                    {
                        "id": "fo-01",
                        "host": "10.0.0.1",
                        "port": 22,
                        "username": "u",
                        "password": "p",
                    },
                ],
            },
        ],
        "servers": [
            {
                "id": "atm",
                "host": "10.0.0.9",
                "port": 22,
                "username": "atm",
                "password": "x",
            },
        ],
        "microservices": [
            {
                "id": "atm-ddc",
                "target_type": "server",
                "target_id": "atm",
                "service_dir": "/srv/atm",
                "outputs": [{"id": "DDC", "arch_prefix": "a", "main_name": "b"}],
            },
            {
                "id": "pay",
                "target_type": "cluster",
                "target_id": "fo",
                "log_layout": "hourly",
                "service_dir": "/srv/pay",
                "outputs": [{"id": "main", "arch_prefix": "pay", "main_name": "pay"}],
            },
        ],
    }


def test_list_sources():
    sources = list_download_sources(_cfg())
    ids = {(k, i) for k, i, _ in sources}
    assert ("cluster", "fo") in ids
    assert ("server", "atm") in ids


def test_resolve_cluster_host():
    ep = resolve_ssh_endpoint(
        _cfg(), target_kind="cluster", target_id="fo", host_id="fo-01"
    )
    assert ep.host == "10.0.0.1"


def test_microservices_filtered():
    fo = microservices_for_source(_cfg(), "cluster", "fo")
    assert len(fo) == 1
    assert fo[0].id == "pay"


def test_hourly_glob():
    svc = Microservice(
        id="x",
        name="x",
        service_dir="/srv",
        log_layout="hourly",
        outputs=(LogOutput("m", "pay", "pay"),),
    )
    fmt = formats_for_day(date(2026, 6, 1))
    path = archived_glob_path(svc, svc.outputs[0], fmt)
    assert "2026-06-01-*" in path
