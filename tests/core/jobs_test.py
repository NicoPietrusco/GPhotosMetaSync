"""Tests for gphotometasync.core.jobs."""

from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from gphotometasync.core.jobs import (
    build_job_zip,
    get_job_dir,
    is_image_file,
    list_job_files,
    new_job,
    resolve_job_file,
    staging_path,
)


@pytest.mark.parametrize(
    ("name", "expected"), [("a.JPG", True), ("b.heic", True), ("c.gif", False)]
)
def test_is_image_file(name: str, expected: bool) -> None:
    assert is_image_file(Path(name)) is expected


def test_new_job_is_found_again_by_id(data_dir: Path) -> None:
    job_id, job_dir = new_job()

    assert get_job_dir(job_id) == job_dir
    assert job_dir.parent == data_dir / "data" / "outputs"


@pytest.mark.parametrize("job_id", ["..", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_unknown_or_malformed_job_ids_are_rejected(data_dir: Path, job_id: str) -> None:
    assert get_job_dir(job_id) is None


def test_staging_path_is_outside_the_job_output(data_dir: Path) -> None:
    job_id, job_dir = new_job()
    path = staging_path(job_id, 3, "IMG.jpg")

    assert path.name == f"{job_id}_3_IMG.jpg"
    assert job_dir not in path.parents


@pytest.mark.parametrize("rel", ["../secret.txt", "a/../../b", "a\0b", "", "a b.jpg"])
def test_resolve_job_file_rejects_escapes_and_unsafe_names(tmp_path: Path, rel: str) -> None:
    assert resolve_job_file(tmp_path, rel) is None


def test_resolve_job_file_accepts_nested_paths(tmp_path: Path) -> None:
    root = tmp_path.resolve()

    assert resolve_job_file(tmp_path, "trip/day1/IMG.jpg") == root / "trip/day1/IMG.jpg"
    assert resolve_job_file(tmp_path, "/etc/passwd") == root / "etc/passwd"  # stays inside


def test_zip_contains_every_file_with_its_capture_date(tmp_path: Path) -> None:
    (tmp_path / "trip").mkdir()
    for rel, when in [
        ("a.jpg", datetime(2019, 1, 2, 3, 4, 6)),
        ("trip/b.jpg", datetime(1975, 6, 1)),
    ]:
        path = tmp_path / rel
        path.write_bytes(b"x")
        os.utime(path, (when.timestamp(), when.timestamp()))

    archive = zipfile.ZipFile(build_job_zip(tmp_path))

    assert list_job_files(tmp_path) == ["a.jpg", "trip/b.jpg"]
    assert archive.getinfo("a.jpg").date_time == (2019, 1, 2, 3, 4, 6)
    assert archive.getinfo("trip/b.jpg").date_time[0] == 1980  # ZIP's earliest date


def test_empty_job_zip_is_valid(tmp_path: Path) -> None:
    assert zipfile.ZipFile(io.BytesIO(build_job_zip(tmp_path).read())).namelist() == []
