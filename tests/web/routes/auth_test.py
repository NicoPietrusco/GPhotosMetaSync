"""Tests for gphotometasync.web.routes.auth."""

from __future__ import annotations

from google_auth_oauthlib.flow import WSGITimeoutError

from gphotometasync.web import session as web_session
from gphotometasync.web.routes import auth


def test_check_auth_without_session_or_token(client) -> None:
    resp = client.get("/api/check-auth")

    assert resp.status_code == 401
    assert resp.get_json() == {"ok": False}


def test_check_auth_accepts_an_existing_session(signed_in_client) -> None:
    assert signed_in_client.get("/api/check-auth").get_json() == {"ok": True}


def test_check_auth_restores_a_session_from_the_saved_token(client, credentials, data_dir) -> None:
    token = data_dir / "credentials" / "google_token.json"
    token.parent.mkdir(parents=True)
    token.write_text(credentials.to_json())

    resp = client.get("/api/check-auth")

    assert resp.status_code == 200
    assert web_session.COOKIE_NAME in resp.headers["Set-Cookie"]
    assert len(web_session.picker_sessions) == 1


def test_check_auth_discards_an_unusable_token(client, data_dir) -> None:
    token = data_dir / "credentials" / "google_token.json"
    token.parent.mkdir(parents=True)
    token.write_text("{}")

    resp = client.get("/api/check-auth")

    assert resp.status_code == 401
    assert resp.get_json()["reason"] == "expired"
    assert not token.exists()


def test_sign_in_without_client_secrets_explains_the_setup(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRETS", str(tmp_path / "missing.json"))

    resp = client.get("/auth", follow_redirects=True)

    assert "client_secrets.json" in resp.get_data(as_text=True)


def test_sign_in_stores_the_token_and_starts_a_session(
    client, credentials, monkeypatch, tmp_path, data_dir
) -> None:
    secrets = tmp_path / "client_secrets.json"
    secrets.write_text("{}")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRETS", str(secrets))
    monkeypatch.setattr(auth.GooglePhotosOAuth, "run_local_server", lambda self: credentials)

    resp = client.get("/auth")

    assert resp.status_code == 302
    assert web_session.COOKIE_NAME in resp.headers["Set-Cookie"]
    assert (data_dir / "credentials" / "google_token.json").is_file()


def test_abandoned_sign_in_times_out_with_a_clear_message(client, monkeypatch, tmp_path) -> None:
    secrets = tmp_path / "client_secrets.json"
    secrets.write_text("{}")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRETS", str(secrets))

    def time_out(self):
        raise WSGITimeoutError("Timed out waiting for response from authorization server")

    monkeypatch.setattr(auth.GooglePhotosOAuth, "run_local_server", time_out)

    page = client.get("/auth", follow_redirects=True).get_data(as_text=True)

    assert "Sign-in timed out" in page
    assert not web_session.picker_sessions
