"""
Application settings and constants for GPhotoMetaSync.
"""

from pathlib import Path
from typing import Set


class Settings:
    """Application-wide settings and constants."""

    # App info
    APP_NAME = "GPhotoMetaSync"
    APP_VERSION = "0.1.0"
    APP_DESCRIPTION = "Google Photos Metadata Synchronizer"

    # Supported image formats
    SUPPORTED_FORMATS: Set[str] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".bmp",
        ".webp",
        ".heic",
        ".heif",
    }

    # Default directories
    DEFAULT_OUTPUT_DIR = Path("output")
    DEFAULT_INPUT_DIR = Path("input")
    DEFAULT_DATA_DIR = Path("data")

    # EXIF date format
    EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

    # Log format
    LOG_FORMAT = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level:<8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - {message}"
    )

    # Progress bar settings
    PROGRESS_DESC_EXTRACT = "📸 Processing images"
    PROGRESS_DESC_EMBED = "🕒 Embedding EXIF"

    # File suffixes
    JSON_SUFFIX = ".json"
    DATED_SUFFIX = "_dated"

    @property
    def base_dir(self) -> Path:
        """Get the base directory of the application."""
        return Path(__file__).parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Get the data directory."""
        return self.base_dir / "data"

    @property
    def docs_dir(self) -> Path:
        """Get the documentation directory."""
        return self.base_dir / "docs"

    @property
    def tests_dir(self) -> Path:
        """Get the tests directory."""
        return self.base_dir / "tests"

    def ensure_directories(self) -> None:
        """Ensure all necessary directories exist."""
        for dir_path in [self.DEFAULT_OUTPUT_DIR, self.data_dir, self.docs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
