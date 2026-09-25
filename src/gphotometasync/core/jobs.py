"""
Export jobs: each job is a folder of processed photos under data/outputs/<uuid>.
"""

from __future__ import annotations

import io
import shutil
import time
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from werkzeug.utils import secure_filename

from ..log import get_logger
from ..settings import settings

logger = get_logger(__name__)


def is_image_file(path: Path) -> bool:
    """True when the extension is one of the supported image formats."""
    return path.suffix.lower() in settings.SUPPORTED_FORMATS


def new_job() -> tuple[str, Path]:
    """Create an empty output folder for a new job (and drop expired ones)."""
    prune_expired_jobs()
    job_id = str(uuid.uuid4())
    job_dir = settings.web_output_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_id, job_dir


def get_job_dir(job_id: str) -> Path | None:
    """Output folder of an existing job, or None for unknown or malformed ids."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        return None
    job_dir = settings.web_output_dir / job_id
    return job_dir if job_dir.is_dir() else None


@contextmanager
def staged_file(job_id: str, index: int, filename: str) -> Iterator[Path]:
    """Path for an incoming file while it is processed; the file is deleted afterwards."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{job_id}_{index}_{filename}"
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def _is_job_id(name: str) -> bool:
    try:
        uuid.UUID(name[:36])
    except ValueError:
        return False
    return True


def prune_expired_jobs(max_age_hours: float | None = None) -> int:
    """
    Delete job outputs (and leftover staged uploads) older than the retention period.

    Only entries named after a job id are touched. Returns how many were removed.
    """
    hours = settings.job_retention_hours if max_age_hours is None else max_age_hours
    cutoff = time.time() - hours * 3600
    removed = 0
    for folder in (settings.web_output_dir, settings.upload_dir):
        if not folder.is_dir():
            continue
        for entry in folder.iterdir():
            try:
                if not _is_job_id(entry.name) or entry.stat().st_mtime >= cutoff:
                    continue
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                removed += 1
            except OSError as e:
                logger.warning("Could not remove expired {}: {}", entry.name, e)
    if removed:
        logger.info("Removed {} expired job file(s)", removed)
    return removed


def list_job_files(job_dir: Path) -> list[str]:
    """Relative POSIX paths of every file in the job, sorted."""
    return sorted(p.relative_to(job_dir).as_posix() for p in job_dir.rglob("*") if p.is_file())


def resolve_job_file(job_dir: Path, rel: str) -> Path | None:
    """Resolve rel to a path under job_dir, or None if invalid or it escapes."""
    rel = rel.replace("\\", "/").strip().lstrip("/")
    if not rel or "\0" in rel:
        return None
    parts = rel.split("/")
    if any(not p or p in (".", "..") or secure_filename(p) != p for p in parts):
        return None
    try:
        root = job_dir.resolve()
        candidate = root.joinpath(*parts).resolve()
        candidate.relative_to(root)
    except (ValueError, OSError):
        return None
    return candidate


def build_job_zip(job_dir: Path) -> io.BytesIO:
    """ZIP every job file; entries keep each file's mtime (the capture date)."""
    buf = io.BytesIO()
    # Capture dates before 1980 are clamped instead of failing the whole download.
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as zf:
        for rel in list_job_files(job_dir):
            zf.write(job_dir / rel, arcname=rel)
    buf.seek(0)
    return buf
