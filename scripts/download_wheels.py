#!/usr/bin/env python3
"""Скачать .whl из requirements-offline.txt в DATA/wheels (Windows py3.13)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEST = REPO / "DATA" / "wheels"
REQ = REPO / "DATA" / "requirements-offline.txt"
SKIP = {"PySimpleGUI==5.0.7", "cx_Oracle==8.3.0"}


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    lines = REQ.read_text(encoding="utf-8").splitlines()
    ok, fail = 0, 0
    for line in lines:
        spec = line.strip()
        if not spec or spec.startswith("#") or spec in SKIP:
            continue
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            spec,
            "-d",
            str(DEST),
            "--platform",
            "win_amd64",
            "--python-version",
            "3.13",
            "--implementation",
            "cp",
            "--no-deps",
        ]
        if "pandastable" in spec or "pyminizip" in spec:
            cmd = [sys.executable, "-m", "pip", "download", spec, "-d", str(DEST), "--no-deps"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
        else:
            fail += 1
            print(f"[skip] {spec}", file=sys.stderr)
    # обновить список имён для офлайн-установки
    names = sorted(p.name for p in DEST.iterdir() if p.suffix in {".whl", ".gz"})
    (REPO / "DATA" / "req.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"Downloaded/verified: {ok}, skipped: {fail}, files: {len(names)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
