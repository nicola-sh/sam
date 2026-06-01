from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sam.util.masking import mask_hosts_in_text


class _MaskingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original = record.getMessage()
        if isinstance(original, str):
            record.msg = mask_hosts_in_text(original)
            record.args = ()
        return super().format(record)


def setup_app_logging(log_dir: Path, *, level: int = logging.INFO) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    log_path = log_dir / f"sam-{day}.log"

    logger = logging.getLogger("sam")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = _MaskingFormatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    if not getattr(sys, "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

    logger.propagate = False
    return logger
