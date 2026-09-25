"""Tests for gphotometasync.core.exif."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import piexif
import pytest
from PIL import Image

from gphotometasync.core.exif import (
    convert_to_degrees,
    load_exif_nested,
    process_image_extract_and_embed,
)
from gphotometasync.core.metadata_fields import ExifFieldConfig, build_exif_field_config


def _export(src: Path, config: ExifFieldConfig) -> dict:
    return process_image_extract_and_embed(src, src.parent / "out", config, write_json=False)


def test_image_without_exif_is_still_exported(make_jpeg) -> None:
    result = _export(make_jpeg("plain.jpg"), build_exif_field_config({}))

    assert "error" not in result
    assert Path(result["output_image"]).is_file()


def test_png_without_exif_is_still_exported(tmp_path: Path) -> None:
    src = tmp_path / "screenshot.png"
    Image.new("RGB", (8, 8)).save(src)

    assert Path(_export(src, build_exif_field_config({}))["output_image"]).is_file()


def test_excluded_gps_is_not_carried_over_when_nothing_else_survives(make_jpeg) -> None:
    src = make_jpeg(
        "gps_only.jpg",
        {
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b"N",
                piexif.GPSIFD.GPSLatitude: ((45, 1), (0, 1), (0, 1)),
            }
        },
    )
    result = _export(src, build_exif_field_config({"gps_location": False}))

    assert not piexif.load(result["output_image"])["GPS"]


def test_only_allowlisted_tags_are_embedded(make_jpeg) -> None:
    src = make_jpeg(
        "portrait.jpg",
        {"0th": {piexif.ImageIFD.Orientation: 6, piexif.ImageIFD.Make: b"Cam"}},
    )
    exif = piexif.load(_export(src, ExifFieldConfig(tags=["0th:Orientation"]))["output_image"])

    assert exif["0th"] == {piexif.ImageIFD.Orientation: 6}


def test_file_date_matches_capture_date(make_jpeg) -> None:
    src = make_jpeg(
        "dated.jpg", {"Exif": {piexif.ExifIFD.DateTimeOriginal: b"2019:01:02 03:04:05"}}
    )
    result = _export(src, build_exif_field_config({}))

    assert result["filesystem_date_set"]
    assert os.path.getmtime(result["output_image"]) == datetime(2019, 1, 2, 3, 4, 5).timestamp()


def test_json_sidecar_has_readable_values_and_decimal_gps(make_jpeg) -> None:
    src = make_jpeg(
        "trip.jpg",
        {
            "0th": {piexif.ImageIFD.Make: b"Cam"},
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b"S",
                piexif.GPSIFD.GPSLatitude: ((33, 1), (30, 1), (0, 1)),
                piexif.GPSIFD.GPSLongitudeRef: b"E",
                piexif.GPSIFD.GPSLongitude: ((151, 1), (15, 1), (0, 1)),
            },
        },
    )
    result = process_image_extract_and_embed(
        src, src.parent / "out", build_exif_field_config({}), write_json=True
    )
    sidecar = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))

    assert sidecar["0th"]["Make"] == "Cam"
    assert sidecar["GPS"]["LatitudeDecimal"] == -33.5
    assert sidecar["GPS"]["LongitudeDecimal"] == 151.25


def test_output_stem_and_suffix_control_the_output_name(make_jpeg) -> None:
    result = process_image_extract_and_embed(
        make_jpeg("upload_0_IMG.jpg"),
        make_jpeg().parent / "out",
        build_exif_field_config({}),
        stem_suffix="",
        output_stem="IMG_1234",
        write_json=False,
    )

    assert Path(result["output_image"]).name == "IMG_1234.jpg"


def test_unreadable_image_reports_an_error(tmp_path: Path) -> None:
    src = tmp_path / "broken.jpg"
    src.write_bytes(b"not an image")

    assert "error" in _export(src, build_exif_field_config({}))


def test_convert_to_degrees_handles_rationals_and_bad_input() -> None:
    assert convert_to_degrees(((10, 1), (30, 1), (36, 1))) == pytest.approx(10.51)  # piexif
    assert convert_to_degrees((10, 30, 36)) == pytest.approx(10.51)
    assert convert_to_degrees(None) is None
    assert convert_to_degrees("garbage") is None


CAPTURE = {
    "0th": {piexif.ImageIFD.Make: b"Apple"},
    "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2021:07:08 09:10:11"},
    "GPS": {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((45, 1), (0, 1), (0, 1)),
    },
}


@pytest.mark.parametrize("name", ["IMG.heic", "IMG.heif", "screenshot.png"])
def test_capture_date_and_gps_survive_non_jpeg_formats(tmp_path: Path, name: str) -> None:
    # PNG and HEIC go through Pillow; their Exif/GPS sub-IFDs used to be dropped.
    src = tmp_path / name
    Image.new("RGB", (16, 16)).save(src, exif=piexif.dump(CAPTURE))

    result = _export(src, build_exif_field_config({}))
    nested, _, _ = load_exif_nested(Path(result["output_image"]))

    assert result["filesystem_date_set"]
    assert nested["Exif"]["DateTimeOriginal"] == b"2021:07:08 09:10:11"
    assert nested["GPS"]["GPSLatitudeRef"] == b"N"
    assert nested["0th"]["Make"] == b"Apple"


def test_rotated_heic_is_not_rotated_twice(tmp_path: Path) -> None:
    src = tmp_path / "portrait.heic"
    Image.new("RGB", (300, 200)).save(
        src, exif=piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}})
    )

    out = Path(_export(src, build_exif_field_config({}))["output_image"])

    # pillow-heif decodes upright pixels; the copy must not also carry Orientation=6.
    with Image.open(out) as img:
        assert img.size == (200, 300)
        assert img.getexif().get(piexif.ImageIFD.Orientation, 1) == 1
