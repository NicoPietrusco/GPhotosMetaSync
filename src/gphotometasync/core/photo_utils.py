"""
Photo manipulation utilities for GPhotoMetaSync.
"""

from pathlib import Path
from typing import List

from tqdm import tqdm

from ..settings import settings
from ..utils.logger_utils import get_logger
from .exif_utils import embed_exif_dates, extract_exif_data

logger = get_logger(__name__)


def process_single_image(image_path: Path, output_dir: Path, verbose: bool) -> bool:
    """
    Process a single image file.

    Args:
        image_path: Path to the image file
        output_dir: Directory for output
        verbose: Whether to show detailed progress

    Returns:
        True if successful, False otherwise
    """
    result = extract_exif_data(image_path, output_dir)
    if "error" in result:
        if verbose:
            logger.error(f"❌ {image_path.name}: {result['error']}")
        return False
    if verbose:
        logger.success(
            f"✅ {image_path.name}: {result['exif_fields_count']} fields → {Path(result['json_path']).name}"
        )
    return True


def process_multiple_images(image_paths: List[Path], output_dir: Path, verbose: bool) -> None:
    """
    Process multiple image files with progress bar.

    Args:
        image_paths: List of image paths to process
        output_dir: Directory for output files
        verbose: Whether to show detailed progress
    """
    success_count = 0
    with tqdm(total=len(image_paths), desc=settings.PROGRESS_DESC_EXTRACT, unit="files") as pbar:
        for img_path in image_paths:
            if process_single_image(img_path, output_dir, verbose):
                success_count += 1
            pbar.update(1)
    logger.info(f"📊 Summary: {success_count}/{len(image_paths)} images processed successfully")


def process_photos_extract(
    targets: List[Path], output_dir: str = "output", verbose: bool = False
) -> None:
    """
    Extract EXIF data from photos to JSON files.

    Args:
        targets: List of file paths, directories, or glob patterns
        output_dir: Directory to save JSON files
        verbose: Whether to show detailed progress
    """
    from ..utils.file_utils import find_images

    image_paths = find_images(targets)
    if not image_paths:
        logger.error("❌ No valid image files found")
        raise SystemExit(1)

    logger.info(f"🚀 Starting EXIF extraction for {len(image_paths)} images to '{output_dir}'...")
    process_multiple_images(image_paths, Path(output_dir), verbose)


def process_photos_embed(
    targets: List[Path], output_dir: str = "output", verbose: bool = False
) -> None:
    """
    Embed EXIF dates into new photo files.

    Args:
        targets: List of file paths, directories, or glob patterns
        output_dir: Directory to save dated images
        verbose: Whether to show detailed progress
    """
    from ..utils.file_utils import find_images

    image_paths = find_images(targets)
    if not image_paths:
        logger.error("❌ No images found")
        raise SystemExit(1)

    logger.info(f"🧭 Embedding EXIF dates into {len(image_paths)} images → {output_dir}")
    success = 0

    with tqdm(total=len(image_paths), desc=settings.PROGRESS_DESC_EMBED, unit="files") as pbar:
        for img in image_paths:
            if embed_exif_dates(img, Path(output_dir)):
                success += 1
            pbar.update(1)

    logger.info(f"📊 Summary: {success}/{len(image_paths)} images updated")
