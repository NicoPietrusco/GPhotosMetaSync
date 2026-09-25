"""
EXIF data extraction and embedding utilities (piexif-first for full IFD coverage).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import piexif
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from ..exif_config import ExifFieldConfig
from ..settings import settings
from ..utils.file_utils import ensure_directory, get_json_output_path, serialize_exif_value
from ..utils.logger_utils import get_logger

logger = get_logger(__name__)

IFD_CLASS_MAP: dict[str, type] = {
    "0th": piexif.ImageIFD,
    "Exif": piexif.ExifIFD,
    "GPS": piexif.GPSIFD,
    "Interop": piexif.InteropIFD,
    # Thumbnail IFD uses same tag namespace as ImageIFD in piexif
    "1st": piexif.ImageIFD,
}


def _tag_id_to_name(ifd_cls: type, tag_id: int) -> str:
    for attr in dir(ifd_cls):
        if attr.startswith("_"):
            continue
        try:
            if getattr(ifd_cls, attr, None) == tag_id:
                return attr
        except Exception:
            continue
    return f"Unknown_{tag_id}"


def _tag_name_to_id(ifd_cls: type, name: str) -> int | None:
    if not hasattr(ifd_cls, name):
        return None
    val = getattr(ifd_cls, name)
    return val if isinstance(val, int) else None


def _serialize_tag_value(val: Any) -> Any:
    """Make EXIF values JSON-safe, keeping human-readable byte values as text."""
    if isinstance(val, bytes):
        try:
            text = val.decode("utf-8").rstrip("\0")
            if text.isprintable():
                return text
        except UnicodeDecodeError:
            pass
        return {"__bytes_b64__": base64.standard_b64encode(val).decode("ascii")}
    if isinstance(val, tuple):
        return tuple(_serialize_tag_value(v) for v in val)
    return serialize_exif_value(val)


def _deserialize_tag_value(val: Any) -> Any:
    if isinstance(val, dict) and "__bytes_b64__" in val:
        return base64.standard_b64decode(val["__bytes_b64__"])
    if isinstance(val, list):
        return tuple(_deserialize_tag_value(v) for v in val)
    return val


def convert_to_degrees(value: Any) -> Optional[float]:
    """Convert GPS coordinates from DMS to decimal degrees."""
    try:
        if not value:
            return None
        if isinstance(value, (tuple, list)) and len(value) == 3:

            def get_fraction(frac: Any) -> float:
                if hasattr(frac, "numerator") and hasattr(frac, "denominator"):
                    return frac.numerator / frac.denominator
                if isinstance(frac, (int, float)):
                    return float(frac)
                return 0.0

            d, m, s = (get_fraction(v) for v in value)
            return d + (m / 60) + (s / 3600)
        return None
    except Exception:
        return None


def extract_gps_data_from_named_gps(gps_named: Dict[str, Any]) -> Dict[str, Any]:
    """Add decimal lat/lon to a GPS IFD dict keyed by piexif GPS tag names."""
    gps_dict = dict(gps_named)
    lat = lon = None
    if "GPSLatitude" in gps_dict and "GPSLatitudeRef" in gps_dict:
        raw_lat = _deserialize_tag_value(gps_dict["GPSLatitude"])
        lat = convert_to_degrees(raw_lat)
        ref = gps_dict["GPSLatitudeRef"]
        if isinstance(ref, bytes):
            ref = ref.decode("ascii", errors="ignore")
        if lat is not None and ref != "N":
            lat = -lat
    if "GPSLongitude" in gps_dict and "GPSLongitudeRef" in gps_dict:
        raw_lon = _deserialize_tag_value(gps_dict["GPSLongitude"])
        lon = convert_to_degrees(raw_lon)
        ref = gps_dict["GPSLongitudeRef"]
        if isinstance(ref, bytes):
            ref = ref.decode("ascii", errors="ignore")
        if lon is not None and ref != "E":
            lon = -lon
    gps_dict["LatitudeDecimal"] = lat
    gps_dict["LongitudeDecimal"] = lon
    return gps_dict


def piexif_raw_to_nested_named(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Convert piexif.load() output to {IFD: {TagName: value}}."""
    nested: dict[str, dict[str, Any]] = {}
    for ifd_key, ifd_data in raw.items():
        if ifd_key == "thumbnail" or ifd_data is None:
            continue
        if not isinstance(ifd_data, dict):
            continue
        cls = IFD_CLASS_MAP.get(ifd_key)
        if cls is None:
            continue
        named: dict[str, Any] = {}
        for tag_id, val in ifd_data.items():
            tname = _tag_id_to_name(cls, int(tag_id))
            named[tname] = val
        nested[ifd_key] = named
    return nested


def _parse_spec(tag_spec: str) -> tuple[str | None, str]:
    """Return (ifd_key or None, tag_name)."""
    s = tag_spec.strip()
    if ":" in s:
        ifd, name = s.split(":", 1)
        return ifd.strip(), name.strip()
    return None, s


def _spec_key(ifd_key: str, tag_name: str) -> str:
    return f"{ifd_key}:{tag_name}"


def filter_nested_exif(
    nested: dict[str, dict[str, Any]],
    config: ExifFieldConfig,
) -> dict[str, dict[str, Any]]:
    """Apply allowlist / exclude to nested EXIF dict."""
    # Build lookup: spec -> (ifd, name)
    specs_flat: list[tuple[str | None, str]] = [_parse_spec(t) for t in config.tags]
    exclude_set: set[str] = set()
    for x in config.exclude_tags:
        ik, tn = _parse_spec(x)
        if ik:
            exclude_set.add(_spec_key(ik, tn))
    exclude_pairs = []
    for x in config.exclude_tags:
        ik, tn = _parse_spec(x)
        if ik:
            exclude_pairs.append((ik, tn))
        else:
            exclude_pairs.append((None, tn))

    def excluded(ifd_key: str, tag_name: str) -> bool:
        if _spec_key(ifd_key, tag_name) in exclude_set:
            return True
        for ik, tn in exclude_pairs:
            if tn != tag_name:
                continue
            if ik is None or ik == ifd_key:
                return True
        return False

    if config.mode == "all":
        out: dict[str, dict[str, Any]] = {}
        for ifd_key, tags in nested.items():
            filt = {
                k: v
                for k, v in tags.items()
                if not excluded(ifd_key, k)
                and not (config.skip_makernote_embed and ifd_key == "Exif" and k == "MakerNote")
            }
            if filt:
                out[ifd_key] = filt
        return out

    # allowlist
    out = {k: {} for k in IFD_CLASS_MAP}
    for ifd_hint, tag_name in specs_flat:
        if ifd_hint:
            if ifd_hint in nested and tag_name in nested[ifd_hint]:
                if not excluded(ifd_hint, tag_name):
                    out.setdefault(ifd_hint, {})[tag_name] = nested[ifd_hint][tag_name]
            continue
        for ifd_key, tags in nested.items():
            if tag_name in tags and not excluded(ifd_key, tag_name):
                out.setdefault(ifd_key, {})[tag_name] = tags[tag_name]
                break
    return {k: v for k, v in out.items() if v}


def nested_named_to_piexif_raw(nested: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Convert filtered nested dict back to piexif integer keys."""
    raw: dict[str, Any] = {}
    for ifd_key, tags in nested.items():
        cls = IFD_CLASS_MAP.get(ifd_key)
        if cls is None:
            continue
        ifd_out: dict[int, Any] = {}
        for tag_name, val in tags.items():
            if val is None:
                continue
            tid = _tag_name_to_id(cls, tag_name)
            if tid is None:
                logger.debug(f"Unknown tag name {ifd_key}:{tag_name}, skip embed")
                continue
            if isinstance(val, dict) and "__bytes_b64__" in val:
                val = _deserialize_tag_value(val)
            ifd_out[tid] = val
        if ifd_out:
            raw[ifd_key] = ifd_out
    return raw


def _nested_from_pillow(image_path: Path) -> dict[str, dict[str, Any]]:
    """Build nested IFD-shaped dict from Pillow getexif() when piexif cannot load."""
    nested: dict[str, dict[str, Any]] = {}
    with Image.open(image_path) as img:
        ex = img.getexif()
        if not ex:
            return {}
        for tag_id, val in ex.items():
            name = TAGS.get(tag_id, f"Unknown_{tag_id}")
            if name == "GPSInfo" and isinstance(val, dict):
                gps_named: dict[str, Any] = {}
                for gid, gval in val.items():
                    gname = GPSTAGS.get(gid, f"GPS_{gid}")
                    gps_named[gname] = gval
                nested["GPS"] = gps_named
            else:
                eid = _tag_name_to_id(piexif.ExifIFD, name)
                zid = _tag_name_to_id(piexif.ImageIFD, name)
                if eid is not None:
                    nested.setdefault("Exif", {})[name] = val
                elif zid is not None:
                    nested.setdefault("0th", {})[name] = val
                else:
                    nested.setdefault("0th", {})[name] = val
    return {k: v for k, v in nested.items() if v}


def load_exif_nested(
    image_path: Path,
) -> tuple[dict[str, dict[str, Any]], bool, dict[str, Any]]:
    """
    Load EXIF as nested IFD dict. Returns (nested, used_piexif, file_info).
    Falls back to Pillow mapping if piexif cannot read the file.
    """
    with Image.open(image_path) as img:
        file_info = {
            "filename": image_path.name,
            "size_bytes": image_path.stat().st_size,
            "format": img.format,
            "mode": img.mode,
            "size": img.size,
        }

    used_piexif = False
    nested: dict[str, dict[str, Any]] = {}
    try:
        raw = piexif.load(str(image_path))
        nested = piexif_raw_to_nested_named(raw)
        if nested:
            used_piexif = True
    except Exception as e:
        logger.debug(f"piexif.load failed for {image_path}, using Pillow: {e}")

    if not nested:
        nested = _nested_from_pillow(image_path)

    return nested, used_piexif, file_info


def extract_exif_data(
    image_path: Path,
    output_dir: Path | None = None,
    field_config: ExifFieldConfig | None = None,
    write_json: bool = True,
    json_stem_name: str | None = None,
) -> dict[str, Any]:
    """
    Extract EXIF using piexif-first pipeline, filter by config, save JSON.

    If json_stem_name is set, the JSON file is named {json_stem_name}.json (used when
    aligning names with output images from a chosen original basename). Otherwise the
    stem of image_path is used (legacy behaviour for Google / temp uploads).
    """
    from ..exif_config import load_exif_field_config

    if field_config is None:
        field_config = load_exif_field_config()

    if not image_path.exists():
        return {"error": f"File not found: {image_path}"}

    try:
        nested, used_piexif, file_info = load_exif_nested(image_path)
        filtered = filter_nested_exif(nested, field_config)

        display: dict[str, Any] = {}
        for ifd_key, tags in filtered.items():
            if ifd_key == "GPS" and tags:
                enriched = extract_gps_data_from_named_gps(tags)
                display["GPS"] = {k: _serialize_tag_value(v) for k, v in enriched.items()}
            else:
                display[ifd_key] = {k: _serialize_tag_value(v) for k, v in tags.items()}

        display["_file_info"] = file_info
        display["_meta"] = {"used_piexif": used_piexif}

        output_dir = output_dir or settings.DEFAULT_OUTPUT_DIR
        ensure_directory(output_dir)
        if write_json:
            if json_stem_name is not None:
                json_path = output_dir / f"{json_stem_name}{settings.JSON_SUFFIX}"
            else:
                json_path = get_json_output_path(image_path, output_dir)
        else:
            json_path = None

        if json_path:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(display, f, indent=2, ensure_ascii=False)

        total_fields = sum(len(v) for k, v in filtered.items() if k != "_meta")
        return {
            "success": True,
            "image_path": str(image_path),
            "json_path": str(json_path) if json_path else None,
            "exif_fields_count": total_fields,
            "nested_filtered": filtered,
        }
    except Exception as e:
        return {"error": f"Failed: {e}"}


def _save_with_pillow(image_path: Path, output_path: Path, exif_bytes: bytes | None) -> None:
    """Re-save a non-JPEG image with the given EXIF (or none)."""
    with Image.open(image_path) as img:
        save_kw: dict[str, Any] = {}
        if exif_bytes is not None:
            save_kw["exif"] = exif_bytes
        if image_path.suffix.lower() == ".webp":
            save_kw["quality"] = 95
        img.save(output_path, format=img.format or "JPEG", **save_kw)


def embed_exif_subset(
    image_path: Path,
    output_path: Path,
    field_config: ExifFieldConfig | None = None,
) -> bool:
    """
    Write a new image with EXIF limited to filtered tags (JPEG via piexif.insert).

    Returns True when output_path was written, even if no tags survived the filter.
    """
    from ..exif_config import load_exif_field_config

    if field_config is None:
        field_config = load_exif_field_config()

    try:
        nested, _, _ = load_exif_nested(image_path)
        filtered = filter_nested_exif(nested, field_config)
        if (
            field_config.skip_makernote_embed
            and "Exif" in filtered
            and "MakerNote" in filtered["Exif"]
        ):
            del filtered["Exif"]["MakerNote"]
            if not filtered["Exif"]:
                del filtered["Exif"]

        raw = nested_named_to_piexif_raw(filtered)
        ensure_directory(output_path.parent)
        suffix = image_path.suffix.lower()
        if not raw:
            # Still write the photo, but never carry over tags the user excluded.
            logger.info("No EXIF to embed for {}; saving without EXIF", image_path.name)
            if not nested:
                shutil.copyfile(image_path, output_path)
            elif suffix in {".jpg", ".jpeg"}:
                shutil.copyfile(image_path, output_path)
                piexif.remove(str(output_path))
            else:
                _save_with_pillow(image_path, output_path, exif_bytes=None)
            return True

        exif_bytes = piexif.dump(raw)
        if suffix in {".jpg", ".jpeg"}:
            piexif.insert(exif_bytes, str(image_path), str(output_path))
            return True
        try:
            _save_with_pillow(image_path, output_path, exif_bytes)
            return True
        except Exception as e2:
            logger.warning(f"Pillow EXIF save not supported for {suffix}: {e2}")
            return False
    except Exception as e:
        logger.error(f"embed_exif_subset failed for {image_path.name}: {e}")
        return False


def embed_exif_dates(image_path: Path, output_dir: Path) -> bool:
    """
    Legacy: copy image with DateTime* fields normalized (uses full piexif load).
    """
    try:
        from ..utils.file_utils import get_dated_output_path

        with Image.open(image_path) as img:
            exif_data = img.getexif()
            date = None
            for tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                tag_id = next((t for t, n in TAGS.items() if n == tag_name), None)
                if tag_id and tag_id in exif_data:
                    date = exif_data[tag_id]
                    break

        if not date:
            logger.warning(f"No EXIF date found for {image_path.name}")
            return False

        try:
            date_str = date if isinstance(date, str) else str(date)
            dt = datetime.strptime(date_str, settings.EXIF_DATE_FORMAT)
            timestamp = dt.timestamp()
        except Exception as e:
            logger.warning(f"Could not parse date '{date}' for {image_path.name}: {e}")
            return False

        exif_dict = piexif.load(str(image_path))
        date_bytes = date_str.encode()
        if "Exif" not in exif_dict or exif_dict["Exif"] is None:
            exif_dict["Exif"] = {}
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_bytes
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = date_bytes
        if "0th" not in exif_dict or exif_dict["0th"] is None:
            exif_dict["0th"] = {}
        exif_dict["0th"][piexif.ImageIFD.DateTime] = date_bytes

        ensure_directory(output_dir)
        output_path = get_dated_output_path(image_path, output_dir)
        piexif.insert(piexif.dump(exif_dict), str(image_path), str(output_path))
        os.utime(output_path, (timestamp, timestamp))
        logger.info(f"Updated EXIF & filesystem date for {image_path.name} → {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to update {image_path.name}: {e}")
        return False


def apply_exif_timestamp(output_path: Path, nested_exif: dict[str, dict[str, Any]]) -> bool:
    """Set an output file's modification time from its best available EXIF capture date."""
    candidates = (
        ("Exif", "DateTimeOriginal"),
        ("Exif", "DateTimeDigitized"),
        ("0th", "DateTime"),
    )
    for ifd_key, tag_name in candidates:
        raw = nested_exif.get(ifd_key, {}).get(tag_name)
        if not raw:
            continue
        date_str = raw.decode("ascii", errors="ignore") if isinstance(raw, bytes) else str(raw)
        try:
            timestamp = datetime.strptime(date_str, settings.EXIF_DATE_FORMAT).timestamp()
            os.utime(output_path, (timestamp, timestamp))
            return True
        except (OSError, ValueError) as e:
            logger.warning("Could not set filesystem date for {}: {}", output_path.name, e)
            return False
    return False


def process_image_extract_and_embed(
    image_path: Path,
    output_dir: Path,
    field_config: ExifFieldConfig | None = None,
    stem_suffix: str = "_exif",
    output_stem: str | None = None,
    write_json: bool = True,
) -> dict[str, Any]:
    """
    Extract filtered EXIF, optionally save JSON, and save a new image with embedded subset.

    If output_stem is set (local folder flow), JSON and image use that basename plus
    stem_suffix (use stem_suffix="" to match original names for overwrite-style output).

    Returns paths and status for Flask / API use.
    """
    from ..exif_config import load_exif_field_config

    if field_config is None:
        field_config = load_exif_field_config()

    output_dir = Path(output_dir)
    ensure_directory(output_dir)

    stem_base = output_stem if output_stem is not None else image_path.stem
    if output_stem is not None:
        json_stem_name = f"{stem_base}{stem_suffix}"
        ext_result = extract_exif_data(
            image_path,
            output_dir,
            field_config,
            write_json=write_json,
            json_stem_name=json_stem_name,
        )
    else:
        ext_result = extract_exif_data(image_path, output_dir, field_config, write_json=write_json)
    if "error" in ext_result:
        return ext_result

    out_name = f"{stem_base}{stem_suffix}{image_path.suffix}"
    output_image = output_dir / out_name

    ok = embed_exif_subset(image_path, output_image, field_config)
    if not ok or not output_image.is_file():
        return {"error": f"Could not save {image_path.suffix.lstrip('.').upper()} image"}
    filesystem_date_set = apply_exif_timestamp(output_image, ext_result["nested_filtered"])
    return {
        "success": True,
        "image_path": str(image_path),
        "json_path": ext_result.get("json_path"),
        "output_image": str(output_image),
        "embed_ok": ok,
        "filesystem_date_set": filesystem_date_set,
        "exif_fields_count": ext_result.get("exif_fields_count", 0),
    }
