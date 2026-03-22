"""
Google Photos Picker API (REST) — OAuth access token from google.oauth2.credentials.
"""

from __future__ import annotations

import json
from typing import Any

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from .google_oauth_picker import SCOPES

PICKER_BASE = "https://photospicker.googleapis.com/v1"


def _session_url(session_id: str) -> str:
    from urllib.parse import quote

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
