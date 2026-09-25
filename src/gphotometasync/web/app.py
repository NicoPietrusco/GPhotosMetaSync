"""
Flask application: local desktop use (localhost). Google Photos via Desktop OAuth + Picker API.
"""

from __future__ import annotations

import io
import os
import re
import secrets
import threading
import uuid
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from google.oauth2.credentials import Credentials
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

from ..core.photo_utils import process_uploaded_image
from ..exif_config import (
    load_metadata_preferences,
    load_user_exif_field_config,
    save_metadata_preferences,
)
from ..settings import settings
from ..utils.file_utils import ensure_directory, is_image_file
from ..utils.logger_utils import get_logger, setup_logger
from . import google_photos
from .google_oauth_picker import SCOPES, GooglePhotosOAuth
from .picker_api import (
    create_picker_session,
    credentials_from_session_json,
    ensure_fresh,
    get_picker_session,
    list_media_items,
    transform_picker_items,
)

setup_logger()
logger = get_logger(__name__)

picker_sessions: dict[str, "PickerSessionData"] = {}


def _is_allowed_google_image_host(hostname: str) -> bool:
    """SSRF guard: only Google CDNs used for Picker thumbnails."""
    if not hostname:
        return False
    hn = hostname.lower()
    return bool(
        hn.endswith(".googleusercontent.com")
        or hn.endswith(".ggpht.com")
        or hn.endswith(".gstatic.com")
    )


_JOB_FILE_PREFIX_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_\d+_(.+)$",
    re.I,
)


def _friendly_job_filename(filename: str) -> str:
    """Strip leading job id + index from stored filenames for display."""
    if "/" in filename:
        return filename
    m = _JOB_FILE_PREFIX_RE.match(filename)
    return m.group(1) if m else filename


def _categorize_job_files(names: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Split output names into images, JSON sidecars, and other."""
    images: list[str] = []
    jsons: list[str] = []
    others: list[str] = []
    exts = settings.SUPPORTED_FORMATS
    for n in names:
        suf = Path(n).suffix.lower()
        if suf == ".json":
            jsons.append(n)
        elif suf in exts:
            images.append(n)
        else:
            others.append(n)
    return images, jsons, others


_STEM_SUFFIX_RE = re.compile(r"^(_?[a-zA-Z0-9_-]{0,63})$")


def _parse_stem_suffix(raw: str | None) -> str:
    """Allow empty (overwrite-style names) or a short safe suffix such as _exif."""
    if raw is None or not str(raw).strip():
        return ""
    s = str(raw).strip()
    if _STEM_SUFFIX_RE.fullmatch(s):
        return s
    return ""


def _parse_bool(raw: object, default: bool = True) -> bool:
    """Parse a form or JSON boolean while preserving backward-compatible defaults."""
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _sanitize_relative_path(rel: str) -> str | None:
    """Normalize a client-provided relative path (folder uploads); reject path traversal."""
    if not rel or "\0" in rel:
        return None
    r = rel.replace("\\", "/").strip().strip("/")
    if not r:
        return None
    parts: list[str] = []
    for p in r.split("/"):
        if not p or p in (".", ".."):
            return None
        safe = secure_filename(p)
        if not safe or safe != p:
            return None
        parts.append(safe)
    if not parts:
        return None
    return "/".join(parts)


def _safe_path_under_job_base(job_base: Path, rel: str) -> Path | None:
    """Resolve rel to an absolute path under job_base, or None if invalid or escapes."""
    rel = rel.replace("\\", "/").strip().lstrip("/")
    if not rel or "\0" in rel:
        return None
    parts: list[str] = []
    for p in rel.split("/"):
        if not p or p in (".", ".."):
            return None
        safe = secure_filename(p)
        if not safe or safe != p:
            return None
        parts.append(safe)
    if not parts:
        return None
    try:
        job_res = job_base.resolve()
        candidate = job_res.joinpath(*parts).resolve()
        candidate.relative_to(job_res)
    except (ValueError, OSError):
        return None
    return candidate


@dataclass
class PickerSessionData:
    credentials_json: str
    picker_session_id: str | None = None


def _get_session_data() -> PickerSessionData | None:
    sid = request.cookies.get("session_id")
    if sid and sid in picker_sessions:
        return picker_sessions[sid]
    return None


def _creds_for_request() -> tuple[Credentials, PickerSessionData] | None:
    data = _get_session_data()
    if not data:
        return None
    creds = credentials_from_session_json(data.credentials_json)
    prev = data.credentials_json
    ensure_fresh(creds)
    data.credentials_json = creds.to_json()
    if data.credentials_json != prev:
        try:
            settings.google_token_path.parent.mkdir(parents=True, exist_ok=True)
            settings.google_token_path.write_text(data.credentials_json)
        except OSError as e:
            logger.warning("Could not persist google_token.json: {}", e)
    return creds, data


def create_app() -> Flask:
    load_dotenv(settings.base_dir / ".env")

    _root = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(_root / "templates"),
        static_folder=str(_root / "static"),
        instance_relative_config=True,
    )
    app.secret_key = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_mb * 1024 * 1024

    data_dir = settings.data_dir
    upload_dir = settings.upload_dir
    output_dir = settings.web_output_dir
    for d in (data_dir, upload_dir, output_dir):
        ensure_directory(d)

    @app.context_processor
    def inject_globals() -> dict:
        return {
            "settings": settings,
            "google_oauth_ready": settings.google_oauth_client_secrets_path.is_file(),
            "metadata_preferences": load_metadata_preferences(settings.metadata_preferences_path),
        }

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            metadata_preferences=load_metadata_preferences(settings.metadata_preferences_path),
        )

    @app.post("/api/metadata-preferences")
    def api_save_metadata_preferences():
        body = request.get_json(silent=True) or {}
        preferences = body.get("preferences")
        if not isinstance(preferences, dict):
            return jsonify({"ok": False, "detail": "preferences must be an object"}), 400
        try:
            saved = save_metadata_preferences(preferences, settings.metadata_preferences_path)
        except OSError as e:
            logger.exception("Could not save metadata preferences")
            return jsonify({"ok": False, "detail": str(e)}), 500
        return jsonify({"ok": True, "preferences": saved})

    @app.get("/auth")
    def auth():
        secret_path = settings.google_oauth_client_secrets_path
        if not secret_path.is_file():
            flash(
                "Google isn’t configured yet. Add the client JSON file as credentials/client_secrets.json.",
                "error",
            )
            return redirect(url_for("index"))
        try:
            creds = GooglePhotosOAuth().run_local_server()
        except Exception as e:
            logger.exception("OAuth failed")
            flash(f"Sign-in didn’t finish: {e}", "error")
            return redirect(url_for("index"))

        settings.google_token_path.parent.mkdir(parents=True, exist_ok=True)
        settings.google_token_path.write_text(creds.to_json())

        sid = secrets.token_urlsafe(16)
        picker_sessions[sid] = PickerSessionData(credentials_json=creds.to_json())
        resp = redirect(url_for("index"))
        resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
        flash("You're signed in. You can choose photos from Google below.", "success")
        return resp

    @app.get("/api/check-auth")
    def check_auth():
        if _get_session_data():
            return jsonify({"ok": True})

        token_path = settings.google_token_path
        if token_path.is_file():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                ensure_fresh(creds)
                token_path.write_text(creds.to_json())
                sid = secrets.token_urlsafe(16)
                picker_sessions[sid] = PickerSessionData(credentials_json=creds.to_json())
                resp = jsonify({"ok": True})
                resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
                return resp
            except Exception as e:
                logger.warning("check-auth token restore: {}", e)
                try:
                    token_path.unlink()
                except OSError:
                    pass
                return jsonify({"ok": False, "reason": "expired"}), 401

        return jsonify({"ok": False}), 401

    @app.get("/api/picker-image")
    def picker_image():
        """
        Fetch a Picker media baseUrl with OAuth. <img> cannot send Authorization headers,
        so we proxy the bytes through the same session cookie.
        """
        raw_url = request.args.get("url", "").strip()
        if not raw_url or len(raw_url) > 8192:
            return "Bad request", 400
        parsed = urlparse(raw_url)
        if parsed.scheme not in ("http", "https"):
            return "Invalid URL", 400
        if not _is_allowed_google_image_host(parsed.hostname or ""):
            return "Forbidden", 403
        pair = _creds_for_request()
        if not pair:
            return jsonify({"detail": "Not authenticated"}), 401
        creds, pdata = pair
        ensure_fresh(creds)
        pdata.credentials_json = creds.to_json()
        try:
            headers = {"Authorization": f"Bearer {creds.token}"}
            r = requests.get(raw_url, headers=headers, timeout=60)
            if r.status_code in (401, 403):
                r = requests.get(raw_url, timeout=60)
            r.raise_for_status()
            raw_ct = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
            ct = raw_ct if raw_ct.startswith("image/") else "image/jpeg"
            return Response(r.content, mimetype=ct)
        except Exception as e:
            logger.warning("picker-image: {}", e)
            return jsonify({"detail": str(e)}), 502

    @app.post("/upload")
    def upload():
        wants_json = (
            "application/json" in (request.headers.get("Accept") or "").lower()
            and request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )

        file_list = request.files.getlist("file")
        if not file_list:
            if wants_json:
                return jsonify({"ok": False, "detail": "No file was uploaded."}), 400
            flash("No file was uploaded. Try again.", "error")
            return redirect(url_for("index"))

        stem_suffix = _parse_stem_suffix(request.form.get("stem_suffix"))
        include_json = _parse_bool(request.form.get("include_json"))

        rows: list[tuple] = []
        form_rels = request.form.getlist("relative_paths")
        for i, f in enumerate(file_list):
            if not f.filename:
                continue
            rel = form_rels[i] if i < len(form_rels) else (f.filename or "")
            safe_rel = _sanitize_relative_path(rel.replace("\\", "/"))
            if not safe_rel:
                bn = secure_filename(Path(rel.replace("\\", "/")).name)
                if not bn:
                    continue
                safe_rel = bn
            name = secure_filename(Path(safe_rel).name)
            if not name or not is_image_file(Path(name)):
                continue
            rows.append((f, name, safe_rel))

        if not rows:
            if wants_json:
                return jsonify({"ok": False, "detail": "No supported images."}), 400
            flash("Choose at least one supported image (JPEG, PNG, etc.).", "error")
            return redirect(url_for("index"))

        job = str(uuid.uuid4())
        job_out = output_dir / job
        ensure_directory(job_out)
        job_out_res = job_out.resolve()
        field_config = load_user_exif_field_config(settings.metadata_preferences_path)

        processed = 0
        errors: list[str] = []
        out_payload: list[dict[str, str | None]] = []
        for i, (f, name, safe_rel) in enumerate(rows):
            parent = str(Path(safe_rel).parent)
            if parent == ".":
                out_subdir = job_out
            else:
                out_subdir = job_out / parent
            ensure_directory(out_subdir)
            dest = upload_dir / f"{job}_{i}_{name}"
            f.save(dest)
            output_stem = Path(safe_rel).stem
            result = process_uploaded_image(
                dest,
                out_subdir,
                field_config,
                stem_suffix=stem_suffix,
                output_stem=output_stem,
                write_json=include_json,
            )
            if result.get("error"):
                errors.append(f"{safe_rel}: {result['error']}")
            else:
                processed += 1
                img_path = Path(result["output_image"]).resolve()
                rel_img = img_path.relative_to(job_out_res).as_posix()
                jp = result.get("json_path")
                rel_json = (
                    Path(jp).resolve().relative_to(job_out_res).as_posix() if jp else None
                )
                out_payload.append(
                    {
                        "relative_path": rel_img,
                        "json_relative_path": rel_json,
                        "image_url": url_for("serve_file", job_id=job, filename=rel_img),
                        "json_url": (
                            url_for("serve_file", job_id=job, filename=rel_json)
                            if rel_json
                            else None
                        ),
                    }
                )

        if processed == 0:
            if wants_json:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "processed": 0,
                            "errors": errors,
                            "detail": errors[0] if errors else "Processing failed.",
                        }
                    ),
                    400,
                )
            flash(
                "Could not process any images. " + (errors[0] if errors else ""),
                "error",
            )
            return redirect(url_for("index"))

        session["last_job"] = job
        msg = f"Done. Saved metadata for {processed} image(s)."
        if errors:
            msg += f" {len(errors)} could not be saved."

        if wants_json:
            return jsonify(
                {
                    "ok": True,
                    "job_id": job,
                    "job_url": url_for("job_result", job_id=job),
                    "processed": processed,
                    "errors": errors,
                    "files": out_payload,
                }
            )

        flash(msg, "success")
        return redirect(url_for("job_result", job_id=job))

    @app.get("/job/<job_id>")
    def job_result(job_id: str):
        base = output_dir / job_id
        if not base.is_dir():
            flash("Those files aren't available anymore. Start from the home page.", "error")
            return redirect(url_for("index"))
        files = sorted(
            (p for p in base.rglob("*") if p.is_file()),
            key=lambda p: p.as_posix(),
        )
        names = [p.relative_to(base).as_posix() for p in files]
        images, jsons, others = _categorize_job_files(names)

        def _items(ns: list[str]) -> list[dict[str, str]]:
            return [{"name": n, "label": _friendly_job_filename(n)} for n in ns]

        download_manifest = [
            {
                "path": n,
                "url": url_for("serve_file", job_id=job_id, filename=n),
            }
            for n in names
        ]

        return render_template(
            "job.html",
            job_id=job_id,
            file_count=len(names),
            image_files=_items(images),
            json_files=_items(jsons),
            other_files=_items(others),
            download_manifest=download_manifest,
        )

    @app.get("/files/<job_id>/<path:filename>")
    def serve_file(job_id: str, filename: str):
        try:
            uuid.UUID(job_id)
        except ValueError:
            return "Invalid job id", 400
        base = output_dir / job_id
        if not base.is_dir():
            return "Not found", 404
        path = _safe_path_under_job_base(base, filename)
        if path is None or not path.is_file():
            return "Not found", 404
        rel = path.relative_to(base.resolve()).as_posix()
        return send_from_directory(base, rel, as_attachment=True)

    @app.get("/job/<job_id>/download-all")
    def download_job_zip(job_id: str):
        try:
            uuid.UUID(job_id)
        except ValueError:
            return "Invalid job id", 400
        base = output_dir / job_id
        if not base.is_dir():
            return "Not found", 404
        paths = sorted(
            (p for p in base.rglob("*") if p.is_file()),
            key=lambda p: p.as_posix(),
        )
        if not paths:
            return "No files", 404
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in paths:
                zf.write(p, arcname=p.relative_to(base).as_posix())
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"photo-meta-sync-{job_id[:8]}.zip",
        )

    @app.post("/api/create-session")
    def api_create_session():
        pair = _creds_for_request()
        if not pair:
            return jsonify({"detail": "Not authenticated"}), 401
        creds, pdata = pair
        try:
            result = create_picker_session(creds)
            pdata.picker_session_id = result.get("id")
            pdata.credentials_json = creds.to_json()
            poll = (result.get("pollingConfig") or {}).get("pollInterval", "5s")
            poll_s = poll.rstrip("s") if isinstance(poll, str) else "5"
            return jsonify(
                {
                    "sessionId": result.get("id"),
                    "pickerUri": result.get("pickerUri"),
                    "pollInterval": poll_s,
                }
            )
        except Exception as e:
            logger.exception("create-session")
            return jsonify({"detail": str(e)}), 502

    @app.get("/api/session-status")
    def api_session_status():
        pair = _creds_for_request()
        if not pair:
            return jsonify({"detail": "Not authenticated"}), 401
        creds, pdata = pair
        if not pdata.picker_session_id:
            return jsonify({"mediaItemsSet": False, "status": "no_session"})
        try:
            result = get_picker_session(creds, pdata.picker_session_id)
            pdata.credentials_json = creds.to_json()
            media_set = bool(result.get("mediaItemsSet"))
            return jsonify(
                {
                    "mediaItemsSet": media_set,
                    "status": "ready" if media_set else "pending",
                }
            )
        except Exception as e:
            logger.warning("session-status: {}", e)
            return jsonify({"mediaItemsSet": False, "status": "error", "error": str(e)})

    @app.get("/api/list-selected")
    def api_list_selected():
        pair = _creds_for_request()
        if not pair:
            return jsonify({"detail": "Not authenticated"}), 401
        creds, pdata = pair
        if not pdata.picker_session_id:
            return jsonify({"items": [], "count": 0})
        try:
            sess = get_picker_session(creds, pdata.picker_session_id)
            if not sess.get("mediaItemsSet"):
                return jsonify({"items": [], "count": 0})
            raw = list_media_items(creds, pdata.picker_session_id)
            pdata.credentials_json = creds.to_json()
            items = transform_picker_items(raw)
            return jsonify({"items": items, "count": len(items)})
        except Exception as e:
            logger.exception("list-selected")
            return jsonify({"detail": str(e)}), 502

    @app.post("/api/process-google")
    def api_process_google():
        pair = _creds_for_request()
        if not pair:
            return jsonify({"detail": "Not authenticated"}), 401
        creds, pdata = pair
        body = request.get_json(silent=True) or {}
        include_json = _parse_bool(body.get("include_json"))
        base_url = (body.get("base_url") or "").strip()
        filename = (body.get("filename") or "photo.jpg").strip() or "photo.jpg"
        if not base_url:
            return jsonify({"detail": "base_url required"}), 400
        ensure_fresh(creds)
        pdata.credentials_json = creds.to_json()
        access_token = creds.token
        if not isinstance(access_token, str):
            return jsonify({"detail": "Google access token unavailable"}), 401
        try:
            raw = google_photos.download_picker_media_bytes(base_url, access_token)
        except Exception as e:
            return jsonify({"detail": f"Download failed: {e}"}), 502

        job = str(uuid.uuid4())
        job_out = output_dir / job
        ensure_directory(job_out)
        name = secure_filename(filename) or "photo.jpg"
        if not is_image_file(Path(name)):
            name = "photo.jpg"
        dest = upload_dir / f"{job}_{name}"
        dest.write_bytes(raw)

        field_config = load_user_exif_field_config(settings.metadata_preferences_path)
        result = process_uploaded_image(dest, job_out, field_config, write_json=include_json)
        if result.get("error"):
            return jsonify({"detail": result["error"]}), 500

        session["last_job"] = job
        return jsonify(
            {
                "ok": True,
                "job_id": job,
                "job_url": url_for("job_result", job_id=job),
                "exif_fields_count": result.get("exif_fields_count", 0),
                "embed_ok": result.get("embed_ok"),
            }
        )

    @app.post("/api/process-google-batch")
    def api_process_google_batch():
        """Download and process all selected Google Picker items into one output job folder."""
        pair = _creds_for_request()
        if not pair:
            return jsonify({"detail": "Not authenticated"}), 401
        creds, pdata = pair
        body = request.get_json(silent=True) or {}
        include_json = _parse_bool(body.get("include_json"))
        items = body.get("items")
        if not isinstance(items, list) or not items:
            return jsonify({"detail": "items must be a non-empty list"}), 400

        ensure_fresh(creds)
        pdata.credentials_json = creds.to_json()
        field_config = load_user_exif_field_config(settings.metadata_preferences_path)

        job_id = str(uuid.uuid4())
        job_out = output_dir / job_id
        ensure_directory(job_out)

        processed = 0
        errors: list[dict[str, str | int]] = []

        for i, it in enumerate(items):
            ensure_fresh(creds)
            pdata.credentials_json = creds.to_json()
            access_token = creds.token
            if not isinstance(access_token, str):
                return jsonify({"detail": "Google access token unavailable"}), 401
            if not isinstance(it, dict):
                errors.append({"index": i, "error": "invalid item"})
                continue
            base_url = (it.get("base_url") or "").strip()
            filename = (it.get("filename") or "photo.jpg").strip() or "photo.jpg"
            if not base_url:
                errors.append({"index": i, "error": "missing base_url"})
                continue

            try:
                raw = google_photos.download_picker_media_bytes(base_url, access_token)
            except Exception as e:
                errors.append({"index": i, "filename": filename, "error": str(e)})
                continue

            stem = secure_filename(filename) or "photo.jpg"
            if not is_image_file(Path(stem)):
                stem = "photo.jpg"
            dest = upload_dir / f"{job_id}_{i}_{stem}"
            dest.write_bytes(raw)

            result = process_uploaded_image(
                dest,
                job_out,
                field_config,
                write_json=include_json,
            )
            if result.get("error"):
                errors.append({"index": i, "filename": stem, "error": result["error"]})
            else:
                processed += 1

        if processed == 0:
            return jsonify(
                {
                    "ok": False,
                    "detail": "No images processed",
                    "processed": 0,
                    "errors": errors,
                }
            ), 500

        session["last_job"] = job_id
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "job_url": url_for("job_result", job_id=job_id),
                "processed": processed,
                "errors": errors,
            }
        )

    return app


def main() -> None:
    app = create_app()
    # Use a stable development port, but avoid collisions in a frozen desktop app.
    default_port = "0" if getattr(__import__("sys"), "frozen", False) else "5001"
    port = int(os.environ.get("PORT", default_port))
    server = make_server("127.0.0.1", port, app)
    url = f"http://127.0.0.1:{server.server_port}"
    logger.info("Photo Meta Sync is running at {}", url)
    threading.Timer(0.2, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Photo Meta Sync stopped")
