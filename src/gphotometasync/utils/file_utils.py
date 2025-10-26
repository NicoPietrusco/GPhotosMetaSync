"""
File handling utilities for GPhotoMetaSync.
"""

import glob
import json
from pathlib import Path
from typing import List, Union

from ..settings import settings


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure

    Returns:
        Path object of the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def find_images(targets: List[Path]) -> List[Path]:
    """
    Find all image files from targets (files, directories, or glob patterns).

    Args:
        targets: List of file paths, directories, or glob patterns

    Returns:
        Sorted list of unique image file paths
    """
    image_extensions = settings.SUPPORTED_FORMATS
    paths = []

    for target in targets:
        if target.is_dir():
            # Find all images in directory
            paths.extend([p for p in target.iterdir() if p.suffix.lower() in image_extensions])
        elif target.exists():
            # Direct file path
            paths.append(target)
        else:
            # Try as glob pattern
            for matched in glob.glob(str(target)):
                p = Path(matched)
                if p.is_file() and p.suffix.lower() in image_extensions:
                    paths.append(p)

    return sorted(list(set(paths)))


def serialize_exif_value(value) -> Union[str, float, int, list, dict]:
    """
    Convert EXIF values to JSON-safe types.

    Args:
        value: The EXIF value to serialize

    Returns:
        JSON-serializable value
    """
    # Handle PIL's special EXIF types (IFDRational)
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        try:
            return float(value)
        except Exception:
            return str(value)

    # Handle bytes
    if isinstance(value, bytes):
        return value.decode(errors="ignore")

    # Handle tuples/lists (common in GPS coordinates)
    if isinstance(value, (tuple, list)):
        return [serialize_exif_value(v) for v in value]

    # Handle dictionaries
    if isinstance(value, dict):
        return {k: serialize_exif_value(v) for k, v in value.items()}

    # Test if it's JSON serializable
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def get_json_output_path(image_path: Path, output_dir: Path) -> Path:
    """
    Get the JSON output path for an image.

    Args:
        image_path: Path to the source image
        output_dir: Directory for JSON output

    Returns:
        Path to the corresponding JSON file
    """
    return output_dir / f"{image_path.stem}{settings.JSON_SUFFIX}"


def get_dated_output_path(image_path: Path, output_dir: Path) -> Path:
    """
    Get the dated output path for an image.

    Args:
        image_path: Path to the source image
        output_dir: Directory for dated image output

    Returns:
        Path to the dated image file
    """
    return output_dir / f"{image_path.stem}{settings.DATED_SUFFIX}{image_path.suffix}"


def is_image_file(file_path: Path) -> bool:
    """
    Check if a file is a supported image format.

    Args:
        file_path: Path to check

    Returns:
        True if file is a supported image format
    """
    return file_path.suffix.lower() in settings.SUPPORTED_FORMATS
