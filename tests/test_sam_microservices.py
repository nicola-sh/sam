from sam.models.microservice import microservice_by_id, parse_microservices


def test_parse_default_atm_ddc():
    cfg = {
        "microservices": [
            {
                "id": "atm-ddc",
                "name": "ATM",
                "service_dir": "/srv/x",
                "outputs": [{"id": "DDC", "arch_prefix": "a", "main_name": "b"}],
            }
        ]
    }
    svcs = parse_microservices(cfg)
    assert len(svcs) == 1
    assert svcs[0].outputs[0].id == "DDC"


def test_legacy_atm_ddc_block():
    cfg = {
        "atm_ddc": {
            "service_dir": "/srv/legacy",
            "log_kinds": [{"id": "DDC", "arch_prefix": "atm-ddc", "main_name": "atm-ddc"}],
        }
    }
    svcs = parse_microservices(cfg)
    assert svcs[0].service_dir == "/srv/legacy"


def test_microservice_by_id():
    cfg = {"microservices": [{"id": "a", "service_dir": "/x", "outputs": []}]}
    assert microservice_by_id(cfg, "a") is not None
