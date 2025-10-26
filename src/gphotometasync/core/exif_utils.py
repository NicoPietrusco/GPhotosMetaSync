"""
EXIF data extraction and embedding utilities.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import piexif
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from ..settings import settings
from ..utils.logger_utils import get_logger

logger = get_logger(__name__)


def convert_to_degrees(value) -> Optional[float]:
    """
    Convert GPS coordinates from DMS to decimal degrees.

    Args:
        value: GPS coordinate value (can be tuple, list, or single value)

    Returns:
        Decimal degrees or None if conversion fails
    """
    try:
        if not value:
            return None

        if isinstance(value, (tuple, list)) and len(value) == 3:

            def get_fraction(frac):
                if hasattr(frac, "numerator") and hasattr(frac, "denominator"):
                    return frac.numerator / frac.denominator
                elif isinstance(frac, (int, float)):
                    return float(frac)
                return 0.0

            d, m, s = (get_fraction(v) for v in value)
            return d + (m / 60) + (s / 3600)
        return None
    except Exception:
        return None


def extract_gps_data(exif_dict: Dict) -> Dict:
    """
    Extract and convert GPS data from EXIF dictionary.

    Args:
        exif_dict: EXIF data dictionary

    Returns:
        Dictionary with GPS information including decimal coordinates
    """
    gps_dict = {}

    if "GPSInfo" not in exif_dict:
        return gps_dict

    gps_info = exif_dict["GPSInfo"]

    # Extract all GPS tags
    for gps_tag, gps_val in gps_info.items():
        gps_tag_name = GPSTAGS.get(gps_tag, f"GPS_{gps_tag}")
        gps_dict[gps_tag_name] = gps_val

    # Convert to decimal degrees
    lat = lon = None
    if "GPSLatitude" in gps_dict and "GPSLatitudeRef" in gps_dict:
        lat = convert_to_degrees(gps_dict["GPSLatitude"])
        if lat is not None and gps_dict["GPSLatitudeRef"] != "N":
            lat = -lat

    if "GPSLongitude" in gps_dict and "GPSLongitudeRef" in gps_dict:
        lon = convert_to_degrees(gps_dict["GPSLongitude"])
        if lon is not None and gps_dict["GPSLongitudeRef"] != "E":
            lon = -lon

    gps_dict["LatitudeDecimal"] = lat
    gps_dict["LongitudeDecimal"] = lon

    return gps_dict


def extract_exif_data(image_path: Path, output_dir: Optional[Path] = None) -> Dict:
    """
    Extract all EXIF data from an image and save to JSON file.

    Args:
        image_path: Path to the image file
        output_dir: Directory to save JSON files (default: ./output)

    Returns:
        Dictionary with extraction results or error info
    """
    if not image_path.exists():
        return {"error": f"File not found: {image_path}"}

    try:
        with Image.open(image_path) as img:
            if not hasattr(img, "_getexif"):
                return {"error": f"{image_path.name}: no EXIF metadata"}

            exif_data = img._getexif() or {}
            exif_dict = {}

            # Extract standard EXIF tags
            for tag, val in exif_data.items():
                tag_name = TAGS.get(tag, f"Unknown_{tag}")
                exif_dict[tag_name] = val

            # Extract and process GPS data
            gps_dict = extract_gps_data(exif_dict)
            if gps_dict:
                exif_dict["GPS"] = gps_dict

            # Add file information
            exif_dict["_file_info"] = {
                "filename": image_path.name,
                "size_bytes": image_path.stat().st_size,
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
            }

        # Prepare output
        output_dir = output_dir or settings.DEFAULT_OUTPUT_DIR
        from ..utils.file_utils import ensure_directory, get_json_output_path

        ensure_directory(output_dir)
        json_path = get_json_output_path(image_path, output_dir)

        # Save to JSON with serialized values
        from ..utils.file_utils import serialize_exif_value

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: serialize_exif_value(v) for k, v in exif_dict.items()},
                f,
                indent=2,
                ensure_ascii=False,
            )

        return {
            "success": True,
            "image_path": str(image_path),
            "json_path": str(json_path),
            "exif_fields_count": len(exif_dict),
        }
    except Exception as e:
        return {"error": f"Failed: {e}"}


def embed_exif_dates(image_path: Path, output_dir: Path) -> bool:
    """
    Create a new image file with EXIF 'DateTimeOriginal', 'DateTimeDigitized',
    and 'DateTime' fields restored from existing metadata, AND update filesystem timestamps.

    Args:
        image_path: Path to the source image
        output_dir: Directory for the output image

    Returns:
        True if successful, False otherwise
    """
    try:
        from ..utils.file_utils import ensure_directory, get_dated_output_path

        with Image.open(image_path) as img:
            exif_data = img.getexif()
            date = None

            # Try to find best available date
            for tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                tag_id = next((t for t, n in TAGS.items() if n == tag_name), None)
                if tag_id and tag_id in exif_data:
                    date = exif_data[tag_id]
                    break

        if not date:
            logger.warning(f"⚠️  No EXIF date found for {image_path.name}")
            return False

        # Parse EXIF date (format: "YYYY:MM:DD HH:MM:SS")
        try:
            date_str = date if isinstance(date, str) else str(date)
            dt = datetime.strptime(date_str, settings.EXIF_DATE_FORMAT)
            timestamp = dt.timestamp()
        except Exception as e:
            logger.warning(f"⚠️  Could not parse date '{date}' for {image_path.name}: {e}")
            return False

        # Update EXIF in copy
        exif_dict = piexif.load(str(image_path))
        date_bytes = date_str.encode()
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_bytes
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = date_bytes
        exif_dict["0th"][piexif.ImageIFD.DateTime] = date_bytes

        # Create output path and ensure directory exists
        ensure_directory(output_dir)
        output_path = get_dated_output_path(image_path, output_dir)

        # Insert EXIF data
        piexif.insert(piexif.dump(exif_dict), str(image_path), str(output_path))

        # Update filesystem timestamps (modified and accessed times)
        os.utime(output_path, (timestamp, timestamp))

        logger.info(
            f"🕒 Updated EXIF & filesystem date for {image_path.name} → {output_path.name} (Date: {date_str})"
        )
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update {image_path.name}: {e}")
        return False
