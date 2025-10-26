"""Core functionality for GPhotoMetaSync."""

from .exif_utils import embed_exif_dates, extract_exif_data
from .photo_utils import process_photos_embed, process_photos_extract

__all__ = [
    "extract_exif_data",
    "embed_exif_dates",
    "process_photos_extract",
    "process_photos_embed",
]
