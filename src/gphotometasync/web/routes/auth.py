"""Google sign-in (desktop OAuth) and session restore from the saved token."""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, url_for
from google.oauth2.credentials import Credentials

from ...google_photos.oauth import SCOPES, GooglePhotosOAuth
from ...google_photos.picker import ensure_fresh
from ...log import get_logger
from ...settings import settings
from ..session import current_session, save_token, start_session

logger = get_logger(__name__)

bp = Blueprint("auth", __name__)


@bp.get("/auth")
def sign_in():
    if not settings.google_oauth_client_secrets_path.is_file():
        flash(
            "Google isn’t configured yet. Add the client JSON file as credentials/client_secrets.json.",
            "error",
        )
        return redirect(url_for("home.index"))
    try:
        creds = GooglePhotosOAuth().run_local_server()
    except Exception as e:
        logger.exception("OAuth failed")
        flash(f"Sign-in didn’t finish: {e}", "error")
        return redirect(url_for("home.index"))

    save_token(creds)
    resp = redirect(url_for("home.index"))
    start_session(creds, resp)
    flash("You're signed in. You can choose photos from Google below.", "success")
    return resp


@bp.get("/api/check-auth")
def check_auth():
    if current_session():
        return jsonify({"ok": True})

    token_path = settings.google_token_path
    if not token_path.is_file():
        return jsonify({"ok": False}), 401
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        ensure_fresh(creds)
        save_token(creds)
    except Exception as e:
        logger.warning("check-auth token restore: {}", e)
        token_path.unlink(missing_ok=True)
        return jsonify({"ok": False, "reason": "expired"}), 401
    resp = jsonify({"ok": True})
    start_session(creds, resp)
    return resp
