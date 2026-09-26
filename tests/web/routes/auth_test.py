"""Tests for hicpicnunc.web.routes.auth."""

from __future__ import annotations

from google_auth_oauthlib.flow import WSGITimeoutError

from hicpicnunc.web import session as web_session
from hicpicnunc.web.routes import auth


def test_check_auth_without_session_or_token(client) -> None:
    resp = client.get("/api/check-auth")

    assert resp.status_code == 401
    assert resp.get_json() == {"ok": False}


def test_check_auth_accepts_an_existing_session(signed_in_client) -> None:
    assert signed_in_client.get("/api/check-auth").get_json() == {"ok": True, "email": None}


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


def test_check_auth_returns_email(client, credentials) -> None:
    web_session.picker_sessions["test-sid"] = web_session.PickerSessionData(
        credentials_json=credentials.to_json(), email="user@gmail.com"
    )
    client.set_cookie(web_session.COOKIE_NAME, "test-sid")

    resp = client.get("/api/check-auth")

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True, "email": "user@gmail.com"}


def test_logout_revokes_token_at_google_and_cleans_up(
    signed_in_client, credentials, data_dir, monkeypatch
) -> None:
    token = data_dir / "credentials" / "google_token.json"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(credentials.to_json())

    revoked_tokens = []
    monkeypatch.setattr(auth, "revoke_token", lambda tok: revoked_tokens.append(tok) or True)

    resp = signed_in_client.post("/auth/logout")

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert not token.exists()
    assert not web_session.picker_sessions
    assert web_session.COOKIE_NAME in resp.headers["Set-Cookie"]
    assert len(revoked_tokens) == 1
    assert revoked_tokens[0] == (credentials.refresh_token or credentials.token)

    # Subsequent check-auth is unauthorized
    check_resp = signed_in_client.get("/api/check-auth")
    assert check_resp.status_code == 401


def test_logout_offline_still_cleans_up_locally(
    signed_in_client, credentials, data_dir, monkeypatch
) -> None:
    token = data_dir / "credentials" / "google_token.json"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(credentials.to_json())

    def fake_revoke(tok):
        import requests

        raise requests.ConnectionError("Offline")

    monkeypatch.setattr(auth, "revoke_token", fake_revoke)

    resp = signed_in_client.post("/auth/logout")

    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert not token.exists()
    assert not web_session.picker_sessions

    check_resp = signed_in_client.get("/api/check-auth")
    assert check_resp.status_code == 401


def test_logout_without_prior_session_or_token(client) -> None:
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}


def test_sign_in_stores_the_token_and_email(
    client, credentials, monkeypatch, tmp_path, data_dir
) -> None:
    secrets = tmp_path / "client_secrets.json"
    secrets.write_text("{}")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRETS", str(secrets))
    monkeypatch.setattr(auth.GooglePhotosOAuth, "run_local_server", lambda self: credentials)
    monkeypatch.setattr(auth, "extract_verified_email", lambda creds: "verified@gmail.com")

    resp = client.get("/auth")

    assert resp.status_code == 302
    assert web_session.COOKIE_NAME in resp.headers["Set-Cookie"]
    token_file = data_dir / "credentials" / "google_token.json"
    assert token_file.is_file()
    assert "verified@gmail.com" in token_file.read_text()
    sid = list(web_session.picker_sessions.keys())[0]
    assert web_session.picker_sessions[sid].email == "verified@gmail.com"
