"""Tests for gphotometasync.google_photos.oauth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from gphotometasync.google_photos import oauth


def test_sign_in_requests_only_read_access_to_picked_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, path: str, scopes: list[str]) -> FakeFlow:
            seen.update(path=path, scopes=scopes)
            return cls()

        def run_local_server(self, **kwargs: Any) -> str:
            seen.update(kwargs)
            return "credentials"

    monkeypatch.setattr(oauth, "InstalledAppFlow", FakeFlow)
    secrets = tmp_path / "client_secrets.json"

    assert oauth.GooglePhotosOAuth(secrets).run_local_server() == "credentials"
    assert seen["path"] == str(secrets)
    assert seen["scopes"] == ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]
    assert seen["port"] == 0  # any free port, so it never collides with the app
    assert seen["timeout_seconds"] == oauth.SIGN_IN_TIMEOUT_SECONDS  # never waits forever
