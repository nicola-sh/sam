from __future__ import annotations

from pathlib import Path

import pyzipper


class ArchiveError(Exception):
    pass


def create_password_zip(
    files: list[Path],
    *,
    output_path: Path,
    password: str,
) -> Path:
    if not files:
        raise ArchiveError("Нет файлов для архивации")
    pwd = password.strip()
    if len(pwd) < 4:
        raise ArchiveError("Пароль архива не короче 4 символов")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with pyzipper.AESZipFile(
        output_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(pwd.encode("utf-8"))
        for path in files:
            if path.is_file():
                zf.write(path, arcname=path.name)

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise ArchiveError("Не удалось создать архив")
    return output_path
