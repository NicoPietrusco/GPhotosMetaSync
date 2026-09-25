"""Regression tests for the metadata export pipeline."""

from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path

import piexif
import pytest
from PIL import Image

from gphotometasync.core.photo_utils import process_uploaded_image
from gphotometasync.exif_config import load_user_exif_field_config, save_metadata_preferences


def _jpeg(path: Path, exif: dict | None = None) -> Path:
    kwargs = {"exif": piexif.dump(exif)} if exif else {}
    Image.new("RGB", (8, 8)).save(path, **kwargs)
    return path


def _config(tmp_path: Path, **preferences: bool):
    prefs_path = tmp_path / "prefs.json"
    save_metadata_preferences(preferences, prefs_path)
    return load_user_exif_field_config(prefs_path)


def test_image_without_exif_is_still_exported(tmp_path: Path) -> None:
    src = _jpeg(tmp_path / "plain.jpg")
    result = process_uploaded_image(src, tmp_path / "out", _config(tmp_path), write_json=False)

    assert "error" not in result
    assert Path(result["output_image"]).is_file()


def test_png_without_exif_is_still_exported(tmp_path: Path) -> None:
    src = tmp_path / "screenshot.png"
    Image.new("RGB", (8, 8)).save(src)
    result = process_uploaded_image(src, tmp_path / "out", _config(tmp_path), write_json=False)

    assert Path(result["output_image"]).is_file()


def test_excluded_gps_is_not_carried_over_when_nothing_else_survives(tmp_path: Path) -> None:
    src = _jpeg(
        tmp_path / "gps_only.jpg",
        {
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b"N",
                piexif.GPSIFD.GPSLatitude: ((45, 1), (0, 1), (0, 1)),
            }
        },
    )
    config = _config(tmp_path, gps_location=False)
    result = process_uploaded_image(src, tmp_path / "out", config, write_json=False)

    assert not piexif.load(result["output_image"])["GPS"]


def test_orientation_is_kept_without_camera_details(tmp_path: Path) -> None:
    src = _jpeg(
        tmp_path / "portrait.jpg",
        {
            "0th": {piexif.ImageIFD.Orientation: 6, piexif.ImageIFD.Make: b"Cam"},
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2020:05:06 07:08:09",
                piexif.ExifIFD.OffsetTimeOriginal: b"+02:00",
            },
        },
    )
    config = _config(tmp_path, camera_details=False)
    exif = piexif.load(process_uploaded_image(src, tmp_path / "out", config)["output_image"])

    assert exif["0th"][piexif.ImageIFD.Orientation] == 6
    assert piexif.ImageIFD.Make not in exif["0th"]
    assert exif["Exif"][piexif.ExifIFD.OffsetTimeOriginal] == b"+02:00"


def test_file_date_matches_capture_date(tmp_path: Path) -> None:
    src = _jpeg(
        tmp_path / "dated.jpg", {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2019:01:02 03:04:05"}}
    )
    result = process_uploaded_image(src, tmp_path / "out", _config(tmp_path), write_json=False)

    assert result["filesystem_date_set"]
    assert os.path.getmtime(result["output_image"]) == datetime(2019, 1, 2, 3, 4, 5).timestamp()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GPHOTOMETASYNC_DATA_DIR", str(tmp_path / "appdata"))
    from gphotometasync.web.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_zip_download_accepts_capture_dates_before_1980(client) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(
        buf,
        "JPEG",
        exif=piexif.dump({"Exif": {piexif.ExifIFD.DateTimeOriginal: b"1975:06:01 12:00:00"}}),
    )
    upload = client.post(
        "/upload",
        data={"file": (io.BytesIO(buf.getvalue()), "old_scan.jpg"), "include_json": "false"},
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
    from gphotometasync.web.app import _is_allowed_google_media_url

    assert _is_allowed_google_media_url("https://lh3.googleusercontent.com/abc=w200")
    assert not _is_allowed_google_media_url("https://evil.example/abc")
    assert not _is_allowed_google_media_url("http://lh3.googleusercontent.com/abc")
    assert not _is_allowed_google_media_url("https://googleusercontent.com.evil.example/x")
