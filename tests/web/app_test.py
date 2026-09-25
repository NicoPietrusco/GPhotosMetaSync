"""Tests for gphotometasync.web.app."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import piexif
import pytest

from gphotometasync.web.app import _is_allowed_google_media_url, create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GPHOTOMETASYNC_DATA_DIR", str(tmp_path / "appdata"))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_zip_download_accepts_capture_dates_before_1980(client, make_jpeg) -> None:
    src = make_jpeg(
        "old_scan.jpg", {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"1975:06:01 12:00:00"}}
    )
    upload = client.post(
        "/upload",
        data={"file": (io.BytesIO(src.read_bytes()), src.name), "include_json": "false"},
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    job_id = upload.get_json()["job_id"]

    download = client.get(f"/job/{job_id}/download-all")

    assert download.status_code == 200
    assert zipfile.ZipFile(io.BytesIO(download.data)).namelist() == ["old_scan.jpg"]


@pytest.mark.parametrize("host", ["localhost:5001", "127.0.0.1", "[::1]:5001"])
def test_loopback_hosts_are_served(client, host: str) -> None:
    assert client.get("/", headers={"Host": host}).status_code == 200


def test_foreign_host_header_is_rejected(client) -> None:
    # A DNS-rebinding page reaches 127.0.0.1 but still sends its own hostname.
    assert client.get("/api/check-auth", headers={"Host": "evil.example:5001"}).status_code == 403


def test_bearer_token_is_only_sent_to_google_hosts() -> None:
    assert _is_allowed_google_media_url("https://lh3.googleusercontent.com/abc=w200")
    assert not _is_allowed_google_media_url("https://evil.example/abc")
    assert not _is_allowed_google_media_url("http://lh3.googleusercontent.com/abc")
    assert not _is_allowed_google_media_url("https://googleusercontent.com.evil.example/x")
