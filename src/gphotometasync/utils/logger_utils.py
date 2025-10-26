"""
Logging utilities for GPhotoMetaSync.
"""

import sys
from typing import Optional

from loguru import logger

from ..settings import settings


def setup_logger(
    level: str = "INFO",
    format: Optional[str] = None,
    colorize: bool = True,
    file_path: Optional[str] = None,
) -> None:
    """
    Setup logging configuration for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format: Custom log format string
        colorize: Whether to enable colored output
        file_path: Optional file path for logging to file
    """
    # Remove default handler
    logger.remove()

    # Use settings format if not provided
    log_format = format or settings.LOG_FORMAT

    # Add console handler
    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=colorize,
    )

    # Add file handler if specified
    if file_path:
        logger.add(
            file_path,
            format=log_format,
            level=level,
            rotation="10 MB",
            retention="1 week",
            encoding="utf-8",
        )


def get_logger(name: str = "gphotometasync"):
    """Get a logger instance for a specific module."""
    return logger.bind(name=name)
