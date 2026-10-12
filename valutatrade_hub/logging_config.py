import logging
import os
from logging.handlers import RotatingFileHandler

from infra.settings import SettingsLoader


def setup_logging() -> logging.Logger:
    """Инициализирует и возвращает логгер для записи действий приложения."""
    settings = SettingsLoader()
    project_root = settings.get("project_root")

    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file_path = os.path.join(logs_dir, "actions.log")

    logger = logging.getLogger("actions_logger")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            filename=log_file_path,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger