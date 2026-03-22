"""
GPhotoMetaSync - Google Photos Metadata Synchronizer

Extract and embed EXIF metadata from images (local upload or Google Photos).
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__description__ = "Google Photos Metadata Synchronizer"

from .settings import Settings

settings = Settings()


def get_web_app():
    """Get Flask app factory (lazy import)."""
    from .web import create_app

    return create_app


__all__ = [
    "settings",
    "__version__",
    "__author__",
    "__description__",
    "get_web_app",
]
