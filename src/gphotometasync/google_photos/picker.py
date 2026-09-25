"""
Google Photos Picker API (REST): sessions, selected items and media download.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlparse

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from .oauth import SCOPES

PICKER_BASE = "https://photospicker.googleapis.com/v1"


def _session_url(session_id: str) -> str:
    return f"{PICKER_BASE}/sessions/{quote(session_id, safe='')}"


def credentials_from_session_json(credentials_json: str) -> Credentials:
    info = json.loads(credentials_json)
    return Credentials.from_authorized_user_info(info, SCOPES)


def ensure_fresh(creds: Credentials) -> None:
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())


def create_picker_session(creds: Credentials) -> dict[str, Any]:
    ensure_fresh(creds)
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    r = requests.post(f"{PICKER_BASE}/sessions", headers=headers, json={}, timeout=60)
    r.raise_for_status()
    return r.json()


def get_picker_session(creds: Credentials, session_id: str) -> dict[str, Any]:
    ensure_fresh(creds)
    headers = {"Authorization": f"Bearer {creds.token}"}
    r = requests.get(_session_url(session_id), headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()


def list_media_items(creds: Credentials, session_id: str) -> dict[str, Any]:
    ensure_fresh(creds)
    headers = {"Authorization": f"Bearer {creds.token}"}
    params = {"sessionId": session_id, "pageSize": 100}
    r = requests.get(f"{PICKER_BASE}/mediaItems", headers=headers, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def transform_picker_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Shape PickedMediaItem list for the frontend."""
    out = []
    for item in raw.get("mediaItems") or []:
        mf = item.get("mediaFile") or {}
        meta = mf.get("mediaFileMetadata") or {}
        photo_meta = meta.get("photoMetadata") or {}
        out.append(
            {
                "id": item.get("id"),
                "baseUrl": mf.get("baseUrl"),
                "mimeType": mf.get("mimeType"),
                "filename": mf.get("filename"),
                "mediaMetadata": {
                    "creationTime": item.get("createTime"),
                    "width": meta.get("width"),
                    "height": meta.get("height"),
                    "photo": photo_meta,
                    "cameraMake": meta.get("cameraMake"),
                    "cameraModel": meta.get("cameraModel"),
                },
            }
        )
    return out


def is_google_media_host(hostname: str) -> bool:
    """SSRF guard: only Google CDNs that serve Picker media."""
    hn = hostname.lower()
    return hn.endswith((".googleusercontent.com", ".ggpht.com", ".gstatic.com"))


def is_google_media_url(raw_url: str) -> bool:
    """Only send the OAuth bearer token to https Google media hosts."""
    parsed = urlparse(raw_url)
    return parsed.scheme == "https" and is_google_media_host(parsed.hostname or "")


def _download_url(base_url: str) -> str:
    """Append =d for download with metadata (see Picker docs)."""
    u = base_url.strip()
    if u.endswith("=d"):
        return u
    if "=" in u:
        return u.rsplit("=", 1)[0] + "=d"
    return u + "=d"


def download_media_bytes(base_url: str, access_token: str) -> bytes:
    """Download the original bytes of a picked item."""
    r = requests.get(
        _download_url(base_url),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=120,
    )
    r.raise_for_status()
    return r.content
