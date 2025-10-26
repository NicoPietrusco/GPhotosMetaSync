"""
Main CLI interface for GPhotoMetaSync.
"""

from pathlib import Path
from typing import List

import typer

from .core.photo_utils import process_photos_embed, process_photos_extract
from .settings import settings
from .utils.logger_utils import setup_logger

# Setup logger
setup_logger()

# Create typer app
app = typer.Typer(
    name=settings.APP_NAME,
    help=settings.APP_DESCRIPTION,
    add_completion=False,
)


@app.command()
def extract(
    targets: List[Path] = typer.Argument(  # noqa: B008
        ..., help="Image files, directories, or glob patterns to process", metavar="FILES..."
    ),
    output_dir: str = typer.Option(  # noqa: B008
        "output", "--output", "-o", help="Directory to save JSON files (default: ./output)"
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False, "--verbose", "-v", help="Show detailed progress information"
    ),
):
    """Extract EXIF data from images and save to JSON files."""
    process_photos_extract(targets, output_dir, verbose)


@app.command()
def embed(
    targets: List[Path] = typer.Argument(  # noqa: B008
        ..., help="Image files, directories, or glob patterns to process", metavar="FILES..."
    ),
    output_dir: str = typer.Option(  # noqa: B008
        "output", "--output", "-o", help="Directory to save output files (default: ./output)"
    ),
    verbose: bool = typer.Option(  # noqa: B008
        False, "--verbose", "-v", help="Show detailed progress information"
    ),
):
    """Embed or restore EXIF create dates inside new image copies."""
    process_photos_embed(targets, output_dir, verbose)


@app.command()
def info():
    """Show detailed information about the GPhotoMetaSync tool."""
    print("=" * 70)
    print(f"📸 {settings.APP_NAME} - {settings.APP_DESCRIPTION}")
    print("=" * 70)

    print("\n🔧 INSTALLATION:")
    print("-" * 30)
    print("uv add pillow typer tqdm loguru piexif")
    print("\nFor HEIC/HEIF images:")
    print("uv add pillow-heif")

    print("\n📖 USAGE:")
    print("-" * 30)
    print("uv run python -m gphotometasync.main extract photo.jpg")
    print("uv run python -m gphotometasync.main extract photos/ --verbose")
    print("uv run python -m gphotometasync.main extract *.jpg --output my_json/")
    print("uv run python -m gphotometasync.main embed photo.jpg")
    print("uv run python -m gphotometasync.main embed photos/ --output corrected/")

    print("\n⚡ BEST PRACTICES:")
    print("- Process photos in batches for better performance")
    print("- Use directory processing for large collections")
    print("- Backup originals before using embed command")
    print("- JSON files include GPS coordinates and timestamps")

    print("\n📊 SUPPORTED FORMATS:")
    print(", ".join(sorted(settings.SUPPORTED_FORMATS)))

    print("\n🗺️ EXTRACTED DATA:")
    print("- Camera info, timestamps, GPS coordinates")
    print("- Image dimensions and technical parameters")
    print("- Decimal GPS values (LatitudeDecimal, LongitudeDecimal)")

    print("\n💾 OUTPUT:")
    print("Extract: Creates .json files with same name as images")
    print("Embed: Creates new images with _dated suffix")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    app()
