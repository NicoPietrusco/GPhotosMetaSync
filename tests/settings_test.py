"""Tests for gphotometasync.settings."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from gphotometasync.settings import settings


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Simulate a PyInstaller bundle with a temp home directory."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("GPHOTOMETASYNC_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_data_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GPHOTOMETASYNC_DATA_DIR", str(tmp_path))

    assert settings.data_dir == tmp_path / "data"
    assert settings.web_output_dir == tmp_path / "data" / "outputs"
    assert settings.google_token_path == tmp_path / "credentials" / "google_token.json"


def test_source_checkout_writes_next_to_the_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GPHOTOMETASYNC_DATA_DIR", raising=False)

    assert settings.app_data_dir == settings.resource_dir
    assert (settings.resource_dir / "pyproject.toml").is_file()


def test_frozen_macos_uses_application_support(
    frozen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    assert settings.app_data_dir == frozen / "Library" / "Application Support" / "GPhotoMetaSync"


def test_frozen_linux_uses_xdg_data_home(frozen: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(frozen / "xdg"))

    assert settings.app_data_dir == frozen / "xdg" / "gphotometasync"


def test_secret_key_from_environment_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "from-env")

    assert settings.secret_key == "from-env"


def test_frozen_secret_key_is_generated_once_and_private(
    frozen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("GPHOTOMETASYNC_DATA_DIR", str(frozen))

    first = settings.secret_key
    key_file = frozen / "state" / "flask_secret_key"

    assert len(first) >= 32
    assert settings.secret_key == first
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
