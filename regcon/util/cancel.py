from __future__ import annotations

from typing import Callable

CancelCallback = Callable[[], bool] | None


class CancelledError(Exception):
    """Операция прервана пользователем."""


def check_cancelled(callback: CancelCallback) -> None:
    if callback and callback():
        raise CancelledError()
