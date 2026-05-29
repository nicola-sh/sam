# -*- mode: python ; coding: utf-8 -*-
# Сборка из корня репозитория: pyinstaller regcon/build/regcon.spec
import sys
from pathlib import Path

regcon_pkg = Path(SPECPATH).resolve().parent
repo = regcon_pkg.parent

a = Analysis(
    [str(regcon_pkg / "__main__.py")],
    pathex=[str(repo)],
    binaries=[],
    datas=[
        (str(regcon_pkg / "config.yaml"), "regcon"),
        (str(regcon_pkg / "config.example.yaml"), "regcon"),
    ],
    hiddenimports=[
        "cryptography",
        "yaml",
        "openpyxl",
        "pandas",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="RegCon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(Path(SPECPATH) / "version_info.txt") if sys.platform == "win32" else None,
    uac_admin=False,
)
