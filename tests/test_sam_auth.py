from pathlib import Path

from sam.auth.users import UserStore


def test_user_create_and_verify(tmp_path: Path):
    store = UserStore(tmp_path / "users.json")
    store.create_user("ivanov", "secret12", display_name="Иванов", role="operator")
    user = store.verify("ivanov", "secret12")
    assert user is not None
    assert user.login == "ivanov"
    assert store.verify("ivanov", "wrong") is None
