"""
Photo processing orchestration for web and programmatic use.
"""

from pathlib import Path

from ..exif_config import ExifFieldConfig, load_exif_field_config
from ..utils.logger_utils import get_logger
from .exif_utils import process_image_extract_and_embed

logger = get_logger(__name__)


def process_uploaded_image(
    image_path: Path,
    output_dir: Path,
    field_config: ExifFieldConfig | None = None,
    stem_suffix: str = "_exif",
    output_stem: str | None = None,
) -> dict:
    """
    Run extract JSON + embed subset for one file (used by Flask).

    Returns a result dict with success, paths, embed_ok, or error.
    """
    if field_config is None:
        field_config = load_exif_field_config()
    return process_image_extract_and_embed(
        image_path,
        output_dir,
        field_config,
        stem_suffix=stem_suffix,
        output_stem=output_stem,
    )
