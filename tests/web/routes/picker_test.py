"""Tests for gphotometasync.web.routes.picker."""

from __future__ import annotations

from typing import Any

import pytest

from gphotometasync.web import session as web_session
from gphotometasync.web.routes import picker

GOOGLE_URL = "https://lh3.googleusercontent.com/item"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/create-session"),
        ("get", "/api/session-status"),
        ("get", "/api/list-selected"),
        ("post", "/api/process-google-batch"),
        ("get", f"/api/picker-image?url={GOOGLE_URL}"),
    ],
)
def test_endpoints_require_sign_in(client, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize(
    ("url", "status"),
    [("", 400), ("ftp://lh3.googleusercontent.com/x", 400), ("https://evil.example/x", 403)],
)
def test_picker_image_only_proxies_google_hosts(signed_in_client, url: str, status: int) -> None:
    assert signed_in_client.get(f"/api/picker-image?url={url}").status_code == status


def test_picker_image_proxies_the_bytes(signed_in_client, monkeypatch, fake_response) -> None:
    monkeypatch.setattr(
        picker.requests,
        "get",
        lambda url, **kw: fake_response(content=b"img", headers={"Content-Type": "image/webp"}),
    )

    resp = signed_in_client.get(f"/api/picker-image?url={GOOGLE_URL}")

    assert resp.data == b"img"
    assert resp.mimetype == "image/webp"


def test_create_session_stores_the_picker_session(signed_in_client, monkeypatch) -> None:
    monkeypatch.setattr(
        picker,
        "create_picker_session",
        lambda creds: {
            "id": "new",
            "pickerUri": "https://photos.google.com/x",
            "pollingConfig": {"pollInterval": "3s"},
        },
    )

    body = signed_in_client.post("/api/create-session").get_json()

    assert body == {
        "sessionId": "new",
        "pickerUri": "https://photos.google.com/x",
        "pollInterval": "3",
    }
    assert web_session.picker_sessions["test-sid"].picker_session_id == "new"


@pytest.mark.parametrize(("media_set", "status"), [(True, "ready"), (False, "pending")])
def test_session_status(signed_in_client, monkeypatch, media_set: bool, status: str) -> None:
    monkeypatch.setattr(
        picker, "get_picker_session", lambda creds, sid: {"mediaItemsSet": media_set}
    )

    assert signed_in_client.get("/api/session-status").get_json()["status"] == status


def test_list_selected_returns_the_picked_items(signed_in_client, monkeypatch) -> None:
    monkeypatch.setattr(picker, "get_picker_session", lambda creds, sid: {"mediaItemsSet": True})
    monkeypatch.setattr(
        picker,
        "list_media_items",
        lambda creds, sid: {"mediaItems": [{"id": "m1", "mediaFile": {"filename": "a.jpg"}}]},
    )

    body = signed_in_client.get("/api/list-selected").get_json()

    assert body["count"] == 1
    assert body["items"][0]["filename"] == "a.jpg"


def test_batch_never_sends_the_token_to_other_hosts(signed_in_client, monkeypatch) -> None:
    def fail_download(*args: Any) -> bytes:
        raise AssertionError("must not download from a non-Google host")

    monkeypatch.setattr(picker, "download_media_bytes", fail_download)

    resp = signed_in_client.post(
        "/api/process-google-batch",
        json={"items": [{"base_url": "https://evil.example/x", "filename": "a.jpg"}]},
    )

    assert resp.status_code == 500
    assert resp.get_json()["errors"] == [
        {"index": 0, "filename": "a.jpg", "error": "invalid base_url"}
    ]


def test_batch_exports_every_item_into_one_job(
    signed_in_client, monkeypatch, make_jpeg, data_dir
) -> None:
    photo = make_jpeg().read_bytes()
    monkeypatch.setattr(picker, "download_media_bytes", lambda url, token: photo)

    body = signed_in_client.post(
        "/api/process-google-batch",
        json={
            "items": [
                {"base_url": GOOGLE_URL, "filename": "a.jpg"},
                {"base_url": GOOGLE_URL, "filename": "b.jpg"},
                "not-a-dict",
            ],
            "include_json": False,
        },
    ).get_json()

    assert body["ok"] and body["processed"] == 2
    assert body["errors"] == [{"index": 2, "error": "invalid item"}]
    page = signed_in_client.get(body["job_url"]).get_data(as_text=True)
    assert "a_exif.jpg" in page and "b_exif.jpg" in page
    assert list((data_dir / "data" / "uploads").iterdir()) == []  # staged downloads removed


def test_batch_requires_items(signed_in_client) -> None:
    assert signed_in_client.post("/api/process-google-batch", json={"items": []}).status_code == 400
