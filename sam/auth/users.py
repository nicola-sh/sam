from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import bcrypt

from sam.auth.session import SamUser

ROLES = frozenset({"operator", "admin"})


@dataclass
class UserRecord:
    login: str
    display_name: str
    role: str
    password_hash: str
    active: bool = True


class UserStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._users: dict[str, UserRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            self._users = {}
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._users = {}
        for raw in data.get("users", []):
            rec = UserRecord(
                login=str(raw["login"]),
                display_name=str(raw.get("display_name") or raw["login"]),
                role=str(raw.get("role") or "operator"),
                password_hash=str(raw["password_hash"]),
                active=bool(raw.get("active", True)),
            )
            self._users[rec.login.lower()] = rec

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": [
                {
                    "login": u.login,
                    "display_name": u.display_name,
                    "role": u.role,
                    "password_hash": u.password_hash,
                    "active": u.active,
                }
                for u in sorted(self._users.values(), key=lambda x: x.login.lower())
            ]
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def count(self) -> int:
        return len(self._users)

    def list_users(self) -> list[UserRecord]:
        return sorted(self._users.values(), key=lambda x: x.login.lower())

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

    def verify(self, login: str, password: str) -> SamUser | None:
        rec = self._users.get(login.strip().lower())
        if rec is None or not rec.active:
            return None
        try:
            ok = bcrypt.checkpw(
                password.encode("utf-8"),
                rec.password_hash.encode("utf-8"),
            )
        except ValueError:
            return None
        if not ok:
            return None
        return SamUser(login=rec.login, display_name=rec.display_name, role=rec.role)

    def create_user(
        self,
        login: str,
        password: str,
        *,
        display_name: str = "",
        role: str = "operator",
    ) -> UserRecord:
        key = login.strip().lower()
        if not key:
            raise ValueError("Логин не может быть пустым")
        if key in self._users:
            raise ValueError(f"Пользователь «{login}» уже существует")
        if role not in ROLES:
            raise ValueError(f"Роль должна быть: {', '.join(sorted(ROLES))}")
        rec = UserRecord(
            login=login.strip(),
            display_name=display_name.strip() or login.strip(),
            role=role,
            password_hash=self.hash_password(password),
        )
        self._users[key] = rec
        self.save()
        return rec

    def set_password(self, login: str, password: str) -> None:
        rec = self._users.get(login.strip().lower())
        if rec is None:
            raise ValueError("Пользователь не найден")
        rec.password_hash = self.hash_password(password)
        self.save()

    def set_active(self, login: str, active: bool) -> None:
        rec = self._users.get(login.strip().lower())
        if rec is None:
            raise ValueError("Пользователь не найден")
        rec.active = active
        self.save()
