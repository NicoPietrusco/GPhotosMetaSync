"""Parsing and validation of client-supplied form/JSON values."""

from __future__ import annotations

import re

from werkzeug.utils import secure_filename

_STEM_SUFFIX_RE = re.compile(r"^(_?[a-zA-Z0-9_-]{0,63})$")


def parse_stem_suffix(raw: str | None) -> str:
    """Allow empty (overwrite-style names) or a short safe suffix such as _exif."""
    if raw is None or not str(raw).strip():
        return ""
    s = str(raw).strip()
    return s if _STEM_SUFFIX_RE.fullmatch(s) else ""


def parse_bool(raw: object, default: bool = True) -> bool:
    """Parse a form or JSON boolean while preserving backward-compatible defaults."""
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def sanitize_relative_path(rel: str) -> str | None:
    """Normalize a client-provided relative path (folder uploads); reject path traversal."""
    if not rel or "\0" in rel:
        return None
    r = rel.replace("\\", "/").strip().strip("/")
    if not r:
        return None
    parts = r.split("/")
    if any(not p or p in (".", "..") or secure_filename(p) != p for p in parts):
        return None
    return "/".join(parts)
