"""
Loadable EXIF field allowlist / exclusions for extract and embed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .settings import settings
from .utils.logger_utils import get_logger

logger = get_logger(__name__)

_DEFAULT_YAML = Path(__file__).resolve().parent / "config" / "default_exif_fields.yaml"

CAPTURE_DATE_TAGS = (
    "0th:DateTime",
    "Exif:DateTimeOriginal",
    "Exif:DateTimeDigitized",
)
METADATA_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "camera_details": (
        "0th:Make",
        "0th:Model",
        "0th:Orientation",
        "Exif:ExposureTime",
        "Exif:FNumber",
        "Exif:ISOSpeedRatings",
        "Exif:FocalLength",
        "Exif:LensModel",
        "Exif:Flash",
        "Exif:WhiteBalance",
        "Exif:ExifVersion",
    ),
    "gps_location": (
        "GPS:GPSLatitude",
        "GPS:GPSLatitudeRef",
        "GPS:GPSLongitude",
        "GPS:GPSLongitudeRef",
        "GPS:GPSAltitude",
        "GPS:GPSAltitudeRef",
    ),
}
DEFAULT_METADATA_PREFERENCES = {
    **{key: True for key in METADATA_FIELD_GROUPS},
    "include_json": False,
}


@dataclass
class ExifFieldConfig:
    """Controls which EXIF tags are extracted and re-embedded."""

    mode: str = "allowlist"  # "allowlist" | "all"
    tags: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=list)
    skip_makernote_embed: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExifFieldConfig:
        return cls(
            mode=str(data.get("mode", "allowlist")),
            tags=list(data.get("tags", [])),
            exclude_tags=list(data.get("exclude_tags", [])),
            skip_makernote_embed=bool(data.get("skip_makernote_embed", True)),
        )


def load_metadata_preferences(path: Path | None = None) -> dict[str, bool]:
    """Load saved user choices, falling back to the shipped defaults."""
    preferences = DEFAULT_METADATA_PREFERENCES.copy()
    preferences_path = path or settings.metadata_preferences_path
    try:
        data = json.loads(preferences_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in preferences:
                if isinstance(data.get(key), bool):
                    preferences[key] = data[key]
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read metadata preferences: {}", e)
    return preferences


def save_metadata_preferences(
    preferences: dict[str, Any], path: Path | None = None
) -> dict[str, bool]:
    """Validate and persist the user's metadata choices atomically."""
    normalized = DEFAULT_METADATA_PREFERENCES.copy()
    for key in normalized:
        value = preferences.get(key)
        if isinstance(value, bool):
            normalized[key] = value

    preferences_path = path or settings.metadata_preferences_path
    preferences_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = preferences_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    try:
        temporary_path.chmod(0o600)
    except OSError:
        pass
    temporary_path.replace(preferences_path)
    return normalized


def load_user_exif_field_config(path: Path | None = None) -> ExifFieldConfig:
    """Build the shared EXIF allowlist from locally saved user preferences."""
    if os.environ.get("EXIF_FIELDS_CONFIG"):
        return load_exif_field_config()

    preferences = load_metadata_preferences(path)
    tags = list(CAPTURE_DATE_TAGS)
    for group, group_tags in METADATA_FIELD_GROUPS.items():
        if preferences[group]:
            tags.extend(group_tags)
    return ExifFieldConfig(tags=tags)


def load_exif_field_config(path: Path | None = None) -> ExifFieldConfig:
    """
    Load YAML or JSON config. Falls back to bundled default.

    Env: EXIF_FIELDS_CONFIG — path to a YAML/JSON file overriding defaults.
    """
    env_path = os.environ.get("EXIF_FIELDS_CONFIG")
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(_DEFAULT_YAML)

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
            if candidate.suffix.lower() in {".yaml", ".yml"}:
                data = yaml.safe_load(text) or {}
            else:
                data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("Root must be a mapping")
            logger.info(f"Loaded EXIF field config from {candidate}")
            return ExifFieldConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load EXIF config from {candidate}: {e}")
            raise

    return ExifFieldConfig()
