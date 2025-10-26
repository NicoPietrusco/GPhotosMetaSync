"""
GPhotoMetaSync - Google Photos Metadata Synchronizer

A comprehensive tool for extracting, analyzing, and embedding EXIF metadata
from images, particularly useful for Google Photos workflows.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__description__ = "Google Photos Metadata Synchronizer"

from .settings import Settings

settings = Settings()


# Import main components (lazy loading to avoid dependency issues)
def get_cli_app():
    """Get CLI app (lazy import)."""
    from .main import app

    return app


def get_gui_main():
    """Get GUI main function (lazy import)."""
    from .gui import main

    return main


__all__ = [
    "settings",
    "__version__",
    "__author__",
    "__description__",
    "get_cli_app",
    "get_gui_main",
]
