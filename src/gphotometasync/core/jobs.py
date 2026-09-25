"""
Export jobs: each job is a folder of processed photos under data/outputs/<uuid>.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

from werkzeug.utils import secure_filename

from ..settings import settings


def is_image_file(path: Path) -> bool:
    """True when the extension is one of the supported image formats."""
    return path.suffix.lower() in settings.SUPPORTED_FORMATS


def new_job() -> tuple[str, Path]:
    """Create an empty output folder for a new job."""
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


def staging_path(job_id: str, index: int, filename: str) -> Path:
    """Where an incoming file is written before processing."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings.upload_dir / f"{job_id}_{index}_{filename}"


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
