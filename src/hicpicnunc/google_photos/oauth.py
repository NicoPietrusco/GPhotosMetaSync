"""
OAuth 2.0 for a local desktop-style app: Installed app client + run_local_server.

End users only sign in with Google; whoever packages the app adds client_secrets.json once.
"""

from __future__ import annotations

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from ..settings import settings

SCOPES = ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]

# Stop waiting for the Google redirect if the user abandons the sign-in page.
SIGN_IN_TIMEOUT_SECONDS = 300


class GooglePhotosOAuth:
    """Desktop OAuth using Google Cloud "Desktop" / Installed client JSON."""

    def __init__(self, client_secret_file: Path | None = None) -> None:
        self.client_secret_file = client_secret_file or settings.google_oauth_client_secrets_path

    def run_local_server(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secret_file),
            SCOPES,
        )
        return flow.run_local_server(
            port=0, open_browser=True, prompt="consent", timeout_seconds=SIGN_IN_TIMEOUT_SECONDS
        )
