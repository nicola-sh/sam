from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SamUser:
    login: str
    display_name: str
    role: str  # operator | admin

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass
class SamSession:
    user: SamUser | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None

    def login(self, user: SamUser) -> None:
        self.user = user

    def logout(self) -> SamUser | None:
        prev = self.user
        self.user = None
        return prev
