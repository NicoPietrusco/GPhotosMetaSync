"""Tests for gphotometasync.core.metadata_fields."""

from __future__ import annotations

from pathlib import Path

import pytest

from gphotometasync.core.metadata_fields import (
    build_exif_field_config,
    load_user_exif_field_config,
    save_metadata_preferences,
)


def test_orientation_and_time_zone_are_kept_without_camera_details() -> None:
    tags = build_exif_field_config({"camera_details": False}).tags

    assert "0th:Orientation" in tags
    assert "Exif:OffsetTimeOriginal" in tags
    assert "0th:Make" not in tags


def test_groups_and_always_kept_tags_come_from_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "fields.yaml"
    custom.write_text(
        'always_kept: ["Exif:DateTimeOriginal"]\ngroups:\n  lens: ["Exif:LensModel"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("EXIF_FIELDS_CONFIG", str(custom))
    prefs_path = tmp_path / "prefs.json"

    assert save_metadata_preferences({"lens": False, "gps_location": True}, prefs_path) == {
        "lens": False,
        "include_json": False,
    }
    assert load_user_exif_field_config(prefs_path).tags == ["Exif:DateTimeOriginal"]
