"""Tests for hicpicnunc.web.routes.jobs."""

from __future__ import annotations

import io
import zipfile

import piexif
import pytest

from hicpicnunc.web.routes.jobs import categorize_job_files, friendly_job_filename

AJAX = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


def _upload(client, files: list[tuple[bytes, str]], **form: str):
    data: dict = {"file": [(io.BytesIO(b), name) for b, name in files], **form}
    return client.post("/upload", data=data, headers=AJAX)


def test_upload_returns_download_links(client, make_jpeg) -> None:
    src = make_jpeg(
        "IMG_1.jpg", {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2020:01:01 10:00:00"}}
    )

    body = _upload(client, [(src.read_bytes(), "IMG_1.jpg")], stem_suffix="_exif").get_json()

    assert body["ok"] and body["processed"] == 1
    assert body["files"][0]["relative_path"] == "IMG_1_exif.jpg"
    assert body["files"][0]["json_relative_path"] == "IMG_1_exif.json"  # sidecar on by default here
    assert client.get(body["files"][0]["image_url"]).status_code == 200


def test_folder_upload_keeps_the_folder_structure(client, make_jpeg) -> None:
    src = make_jpeg().read_bytes()

    body = _upload(
        client,
        [(src, "a.jpg"), (src, "b.jpg")],
        relative_paths=["trip/day1/a.jpg", "trip/b.jpg"],
        include_json="false",
    ).get_json()

    assert sorted(f["relative_path"] for f in body["files"]) == ["trip/b.jpg", "trip/day1/a.jpg"]


def test_upload_leaves_no_staged_copies(client, make_jpeg, data_dir) -> None:
    _upload(client, [(make_jpeg().read_bytes(), "IMG.jpg"), (b"broken", "bad.jpg")])

    assert list((data_dir / "data" / "uploads").iterdir()) == []


def test_upload_rejects_unsupported_files(client) -> None:
    resp = _upload(client, [(b"GIF89a", "anim.gif")])

    assert resp.status_code == 400
    assert resp.get_json()["detail"] == "No supported images."


def test_upload_without_files_redirects_home_for_html_forms(client) -> None:
    resp = client.post("/upload", data={})

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_upload_reports_images_that_cannot_be_processed(client) -> None:
    resp = _upload(client, [(b"not really a jpeg", "broken.jpg")])

    assert resp.status_code == 400
    assert resp.get_json()["errors"][0].startswith("broken.jpg:")


def test_result_page_lists_the_job_files(client, make_jpeg) -> None:
    body = _upload(client, [(make_jpeg().read_bytes(), "IMG.jpg")], include_json="false").get_json()

    page = client.get(body["job_url"]).get_data(as_text=True)

    assert "IMG.jpg" in page
    assert f"/job/{body['job_id']}/download-all" in page


@pytest.mark.parametrize(
    ("query", "notice"),
    [
        ("?failed=2", "2 items couldn"),
        ("?failed=1", "1 item couldn"),
        ("", None),
        ("?failed=-3", None),
    ],
)
def test_result_page_reports_items_that_failed(client, make_jpeg, query: str, notice) -> None:
    body = _upload(client, [(make_jpeg().read_bytes(), "IMG.jpg")], include_json="false").get_json()

    page = client.get(body["job_url"] + query).get_data(as_text=True)

    if notice:
        assert notice in page
    else:
        assert "couldn’t be saved" not in page


@pytest.mark.parametrize("job_id", ["..", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_unknown_jobs_are_not_served(client, job_id: str) -> None:
    assert client.get(f"/job/{job_id}").status_code == 302
    assert client.get(f"/job/{job_id}/download-all").status_code == 404
    assert client.get(f"/files/{job_id}/x.jpg").status_code == 404


def test_files_outside_the_job_are_not_served(client, make_jpeg) -> None:
    job_id = _upload(client, [(make_jpeg().read_bytes(), "IMG.jpg")]).get_json()["job_id"]

    assert client.get(f"/files/{job_id}/../../settings/x.json").status_code == 404
    assert client.get(f"/files/{job_id}/missing.jpg").status_code == 404


def test_zip_download_accepts_capture_dates_before_1980(client, make_jpeg) -> None:
    src = make_jpeg(
        "old_scan.jpg", {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"1975:06:01 12:00:00"}}
    )
    job_id = _upload(client, [(src.read_bytes(), src.name)], include_json="false").get_json()[
        "job_id"
    ]

    download = client.get(f"/job/{job_id}/download-all")

    assert download.status_code == 200
    assert f'filename="hicpicnunc-{job_id[:8]}.zip"' in download.headers["Content-Disposition"]
    assert zipfile.ZipFile(io.BytesIO(download.data)).namelist() == ["old_scan.jpg"]


def test_result_page_lists_files_by_displayed_name(client, data_dir) -> None:
    job_id = "0f8fad5b-d9cb-469f-a165-70867728950e"
    job_dir = data_dir / "data" / "outputs" / job_id
    job_dir.mkdir(parents=True)
    for i, name in [(0, "IMG_0000"), (1, "IMG_0001"), (10, "IMG_0010"), (100, "IMG_0100")]:
        (job_dir / f"{job_id}_{i}_{name}_exif.jpg").write_bytes(b"x")

    page = client.get(f"/job/{job_id}").get_data(as_text=True)
    positions = [page.index(f">IMG_{n}_exif.jpg<") for n in ("0000", "0001", "0010", "0100")]

    assert positions == sorted(positions)


def test_friendly_job_filename_strips_the_storage_prefix() -> None:
    assert (
        friendly_job_filename("0f8fad5b-d9cb-469f-a165-70867728950e_3_IMG_exif.jpg")
        == "IMG_exif.jpg"
    )
    assert friendly_job_filename("trip/IMG.jpg") == "trip/IMG.jpg"
    assert friendly_job_filename("IMG.jpg") == "IMG.jpg"


def test_categorize_job_files() -> None:
    assert categorize_job_files(["a.jpg", "a.json", "notes.txt", "b.HEIC", "clip.MOV"]) == {
        "images": ["a.jpg", "b.HEIC"],
        "videos": ["clip.MOV"],
        "jsons": ["a.json"],
        "others": ["notes.txt"],
    }


def test_result_page_lists_videos_separately(client, data_dir) -> None:
    job_id = "0f8fad5b-d9cb-469f-a165-70867728950e"
    job_dir = data_dir / "data" / "outputs" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / f"{job_id}_0_IMG_1_exif.jpg").write_bytes(b"x")
    (job_dir / f"{job_id}_1_VID_1.mp4").write_bytes(b"x")

    page = " ".join(client.get(f"/job/{job_id}").get_data(as_text=True).split())

    assert "files: 1 image, 1 video" in page
    assert '<h3 class="job-section-title">Videos</h3>' in page
    assert ">VID_1.mp4<" in page
