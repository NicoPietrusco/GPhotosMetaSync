"""Photo Meta Sync: export photos from Google Photos while keeping their capture metadata."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gphotometasync")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"
