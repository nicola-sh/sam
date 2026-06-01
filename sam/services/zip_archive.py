from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path


class ArchiveError(Exception):
    pass


def aes_zip_available() -> bool:
    return importlib.util.find_spec("pyzipper") is not None


def _create_plain_zip(files: list[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            if path.is_file():
                zf.write(path, arcname=path.name)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise ArchiveError("Не удалось создать архив")
    return output_path


def _create_aes_zip(files: list[Path], output_path: Path, password: str) -> Path:
    import pyzipper

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    with pyzipper.AESZipFile(
        output_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        for path in files:
            if path.is_file():
                zf.write(path, arcname=path.name)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise ArchiveError("Не удалось создать архив")
    return output_path


def create_password_zip(
    files: list[Path],
    *,
    output_path: Path,
    password: str,
) -> Path:
    """ZIP без пароля — stdlib; с паролем — pyzipper (опционально из DATA\\wheels)."""
    if not files:
        raise ArchiveError("Нет файлов для архивации")

    pwd = password.strip()
    if pwd:
        if len(pwd) < 4:
            raise ArchiveError("Пароль архива не короче 4 символов")
        if not aes_zip_available():
            raise ArchiveError(
                "ZIP с паролем требует pyzipper из DATA\\wheels.\n"
                "Запустите scripts\\install_offline.bat\n"
                "или создайте архив без пароля."
            )
        return _create_aes_zip(files, output_path, pwd)
    return _create_plain_zip(files, output_path)
