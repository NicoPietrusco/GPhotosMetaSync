"""Tests for gphotometasync.web.app."""

from __future__ import annotations

import pytest

from gphotometasync.web.app import is_local_host_header


@pytest.mark.parametrize(
    "host", ["localhost:5001", "127.0.0.1", "[::1]:5001", "[::1]", "LOCALHOST"]
)
def test_loopback_hosts_are_served(client, host: str) -> None:
    assert is_local_host_header(host)
    assert client.get("/", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example:5001", "127.0.0.1.evil.example", "localhost.evil"])
def test_foreign_host_header_is_rejected(client, host: str) -> None:
    # A DNS-rebinding page reaches 127.0.0.1 but still sends its own hostname.
    assert client.get("/api/check-auth", headers={"Host": host}).status_code == 403


def test_create_app_prepares_writable_folders(app, data_dir) -> None:
    assert (data_dir / "data" / "uploads").is_dir()
    assert (data_dir / "data" / "outputs").is_dir()


def test_templates_see_google_setup_state(client) -> None:
    # No client_secrets.json in the temp data dir's resource tree is required for the page.
    assert b"Photo Meta Sync" in client.get("/").data
