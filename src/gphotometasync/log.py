"""Logging setup (loguru)."""

import sys

from loguru import logger

LOG_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - {message}"
)


def setup_logger(level: str = "INFO") -> None:
    """Replace loguru's default handler with a colored stderr handler."""
    logger.remove()
    logger.add(sys.stderr, format=LOG_FORMAT, level=level, colorize=True)


def get_logger(name: str = "gphotometasync"):
    """Get a logger instance for a specific module."""
    return logger.bind(name=name)
