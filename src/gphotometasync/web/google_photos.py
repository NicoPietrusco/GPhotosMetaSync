"""
Download bytes from a Picker API media baseUrl using an OAuth access token.
"""

from __future__ import annotations

import requests


def _download_url(base_url: str) -> str:
    """Append =d for download with metadata (see Picker docs)."""
    u = base_url.strip()
    if u.endswith("=d"):
        return u
    if "=" in u:
        return u.rsplit("=", 1)[0] + "=d"
    return u + "=d"


def download_picker_media_bytes(base_url: str, access_token: str) -> bytes:
    url = _download_url(base_url)
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=120,
    )
    r.raise_for_status()
    return r.content
