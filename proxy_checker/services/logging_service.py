import logging
import os
from logging.handlers import RotatingFileHandler

from proxy_checker.config import LOG_BACKUP_COUNT, LOG_MAX_BYTES


def configure_logging(
    log_file_path,
    logger_name="proxy_checker",
    *,
    max_bytes=None,
    backup_count=None,
):
    logger = logging.getLogger(logger_name)
    if getattr(logger, "_proxy_checker_configured", False):
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    directory = os.path.dirname(os.path.abspath(log_file_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes if max_bytes is not None else LOG_MAX_BYTES,
        backupCount=backup_count if backup_count is not None else LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    logger._proxy_checker_configured = True
    return logger
