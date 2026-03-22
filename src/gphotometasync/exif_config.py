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

from .utils.logger_utils import get_logger

logger = get_logger(__name__)

_DEFAULT_YAML = Path(__file__).resolve().parent / "config" / "default_exif_fields.yaml"


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
