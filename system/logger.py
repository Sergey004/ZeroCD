"""
ZeroCD Logger
"""
import logging
import os

LOG_FILE = "/var/log/zerocd.log"


def setup_logger(name: str = "zerocd") -> logging.Logger:
    """Initialize logger with file and console handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get logger by name."""
    return logging.getLogger(f"zerocd.{name}")
