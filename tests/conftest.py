"""Shared fixtures for the test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import piexif
import pytest
from PIL import Image


@pytest.fixture
def make_jpeg(tmp_path: Path) -> Callable[..., Path]:
    """Create a small JPEG in tmp_path, optionally with a piexif-style EXIF dict."""

    def _make(name: str = "photo.jpg", exif: dict | None = None) -> Path:
        path = tmp_path / name
        kwargs = {"exif": piexif.dump(exif)} if exif else {}
        Image.new("RGB", (8, 8)).save(path, **kwargs)
        return path

    return _make
