"""
Application settings and constants for GPhotoMetaSync.
"""

import os
import secrets
import sys
from pathlib import Path
from typing import Set


class Settings:
    """Application-wide settings and constants."""

    # App info (shown in the web UI)
    APP_NAME = "Photo Meta Sync"
    APP_VERSION = "0.1.0"
    APP_DESCRIPTION = "Save dates, camera info, and location from your photos—on this computer or from Google Photos."

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

    # Web / Flask (override via environment)
    @property
    def secret_key(self) -> str:
        configured = os.environ.get("SECRET_KEY")
        if configured:
            return configured
        if not getattr(sys, "frozen", False):
            return "dev-only-change-SECRET_KEY"

        key_path = self.app_data_dir / "state" / "flask_secret_key"
        try:
            if key_path.is_file():
                return key_path.read_text(encoding="utf-8").strip()
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key = secrets.token_urlsafe(32)
            key_path.write_text(key, encoding="utf-8")
            try:
                key_path.chmod(0o600)
            except OSError:
                pass
            return key
        except OSError:
            return secrets.token_urlsafe(32)

    @property
    def max_upload_mb(self) -> int:
        return int(os.environ.get("MAX_UPLOAD_MB", "50"))

    @property
    def web_output_image_suffix(self) -> str:
        """
        Suffix appended to image/JSON basenames when "add suffix" is enabled locally.
        Set to empty in .env to default the UI to overwrite-style names (same basename).
        """
        return os.environ.get("WEB_OUTPUT_IMAGE_SUFFIX", "_exif")

    @property
    def google_oauth_client_secrets_path(self) -> Path:
        """Desktop OAuth client JSON from Google Cloud (Installed app)."""
        env = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRETS")
        if env:
            return Path(env)
        return self.resource_dir / "credentials" / "client_secrets.json"

    @property
    def google_token_path(self) -> Path:
        """Saved OAuth token after first sign-in (local only, gitignored)."""
        return self.app_data_dir / "credentials" / "google_token.json"

    @property
    def metadata_preferences_path(self) -> Path:
        """Per-user metadata choices shared by local and Google Photos workflows."""
        return self.app_data_dir / "settings" / "metadata_preferences.json"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def web_output_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def base_dir(self) -> Path:
        """Backward-compatible alias for the directory containing app resources."""
        return self.resource_dir

    @property
    def resource_dir(self) -> Path:
        """Directory containing read-only application resources."""
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if getattr(sys, "frozen", False) and isinstance(bundle_dir, str):
            return Path(bundle_dir)
        return Path(__file__).parent.parent.parent

    @property
    def app_data_dir(self) -> Path:
        """Writable data directory; separate from a frozen app bundle."""
        override = os.environ.get("GPHOTOMETASYNC_DATA_DIR")
        if override:
            return Path(override).expanduser()
        if not getattr(sys, "frozen", False):
            return self.resource_dir
        home = Path.home()
        if sys.platform == "darwin":
            return home / "Library" / "Application Support" / "GPhotoMetaSync"
        if os.name == "nt":
            return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "GPhotoMetaSync"
        return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "gphotometasync"

    @property
    def data_dir(self) -> Path:
        """Get the data directory."""
        return self.app_data_dir / "data"

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
